#!/usr/bin/env python3
"""Natural-language query interface for the NGraph deep knowledge phase."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import pickle
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.sparse import load_npz
from sklearn.feature_extraction.text import TfidfVectorizer


REQUIRED_MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "scipy": "scipy",
    "sklearn": "sklearn",
}


def check_environment() -> None:
    missing = [name for name, module in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "Missing required Python packages for query execution: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

from ngraph_discovery_common import combo_root, ensure_dirs, read_table  # noqa: E402
from ngraph_rag_orchestrator import augment_result  # noqa: E402


SEED = 42
np.random.seed(SEED)

CANONICAL_QUERIES = [
    "What taxa work together to transition from glacial to interglacial periods?",
    "If I was seeding a new environment similar to that found in core R1 at 150 kya, what are the top 100 taxa I would need?",
    "What are the top functional capabilities that these taxa do and how might they work with the ecosystem?",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discovery_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_knowledge_discovery"


def threshold_root(branch: str, threshold: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / threshold


def setup_logger(log_path: Path) -> logging.Logger:
    ensure_dirs(log_path.parent)
    logger = logging.getLogger(log_path.stem)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(fmt)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def join_text(row: pd.Series, cols: Sequence[str]) -> str:
    parts = []
    for col in cols:
        if col not in row or pd.isna(row[col]):
            continue
        text = str(row[col]).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def semantic_search(cards: pd.DataFrame, matrix, vectorizer: TfidfVectorizer, query: str, top_k: int) -> pd.DataFrame:
    q_vec = vectorizer.transform([query])
    sims = (matrix @ q_vec.T).toarray().ravel()
    out = cards.copy()
    out["semantic_score"] = sims
    out = out.sort_values("semantic_score", ascending=False).head(top_k)
    return out


def normalize_series(series: pd.Series) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    if x.dropna().empty:
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    lo, hi = x.min(), x.max()
    if pd.isna(lo) or pd.isna(hi) or hi == lo:
        return pd.Series(np.zeros(len(series)), index=series.index, dtype=float)
    return (x - lo) / (hi - lo)


def parse_age_kya(query: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*kya", query.lower())
    return float(match.group(1)) if match else None


def parse_core(query: str, cores: Sequence[str]) -> Optional[str]:
    query_l = query.lower()
    cores = sorted(cores, key=len, reverse=True)
    for core in cores:
        if core.lower() in query_l:
            return core
    if "core r1" in query_l or "r1" in query_l:
        for core in cores:
            if core.endswith("_R1") or core.endswith("R1"):
                return core
    if "core r2" in query_l or "r2" in query_l:
        for core in cores:
            if core.endswith("_R2") or core.endswith("R2"):
                return core
    return None


def load_inputs(branch: str):
    discovery_dir = discovery_root(branch)
    cards = pd.read_csv(discovery_dir / "cards" / "evidence_cards.tsv", sep="\t")
    card_index = pd.read_csv(discovery_dir / "indexes" / "card_index.tsv", sep="\t")
    vectorizer = pickle.load((discovery_dir / "indexes" / "card_tfidf_vectorizer.pkl").open("rb"))
    card_matrix = load_npz(discovery_dir / "indexes" / "card_tfidf_matrix.npz")
    vgae_embeddings = pd.read_csv(discovery_dir / "indexes" / "vgae_embedding_index.tsv", sep="\t")
    nn_index = pickle.load((discovery_dir / "indexes" / "vgae_nearest_neighbors.pkl").open("rb"))
    sample_abundance = pd.read_csv(discovery_dir / "tables" / "sample_taxon_abundance_long.tsv", sep="\t")
    sample_clr = pd.read_csv(discovery_dir / "tables" / "sample_taxon_clr_long.tsv", sep="\t")
    sample_qc = pd.read_csv(threshold_root(branch, "prev_5") / "tables" / "ngraph_sample_qc.tsv", sep="\t")
    taxon_nodes = pd.read_csv(combo_root(branch, "prev_5", "pearson", kind="deep_modules") / "tables" / "hetero_taxon_nodes.tsv", sep="\t")
    site_nodes = pd.read_csv(combo_root(branch, "prev_5", "pearson", kind="deep_modules") / "tables" / "hetero_site_nodes.tsv", sep="\t")
    link_prediction = read_table(discovery_dir / "link_prediction_top_candidates.tsv")
    return {
        "cards": cards,
        "card_index": card_index,
        "vectorizer": vectorizer,
        "card_matrix": card_matrix,
        "embeddings": vgae_embeddings,
        "nn_index": nn_index,
        "sample_abundance": sample_abundance,
        "sample_clr": sample_clr,
        "sample_qc": sample_qc,
        "taxon_nodes": taxon_nodes,
        "site_nodes": site_nodes,
        "link_prediction": link_prediction,
        "discovery_dir": discovery_dir,
    }


def semantic_context(cards: pd.DataFrame, matrix, vectorizer, query: str, top_k: int = 8) -> pd.DataFrame:
    hits = semantic_search(cards, matrix, vectorizer, query, top_k=top_k)
    cols = [c for c in ["card_id", "card_type", "entity_id", "title", "summary", "semantic_score", "threshold", "method", "relation_type", "observed_status"] if c in hits.columns]
    return hits[cols]


def build_transition_answer(query: str, data: dict, context_taxa: Optional[List[str]] = None) -> dict:
    sample_qc = data["sample_qc"].copy()
    sample_abundance = data["sample_abundance"].copy()
    cards = data["cards"]
    taxon_nodes = data["taxon_nodes"].copy()
    link_prediction = data["link_prediction"]

    if "mis" not in sample_qc.columns:
        raise SystemExit("sample_qc is missing MIS values needed for transition queries.")

    mis_values = sample_qc["mis"].dropna()
    if mis_values.empty:
        split_val = sample_qc["mis"].median()
    else:
        split_val = mis_values.median()
    low_samples = sample_qc[sample_qc["mis"] <= split_val]["sample" if "sample" in sample_qc.columns else "label"]
    high_samples = sample_qc[sample_qc["mis"] > split_val]["sample" if "sample" in sample_qc.columns else "label"]

    if "sample" not in sample_abundance.columns and "label" in sample_abundance.columns:
        sample_abundance = sample_abundance.rename(columns={"label": "sample"})
    if "sample" not in sample_abundance.columns:
        raise SystemExit("sample abundance table missing sample identifiers.")

    low_mean = sample_abundance[sample_abundance["sample"].isin(low_samples)].groupby("taxon")["abundance"].mean()
    high_mean = sample_abundance[sample_abundance["sample"].isin(high_samples)].groupby("taxon")["abundance"].mean()
    diff = pd.DataFrame({"low_mean": low_mean, "high_mean": high_mean}).fillna(0.0)
    diff["delta"] = diff["high_mean"] - diff["low_mean"]
    diff["abs_delta"] = diff["delta"].abs()
    diff = diff.sort_values("abs_delta", ascending=False)

    taxon_cards = cards[cards["card_type"] == "taxon"].copy()
    taxon_cards = taxon_cards[["entity_id", "title", "summary", "source_tables"]].rename(columns={"entity_id": "taxon"})
    diff = diff.reset_index().rename(columns={"index": "taxon"})
    diff = diff.merge(taxon_cards, on="taxon", how="left")
    diff = diff.merge(taxon_nodes[[c for c in ["taxon", "functional_group", "ecological_role", "tea_primary", "guild_tier", "vgae_module", "diffpool_module"] if c in taxon_nodes.columns]], on="taxon", how="left")
    diff["score"] = normalize_series(diff["abs_delta"])
    diff = diff.sort_values("score", ascending=False)

    candidate_taxa = diff["taxon"].head(20).dropna().tolist()
    if context_taxa:
        candidate_taxa = list(dict.fromkeys(context_taxa + candidate_taxa))

    link_hits = pd.DataFrame()
    if link_prediction is not None and not link_prediction.empty and "taxon_taxon" in set(link_prediction["relation_type"]):
        link_hits = link_prediction[link_prediction["relation_type"] == "taxon_taxon"].copy()
        if "taxon_from" in link_hits.columns:
            link_hits = link_hits[
                link_hits["taxon_from"].isin(candidate_taxa) & link_hits["taxon_to"].isin(candidate_taxa)
            ]
        link_hits = link_hits.sort_values("latent_score", ascending=False).head(10)

    top_taxa = diff.head(20)[["taxon", "score", "delta", "low_mean", "high_mean"]]
    answer_lines = [
        "The strongest transition-linked taxa are the taxa whose abundance shifts most between the two MIS bins, with predicted links used as a second-pass filter.",
        f"Binary MIS split used here: {split_val:.3f} (lower <= split, higher > split).",
    ]
    if len(link_hits) > 0:
        answer_lines.append(
            "The most plausible co-working pairs are the high-scoring predicted links that sit inside the top differential taxa set."
        )
    return {
        "query_type": "transition",
        "query": query,
        "answer_lines": answer_lines,
        "top_taxa": top_taxa,
        "link_hits": link_hits,
        "semantic_hits": semantic_context(cards, data["card_matrix"], data["vectorizer"], query, top_k=8),
        "context_taxa": candidate_taxa[:50],
    }


def build_seed_answer(query: str, data: dict) -> dict:
    sample_qc = data["sample_qc"].copy()
    sample_abundance = data["sample_abundance"].copy()
    taxon_nodes = data["taxon_nodes"].copy()
    cards = data["cards"]
    embeddings = data["embeddings"].copy()
    link_prediction = data["link_prediction"]

    cores = data["sample_qc"]["core"].dropna().astype(str).unique().tolist()
    core = parse_core(query, cores) or "GeoB25202_R1"
    age_target = parse_age_kya(query) or 150.0
    if "sample" not in sample_abundance.columns and "label" in sample_abundance.columns:
        sample_abundance = sample_abundance.rename(columns={"label": "sample"})
    selected = sample_qc[(sample_qc["core"].astype(str) == core) & (sample_qc["age_kyr"].sub(age_target).abs() <= 10.0)].copy()
    if selected.empty:
        selected = sample_qc[sample_qc["core"].astype(str) == core].copy()
    if selected.empty:
        selected = sample_qc.nsmallest(5, "age_kyr").copy()

    selected_samples = selected["sample" if "sample" in selected.columns else "label"].astype(str).tolist()
    abund = sample_abundance[sample_abundance["sample"].isin(selected_samples)].copy()
    abundance_scores = abund.groupby("taxon")["abundance"].mean().rename("mean_abundance").to_frame()
    abundance_scores["presence_count"] = abund.groupby("taxon")["abundance"].apply(lambda x: (x > 0).sum())
    abundance_scores = abundance_scores.fillna(0.0)

    link_deg = pd.DataFrame(columns=["taxon", "predicted_link_degree"])
    if link_prediction is not None and not link_prediction.empty:
        if "taxon_from" in link_prediction.columns:
            from_counts = link_prediction.groupby("taxon_from").size().rename("predicted_link_degree_from").to_frame()
            to_counts = link_prediction.groupby("taxon_to").size().rename("predicted_link_degree_to").to_frame()
            link_deg = from_counts.join(to_counts, how="outer").fillna(0)
            link_deg["predicted_link_degree"] = link_deg.sum(axis=1)
            link_deg = link_deg[["predicted_link_degree"]]
            link_deg.index.name = "taxon"
        elif "taxon" in link_prediction.columns:
            link_deg = link_prediction.groupby("taxon").size().rename("predicted_link_degree").to_frame()
            link_deg.index.name = "taxon"
        link_deg = link_deg.reset_index()

    ranked = abundance_scores.reset_index().rename(columns={"index": "taxon"})
    ranked = ranked.merge(link_deg, on="taxon", how="left")
    ranked = ranked.merge(taxon_nodes[[c for c in ["taxon", "functional_group", "ecological_role", "tea_primary", "guild_tier", "vgae_module", "diffpool_module"] if c in taxon_nodes.columns]], on="taxon", how="left")
    ranked["predicted_link_degree"] = ranked["predicted_link_degree"].fillna(0)
    ranked["combined_score"] = (
        0.6 * normalize_series(ranked["mean_abundance"]) +
        0.2 * normalize_series(ranked["presence_count"]) +
        0.2 * normalize_series(ranked["predicted_link_degree"])
    )
    ranked = ranked.sort_values("combined_score", ascending=False)

    top_taxa = ranked.head(100).copy()
    semantic_hits = semantic_context(cards, data["card_matrix"], data["vectorizer"], query, top_k=10)
    answer_lines = [
        f"I used core {core} samples within approximately {age_target:.1f} kya, with a ±10 kya window when possible.",
        "Taxa were ranked by mean abundance in the selected samples, presence count, and learned-link support.",
    ]
    return {
        "query_type": "seeding",
        "query": query,
        "core": core,
        "age_target": age_target,
        "selected_samples": selected_samples,
        "answer_lines": answer_lines,
        "top_taxa": top_taxa,
        "semantic_hits": semantic_hits,
        "context_taxa": top_taxa["taxon"].head(30).dropna().tolist(),
    }


def build_functional_answer(query: str, data: dict, context_taxa: Optional[List[str]] = None) -> dict:
    taxon_nodes = data["taxon_nodes"].copy()
    cards = data["cards"]
    if context_taxa is None or len(context_taxa) == 0:
        semantic_hits = semantic_context(cards, data["card_matrix"], data["vectorizer"], query, top_k=10)
        context_taxa = semantic_hits.loc[semantic_hits["card_type"] == "taxon", "entity_id"].dropna().astype(str).tolist()
    else:
        semantic_hits = semantic_context(cards, data["card_matrix"], data["vectorizer"], query, top_k=10)

    focus = taxon_nodes[taxon_nodes["taxon"].astype(str).isin(context_taxa)].copy()
    if focus.empty:
        focus = taxon_nodes.head(min(30, len(taxon_nodes))).copy()

    capability_cols = [c for c in ["functional_group", "ecological_role", "tea_primary", "guild_tier", "domain", "phylum", "class"] if c in focus.columns]
    capability_tables = {}
    for col in capability_cols:
        capability_tables[col] = (
            focus.groupby(col).size().sort_values(ascending=False).head(10).rename("N").reset_index()
            if col in focus.columns else pd.DataFrame()
        )

    answer_lines = [
        "The functional profile is driven by the taxa returned by the prior retrieval step, with learned modules and the ontology-style annotations providing the functional labels.",
        "Observed functional annotations are drawn from the taxon reference table; module labels come from VGAE and DiffPool summaries.",
    ]
    return {
        "query_type": "functional",
        "query": query,
        "answer_lines": answer_lines,
        "capability_tables": capability_tables,
        "semantic_hits": semantic_hits,
        "context_taxa": context_taxa,
    }


def format_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or len(df) == 0:
        return "No rows.\n"
    frame = df.head(max_rows).copy()
    cols = list(frame.columns)
    lines = ["|" + "|".join(map(str, cols)) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if pd.isna(value):
                vals.append("NA")
            else:
                vals.append(str(value).replace("|", "/"))
        lines.append("|" + "|".join(vals) + "|")
    return "\n".join(lines)


def render_answer(result: dict) -> str:
    lines = [f"## {result['query']}", ""]
    if result.get("llm_provider"):
        lines.extend(
            [
                f"- LLM provider: `{result.get('llm_provider')}`",
                f"- LLM status: `{result.get('llm_status', '')}`",
            ]
        )
        if result.get("llm_model"):
            lines.append(f"- LLM model: `{result.get('llm_model')}`")
    if result.get("llm_answer"):
        lines.extend(["", "### LLM Synthesis", "", str(result["llm_answer"])])
        if result.get("llm_evidence_ids"):
            lines.extend(["", "#### LLM Evidence IDs", "", ", ".join(map(str, result["llm_evidence_ids"]))])
        if result.get("llm_uncertainty"):
            lines.extend(["", "#### LLM Uncertainty", "", str(result["llm_uncertainty"])])
        if result.get("llm_followups"):
            lines.extend(["", "#### Follow-ups", ""])
            for item in result["llm_followups"]:
                lines.append(f"- {item}")
    for line in result.get("answer_lines", []):
        lines.append(f"- {line}")
    retrieval_summary = result.get("retrieval_summary") or {}
    if retrieval_summary:
        lines.extend(
            [
                "",
                "### Retrieval Summary",
                "",
                f"- Semantic hits: {retrieval_summary.get('semantic_hit_count', 0)}",
                f"- Retrieved cards: {retrieval_summary.get('retrieved_card_count', 0)}",
                f"- Taxon context: {retrieval_summary.get('taxon_context_count', 0)}",
                f"- Module context: {retrieval_summary.get('module_context_count', 0)}",
                f"- Site context: {retrieval_summary.get('site_context_count', 0)}",
                f"- Predicted links: {retrieval_summary.get('predicted_link_count', 0)}",
            ]
        )
    if result.get("semantic_hits") is not None and len(result["semantic_hits"]) > 0:
        lines.extend(["", "### Relevant Cards", "", format_table(result["semantic_hits"])])
    if "retrieved_cards" in result and isinstance(result["retrieved_cards"], pd.DataFrame) and len(result["retrieved_cards"]) > 0:
        lines.extend(["", "### Retrieved Evidence", "", format_table(result["retrieved_cards"])])
    if "top_taxa" in result and result["top_taxa"] is not None and len(result["top_taxa"]) > 0:
        lines.extend(["", "### Top Taxa", "", format_table(result["top_taxa"])])
    if "link_hits" in result and isinstance(result["link_hits"], pd.DataFrame) and len(result["link_hits"]) > 0:
        lines.extend(["", "### Top Predicted Links", "", format_table(result["link_hits"])])
    if "capability_tables" in result:
        for key, table in result["capability_tables"].items():
            if table is None or len(table) == 0:
                continue
            lines.extend([f"", f"### {key}", "", format_table(table)])
    lines.append("")
    return "\n".join(lines)


def choose_query_type(query: str) -> str:
    q = query.lower()
    if "seed" in q or "top 100 taxa" in q or "similar to core" in q or "what taxa would i need" in q:
        return "seeding"
    if "functional capabilities" in q or "what are the top functional" in q or "how might they work" in q:
        return "functional"
    if "glacial" in q or "interglacial" in q or "transition" in q:
        return "transition"
    return "general"


def run_query(
    query: str,
    data: dict,
    context_taxa: Optional[List[str]] = None,
    llm_provider: Optional[str] = None,
) -> dict:
    qtype = choose_query_type(query)
    if qtype == "seeding":
        base = build_seed_answer(query, data)
    elif qtype == "transition":
        base = build_transition_answer(query, data, context_taxa=context_taxa)
    elif qtype == "functional":
        base = build_functional_answer(query, data, context_taxa=context_taxa)
    else:
        base = {
            "query_type": "general",
            "query": query,
            "answer_lines": ["A general semantic retrieval pass was used because no specialized pattern matched."],
            "semantic_hits": semantic_context(data["cards"], data["card_matrix"], data["vectorizer"], query, top_k=10),
            "context_taxa": [],
        }
    return augment_result(query, base, data, top_k=10, llm_provider=llm_provider)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("NG_BRANCH", "abundance_thresholding"))
    parser.add_argument("--query", default=None, help="Run a single natural-language query")
    parser.add_argument("--question-file", default=None, help="Optional text file with one query per line")
    parser.add_argument("--llm-provider", default=os.environ.get("NG_LLM_PROVIDER", "local"), help="LLM provider override: local or gemini")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    logger = setup_logger(project_root() / "logs" / "13_ngraph_query_engine.log")
    logger.info("Starting query engine")
    logger.info("Seed: %d", SEED)
    logger.info("Package versions: numpy %s, pandas %s, scipy %s, sklearn %s", np.__version__, pd.__version__, scipy.__version__, sklearn.__version__)

    data = load_inputs(args.branch)
    discovery_dir = data["discovery_dir"]
    ensure_dirs(discovery_dir / "reports")

    if args.question_file:
        questions = [line.strip() for line in Path(args.question_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    elif args.query:
        questions = [args.query.strip()]
    else:
        questions = CANONICAL_QUERIES

    answers = []
    context_taxa: Optional[List[str]] = None
    report_lines = [
        "# NGraph Natural-Language Query Report",
        "",
        f"- Generated: {pd.Timestamp.utcnow():%Y-%m-%d %H:%M:%S UTC}",
        f"- Seed: `{SEED}`",
        f"- Branch: `{args.branch}`",
        "",
    ]

    for idx, query in enumerate(questions, start=1):
        result = run_query(query, data, context_taxa=context_taxa, llm_provider=args.llm_provider)
        context_taxa = result.get("context_taxa") or context_taxa
        result["query_id"] = idx
        answers.append(result)
        report_lines.extend([f"## Query {idx}", "", f"**Question**: {query}", "", render_answer(result)])

    results_jsonl = discovery_dir / "query_results.jsonl"
    with results_jsonl.open("w", encoding="utf-8") as handle:
        for result in answers:
            serializable = dict(result)
            for key in ["semantic_hits", "top_taxa", "link_hits", "retrieved_cards", "retrieved_links", "llm_response_json"]:
                if key in serializable and isinstance(serializable[key], pd.DataFrame):
                    serializable[key] = serializable[key].to_dict(orient="records")
            if "capability_tables" in serializable:
                serializable["capability_tables"] = {
                    key: (value.to_dict(orient="records") if isinstance(value, pd.DataFrame) else value)
                    for key, value in serializable["capability_tables"].items()
                }
            handle.write(json.dumps(serializable, default=str))
            handle.write("\n")

    flat_rows = []
    for result in answers:
        flat_rows.append(
            {
                "query_id": result["query_id"],
                "query_type": result["query_type"],
                "query": result["query"],
                "context_taxa_count": len(result.get("context_taxa") or []),
                "top_taxa_count": len(result["top_taxa"]) if isinstance(result.get("top_taxa"), pd.DataFrame) else 0,
                "top_links_count": len(result["link_hits"]) if isinstance(result.get("link_hits"), pd.DataFrame) else 0,
            }
        )
    pd.DataFrame(flat_rows).to_csv(discovery_dir / "query_results.tsv", sep="\t", index=False)

    report_path = discovery_dir / "reports" / "NGRAPH_QUERY_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    manifest = {
        "branch": args.branch,
        "llm_provider": args.llm_provider,
        "seed": SEED,
        "questions": questions,
        "results_jsonl": str(results_jsonl),
        "results_tsv": str(discovery_dir / "query_results.tsv"),
        "report": str(report_path),
    }
    with (discovery_dir / "query_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)

    logger.info("Query engine complete")
    logger.info("Report written: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
