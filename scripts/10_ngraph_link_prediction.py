#!/usr/bin/env python3
"""Calibrate learned link-prediction hypotheses from NGraph latent embeddings."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import math
import os
import sys
from itertools import combinations, product
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


REQUIRED_MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "sklearn": "sklearn",
}


def check_environment() -> None:
    missing = [name for name, module in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "Missing required Python packages for link prediction: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

from ngraph_discovery_common import (  # noqa: E402
    combo_root,
    deep_modules_root,
    ensure_dirs,
    list_combo_dirs,
    normalize_threshold_label,
    read_json,
    read_table,
    write_json,
)


SEED = 42
np.random.seed(SEED)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def discovery_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_knowledge_discovery"


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


def markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or len(df) == 0:
        return "No rows.\n"
    frame = df.head(max_rows).copy()
    cols = list(frame.columns)
    lines = ["|" + "|".join(map(str, cols)) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            vals.append("NA" if pd.isna(value) else str(value).replace("|", "/"))
        lines.append("|" + "|".join(vals) + "|")
    return "\n".join(lines)


def safe_numeric_columns(df: pd.DataFrame, exclude: Sequence[str]) -> List[str]:
    cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    if not cols:
        raise SystemExit("No numeric embedding columns found.")
    return cols


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    a_norm = np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = np.linalg.norm(b, axis=1, keepdims=True)
    denom = np.clip(a_norm * b_norm.T, 1e-12, None)
    return (a @ b.T) / denom


def pair_key(a: str, b: str) -> Tuple[str, str]:
    return tuple(sorted((str(a), str(b))))


def sample_negatives(rng: np.random.Generator, candidates: List[Tuple[str, str]], n: int) -> List[Tuple[str, str]]:
    if n <= 0:
        return []
    if len(candidates) <= n:
        return candidates
    idx = rng.choice(len(candidates), size=n, replace=False)
    return [candidates[i] for i in idx]


def fit_relation_model(features: np.ndarray, labels: np.ndarray, seed: int = SEED):
    if len(np.unique(labels)) < 2:
        raise SystemExit("Cannot fit calibration model with a single label class.")
    stratify = labels if min(np.bincount(labels)) >= 2 else None
    train_x, test_x, train_y, test_y = train_test_split(
        features,
        labels,
        test_size=0.2,
        random_state=seed,
        stratify=stratify,
    )
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, random_state=seed, class_weight="balanced"),
    )
    model.fit(train_x, train_y)
    test_prob = model.predict_proba(test_x)[:, 1]
    metrics = {
        "holdout_auc": float(roc_auc_score(test_y, test_prob)),
        "holdout_ap": float(average_precision_score(test_y, test_prob)),
    }
    final_model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, random_state=seed, class_weight="balanced"),
    )
    final_model.fit(features, labels)
    return final_model, metrics


def load_embeddings(path: Path) -> Tuple[pd.DataFrame, List[str]]:
    emb = pd.read_csv(path, sep="\t")
    z_cols = safe_numeric_columns(emb, exclude=["node_id", "node_type"])
    return emb, z_cols


def load_primary_module_lookup(primary_dir: Path) -> Dict[str, Dict[str, str]]:
    lookup: Dict[str, Dict[str, str]] = {}
    vgae_modules = read_table(primary_dir / "tables" / "vgae_taxon_modules.tsv")
    if vgae_modules is not None and "taxon" in vgae_modules.columns:
        lookup["vgae"] = dict(zip(vgae_modules["taxon"].astype(str), vgae_modules["module_kmeans"].astype(str)))
    diffpool_modules = read_table(primary_dir / "tables" / "diffpool_consensus_modules.tsv")
    if diffpool_modules is not None and "taxon" in diffpool_modules.columns:
        lookup["diffpool"] = dict(zip(diffpool_modules["taxon"].astype(str), diffpool_modules["consensus_module"].astype(str)))
    return lookup


def unique_taxon_pairs(edges: pd.DataFrame, left_col: str, right_col: str) -> List[Tuple[str, str]]:
    if edges is None or edges.empty:
        return []
    pairs = {pair_key(a, b) for a, b in zip(edges[left_col].astype(str), edges[right_col].astype(str))}
    return sorted(pairs)


def build_taxon_taxon_scores(
    taxon_nodes: pd.DataFrame,
    taxon_taxon: pd.DataFrame,
    taxon_site: pd.DataFrame,
    embeddings: pd.DataFrame,
    z_cols: List[str],
    threshold: str,
    method: str,
    combo_dir: Path,
    logger: logging.Logger,
) -> pd.DataFrame:
    taxon_emb = embeddings[embeddings["node_type"] == "taxon"].copy()
    taxon_emb = taxon_emb.set_index("node_id").loc[taxon_nodes["taxon"].astype(str)]
    taxon_matrix = taxon_emb[z_cols].to_numpy(dtype=float)
    taxon_names = taxon_emb.index.astype(str).tolist()
    taxon_index = {taxon: i for i, taxon in enumerate(taxon_names)}

    observed_pairs = set(unique_taxon_pairs(taxon_taxon, "taxon_from", "taxon_to"))
    all_pairs = [pair_key(a, b) for a, b in combinations(taxon_names, 2)]
    candidate_pairs = [pair for pair in all_pairs if pair not in observed_pairs]

    taxon_core_sets = {
        taxon: set(group["core"].astype(str))
        for taxon, group in taxon_site.groupby("taxon", sort=False)
    }
    taxon_prevalence = {
        taxon: int(taxon_nodes.loc[taxon_nodes["taxon"].astype(str) == taxon, "n_cores"].iloc[0])
        if "n_cores" in taxon_nodes.columns and not taxon_nodes.loc[taxon_nodes["taxon"].astype(str) == taxon].empty
        else len(taxon_core_sets.get(taxon, set()))
        for taxon in taxon_names
    }

    def feature_row(a: str, b: str) -> List[float]:
        ia, ib = taxon_index[a], taxon_index[b]
        va, vb = taxon_matrix[ia], taxon_matrix[ib]
        cosine = float(np.dot(va, vb) / max(np.linalg.norm(va) * np.linalg.norm(vb), 1e-12))
        shared_cores = len(taxon_core_sets.get(a, set()) & taxon_core_sets.get(b, set()))
        min_prev = min(taxon_prevalence.get(a, 0), taxon_prevalence.get(b, 0))
        max_prev = max(taxon_prevalence.get(a, 0), taxon_prevalence.get(b, 0))
        return [cosine, float(shared_cores), float(min_prev), float(max_prev)]

    positive_pairs = list(observed_pairs)
    negative_pool = candidate_pairs.copy()
    rng = np.random.default_rng(SEED)
    sampled_negatives = sample_negatives(rng, negative_pool, len(positive_pairs))

    train_pairs = positive_pairs + sampled_negatives
    y = np.array([1] * len(positive_pairs) + [0] * len(sampled_negatives), dtype=int)
    x = np.asarray([feature_row(a, b) for a, b in train_pairs], dtype=float)
    model, metrics = fit_relation_model(x, y, seed=SEED)

    candidate_x = np.asarray([feature_row(a, b) for a, b in candidate_pairs], dtype=float)
    candidate_scores = model.predict_proba(candidate_x)[:, 1]

    out = pd.DataFrame(
        {
            "threshold": threshold,
            "method": method,
            "relation_type": "taxon_taxon",
            "taxon_from": [a for a, _ in candidate_pairs],
            "taxon_to": [b for _, b in candidate_pairs],
            "latent_score": candidate_scores,
            "cosine_similarity": candidate_x[:, 0],
            "shared_core_count": candidate_x[:, 1].astype(int),
            "min_core_prevalence": candidate_x[:, 2].astype(int),
            "max_core_prevalence": candidate_x[:, 3].astype(int),
            "observed_status": "absent",
            "model_type": "logistic_calibrated_latent_similarity",
            "holdout_auc": metrics["holdout_auc"],
            "holdout_ap": metrics["holdout_ap"],
        }
    )
    out = out.sort_values("latent_score", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    out.to_csv(combo_dir / "tables" / "ngraph_taxon_taxon_link_predictions.tsv", sep="\t", index=False)
    logger.info("%s/%s taxon-taxon: %d candidate pairs, holdout AUC %.3f", threshold, method, len(out), metrics["holdout_auc"])
    return out


def build_taxon_site_scores(
    taxon_nodes: pd.DataFrame,
    site_nodes: pd.DataFrame,
    taxon_site: pd.DataFrame,
    embeddings: pd.DataFrame,
    z_cols: List[str],
    threshold: str,
    method: str,
    combo_dir: Path,
    logger: logging.Logger,
) -> pd.DataFrame:
    taxon_emb = embeddings[embeddings["node_type"] == "taxon"].copy()
    site_emb = embeddings[embeddings["node_type"] == "site"].copy()
    taxon_emb = taxon_emb.set_index("node_id").loc[taxon_nodes["taxon"].astype(str)]
    site_emb = site_emb.set_index("node_id").loc[site_nodes["core"].astype(str)]
    taxon_matrix = taxon_emb[z_cols].to_numpy(dtype=float)
    site_matrix = site_emb[z_cols].to_numpy(dtype=float)
    taxon_names = taxon_emb.index.astype(str).tolist()
    site_names = site_emb.index.astype(str).tolist()
    taxon_index = {taxon: i for i, taxon in enumerate(taxon_names)}
    site_index = {site: i for i, site in enumerate(site_names)}

    observed_pairs = {(str(row.taxon), str(row.core)) for row in taxon_site.itertuples(index=False)}
    all_pairs = [(taxon, site) for taxon in taxon_names for site in site_names]
    candidate_pairs = [pair for pair in all_pairs if pair not in observed_pairs]

    taxon_prevalence = {
        taxon: int(taxon_nodes.loc[taxon_nodes["taxon"].astype(str) == taxon, "n_cores"].iloc[0])
        if "n_cores" in taxon_nodes.columns and not taxon_nodes.loc[taxon_nodes["taxon"].astype(str) == taxon].empty
        else int(taxon_site[taxon_site["taxon"].astype(str) == taxon]["core"].nunique())
        for taxon in taxon_names
    }
    site_sample_counts = {
        site: int(site_nodes.loc[site_nodes["core"].astype(str) == site, "samples"].iloc[0])
        if "samples" in site_nodes.columns and not site_nodes.loc[site_nodes["core"].astype(str) == site].empty
        else int(taxon_site[taxon_site["core"].astype(str) == site].shape[0])
        for site in site_names
    }
    site_age_mean = {
        site: float(site_nodes.loc[site_nodes["core"].astype(str) == site, "age_mean_kyr"].iloc[0])
        if "age_mean_kyr" in site_nodes.columns and not site_nodes.loc[site_nodes["core"].astype(str) == site].empty
        else math.nan
        for site in site_names
    }
    site_age_span = {
        site: float(
            site_nodes.loc[site_nodes["core"].astype(str) == site, "age_max_kyr"].iloc[0]
            - site_nodes.loc[site_nodes["core"].astype(str) == site, "age_min_kyr"].iloc[0]
        )
        if {"age_max_kyr", "age_min_kyr"}.issubset(site_nodes.columns)
        and not site_nodes.loc[site_nodes["core"].astype(str) == site].empty
        else math.nan
        for site in site_names
    }

    def feature_row(taxon: str, site: str) -> List[float]:
        it, isite = taxon_index[taxon], site_index[site]
        vt, vs = taxon_matrix[it], site_matrix[isite]
        cosine = float(np.dot(vt, vs) / max(np.linalg.norm(vt) * np.linalg.norm(vs), 1e-12))
        return [
            cosine,
            float(taxon_prevalence.get(taxon, 0)),
            float(site_sample_counts.get(site, 0)),
            float(site_age_mean.get(site, math.nan)),
            float(site_age_span.get(site, math.nan)),
        ]

    positive_pairs = list(observed_pairs)
    negative_pool = candidate_pairs.copy()
    rng = np.random.default_rng(SEED + 1)
    sampled_negatives = sample_negatives(rng, negative_pool, len(positive_pairs))

    train_pairs = positive_pairs + sampled_negatives
    y = np.array([1] * len(positive_pairs) + [0] * len(sampled_negatives), dtype=int)
    x = np.asarray([feature_row(a, b) for a, b in train_pairs], dtype=float)
    x = np.nan_to_num(x, nan=np.nanmean(x[np.isfinite(x)]))
    model, metrics = fit_relation_model(x, y, seed=SEED)

    candidate_x = np.asarray([feature_row(a, b) for a, b in candidate_pairs], dtype=float)
    candidate_x = np.nan_to_num(candidate_x, nan=np.nanmean(candidate_x[np.isfinite(candidate_x)]))
    candidate_scores = model.predict_proba(candidate_x)[:, 1]

    out = pd.DataFrame(
        {
            "threshold": threshold,
            "method": method,
            "relation_type": "taxon_site",
            "taxon": [a for a, _ in candidate_pairs],
            "core": [b for _, b in candidate_pairs],
            "latent_score": candidate_scores,
            "cosine_similarity": candidate_x[:, 0],
            "taxon_prevalence_cores": candidate_x[:, 1].astype(int),
            "site_sample_count": candidate_x[:, 2].astype(int),
            "site_age_mean_kyr": candidate_x[:, 3],
            "site_age_span_kyr": candidate_x[:, 4],
            "observed_status": "absent",
            "model_type": "logistic_calibrated_latent_similarity",
            "holdout_auc": metrics["holdout_auc"],
            "holdout_ap": metrics["holdout_ap"],
        }
    )
    out = out.sort_values("latent_score", ascending=False).reset_index(drop=True)
    out["rank"] = np.arange(1, len(out) + 1)
    out.to_csv(combo_dir / "tables" / "ngraph_taxon_site_link_predictions.tsv", sep="\t", index=False)
    logger.info("%s/%s taxon-site: %d candidate pairs, holdout AUC %.3f", threshold, method, len(out), metrics["holdout_auc"])
    return out


def load_combo_inputs(branch: str, threshold: str, method: str):
    combo_dir = combo_root(branch, threshold, method, kind="deep_modules")
    tables = combo_dir / "tables"
    required = [
        tables / "hetero_taxon_nodes.tsv",
        tables / "hetero_site_nodes.tsv",
        tables / "hetero_taxon_taxon_edges.tsv",
        tables / "hetero_site_site_edges.tsv",
        tables / "hetero_taxon_site_edges.tsv",
        tables / "vgae_embeddings.tsv",
    ]
    if not all(path.exists() for path in required):
        return None
    return {
        "combo_dir": combo_dir,
        "taxon_nodes": pd.read_csv(tables / "hetero_taxon_nodes.tsv", sep="\t"),
        "site_nodes": pd.read_csv(tables / "hetero_site_nodes.tsv", sep="\t"),
        "taxon_taxon": pd.read_csv(tables / "hetero_taxon_taxon_edges.tsv", sep="\t"),
        "site_site": pd.read_csv(tables / "hetero_site_site_edges.tsv", sep="\t"),
        "taxon_site": pd.read_csv(tables / "hetero_taxon_site_edges.tsv", sep="\t"),
        "embeddings": pd.read_csv(tables / "vgae_embeddings.tsv", sep="\t"),
        "vgae_summary": read_table(tables / "vgae_run_summary.tsv"),
        "diffpool_summary": read_table(tables / "diffpool_run_summary.tsv"),
        "manifest": read_json(tables / "heterograph_manifest.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("NG_BRANCH", "abundance_thresholding"))
    parser.add_argument("--threshold", default=None, help="Limit to one threshold label such as prev_5")
    parser.add_argument("--method", default=None, help="Limit to one method label")
    parser.add_argument("--top-n", type=int, default=100)
    args = parser.parse_args()

    logger = setup_logger(project_root() / "logs" / "10_ngraph_link_prediction.log")
    logger.info("Starting link prediction")
    logger.info("Seed: %d", SEED)
    logger.info("Package versions: numpy %s, pandas %s, sklearn %s", np.__version__, pd.__version__, sklearn.__version__)

    discovery_dir = discovery_root(args.branch)
    ensure_dirs(discovery_dir, discovery_dir / "reports", discovery_dir / "tables")

    summaries: List[pd.DataFrame] = []
    top_cards: List[pd.DataFrame] = []

    combos = list_combo_dirs(args.branch, kind="deep_modules")
    if args.threshold is not None:
        combos = [c for c in combos if c[0] == normalize_threshold_label(args.threshold)]
    if args.method is not None:
        combos = [c for c in combos if c[1] == args.method]

    if not combos:
        raise SystemExit("No deep-module combos were found for link prediction.")

    for threshold, method, combo_path in combos:
        payload = load_combo_inputs(args.branch, threshold, method)
        if payload is None:
            logger.info("Skipping %s/%s: incomplete deep-module inputs", threshold, method)
            continue

        taxon_taxon_scores = build_taxon_taxon_scores(
            payload["taxon_nodes"],
            payload["taxon_taxon"],
            payload["taxon_site"],
            payload["embeddings"],
            safe_numeric_columns(payload["embeddings"], exclude=["node_id", "node_type"]),
            threshold,
            method,
            combo_path,
            logger,
        )
        taxon_site_scores = build_taxon_site_scores(
            payload["taxon_nodes"],
            payload["site_nodes"],
            payload["taxon_site"],
            payload["embeddings"],
            safe_numeric_columns(payload["embeddings"], exclude=["node_id", "node_type"]),
            threshold,
            method,
            combo_path,
            logger,
        )

        top_cards.append(taxon_taxon_scores.head(args.top_n).assign(card_kind="taxon_taxon"))
        top_cards.append(taxon_site_scores.head(args.top_n).assign(card_kind="taxon_site"))

        combo_summary = pd.DataFrame(
            [
                {
                    "threshold": threshold,
                    "method": method,
                    "taxon_taxon_candidates": int(len(taxon_taxon_scores)),
                    "taxon_site_candidates": int(len(taxon_site_scores)),
                    "taxon_taxon_holdout_auc": float(taxon_taxon_scores["holdout_auc"].iloc[0]) if len(taxon_taxon_scores) else np.nan,
                    "taxon_taxon_holdout_ap": float(taxon_taxon_scores["holdout_ap"].iloc[0]) if len(taxon_taxon_scores) else np.nan,
                    "taxon_site_holdout_auc": float(taxon_site_scores["holdout_auc"].iloc[0]) if len(taxon_site_scores) else np.nan,
                    "taxon_site_holdout_ap": float(taxon_site_scores["holdout_ap"].iloc[0]) if len(taxon_site_scores) else np.nan,
                    "top_taxon_taxon_score": float(taxon_taxon_scores["latent_score"].max()) if len(taxon_taxon_scores) else np.nan,
                    "top_taxon_site_score": float(taxon_site_scores["latent_score"].max()) if len(taxon_site_scores) else np.nan,
                    "output_root": str(combo_path),
                }
            ]
        )
        summaries.append(combo_summary)

    summary_df = pd.concat(summaries, ignore_index=True) if summaries else pd.DataFrame()
    if not summary_df.empty:
        summary_df.to_csv(discovery_dir / "link_prediction_summary.tsv", sep="\t", index=False)

    if top_cards:
        top_df = pd.concat(top_cards, ignore_index=True)
        top_df.to_csv(discovery_dir / "link_prediction_top_candidates.tsv", sep="\t", index=False)

    report_path = discovery_dir / "reports" / "NGRAPH_LINK_PREDICTION_REPORT.md"
    with report_path.open("w", encoding="utf-8") as handle:
        handle.write("# NGraph Learned Link Prediction Report\n\n")
        handle.write(f"- Generated: {pd.Timestamp.utcnow():%Y-%m-%d %H:%M:%S UTC}\n")
        handle.write(f"- Seed: `{SEED}`\n")
        handle.write(f"- Branch: `{args.branch}`\n")
        handle.write("\n## Summary\n\n")
        if summary_df.empty:
            handle.write("No link-prediction outputs were produced.\n")
        else:
            handle.write(markdown_table(summary_df))
            handle.write("\n")

    write_json(
        discovery_dir / "link_prediction_manifest.json",
        {
            "branch": args.branch,
            "seed": SEED,
            "threshold_filter": args.threshold,
            "method_filter": args.method,
            "top_n": args.top_n,
            "summary_table": "link_prediction_summary.tsv",
            "top_candidates_table": "link_prediction_top_candidates.tsv",
        },
    )

    logger.info("Link prediction complete")
    logger.info("Report written: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
