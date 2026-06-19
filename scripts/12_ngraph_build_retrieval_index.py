#!/usr/bin/env python3
"""Build local retrieval indexes over NGraph evidence cards and learned embeddings."""

from __future__ import annotations

import argparse
import importlib.util
import logging
import os
import pickle
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import scipy
import sklearn
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors


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
            "Missing required Python packages for retrieval indexing: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

from ngraph_discovery_common import combo_root, ensure_dirs, read_table, write_json  # noqa: E402


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


def join_text(row: pd.Series, cols: List[str]) -> str:
    parts = []
    for col in cols:
        value = row.get(col)
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("NG_BRANCH", "abundance_thresholding"))
    args = parser.parse_args()

    logger = setup_logger(project_root() / "logs" / "12_ngraph_build_retrieval_index.log")
    logger.info("Starting retrieval index build")
    logger.info("Seed: %d", SEED)
    logger.info("Package versions: numpy %s, pandas %s, scipy %s, sklearn %s", np.__version__, pd.__version__, scipy.__version__, sklearn.__version__)

    discovery_dir = discovery_root(args.branch)
    ensure_dirs(discovery_dir, discovery_dir / "indexes", discovery_dir / "reports")

    cards_path = discovery_dir / "cards" / "evidence_cards.tsv"
    if not cards_path.exists():
        raise SystemExit(f"Missing evidence cards: {cards_path}. Run step 11 first.")

    cards = pd.read_csv(cards_path, sep="\t")
    text_cols = [c for c in ["title", "summary", "evidence", "entity_id", "card_type", "relation_type"] if c in cards.columns]
    cards["card_text"] = cards.apply(lambda row: join_text(row, text_cols), axis=1)

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1, stop_words="english")
    card_matrix = vectorizer.fit_transform(cards["card_text"].fillna(""))
    save_npz(discovery_dir / "indexes" / "card_tfidf_matrix.npz", card_matrix)
    with (discovery_dir / "indexes" / "card_tfidf_vectorizer.pkl").open("wb") as handle:
        pickle.dump(vectorizer, handle)
    cards.drop(columns=["card_text"]).to_csv(discovery_dir / "indexes" / "card_index.tsv", sep="\t", index=False)

    primary_thr = 5
    primary_method = "pearson"
    embedding_path = combo_root(args.branch, f"prev_{primary_thr}", primary_method, kind="deep_modules") / "tables" / "vgae_embeddings.tsv"
    if not embedding_path.exists():
        raise SystemExit(f"Missing VGAE embeddings: {embedding_path}. Run step 07 first.")

    embeddings = pd.read_csv(embedding_path, sep="\t")
    z_cols = [c for c in embeddings.columns if c.startswith("z_")]
    if not z_cols:
        raise SystemExit("No embedding columns found in vgae_embeddings.tsv")

    embed_matrix = embeddings[z_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(np.float32).to_numpy()
    nn_index = NearestNeighbors(metric="cosine", algorithm="brute")
    nn_index.fit(embed_matrix)
    with (discovery_dir / "indexes" / "vgae_nearest_neighbors.pkl").open("wb") as handle:
        pickle.dump(nn_index, handle)
    embeddings.to_csv(discovery_dir / "indexes" / "vgae_embedding_index.tsv", sep="\t", index=False)

    manifest = {
        "branch": args.branch,
        "seed": SEED,
        "card_count": int(len(cards)),
        "embedding_count": int(len(embeddings)),
        "card_index": str(discovery_dir / "indexes" / "card_index.tsv"),
        "card_tfidf_matrix": str(discovery_dir / "indexes" / "card_tfidf_matrix.npz"),
        "card_tfidf_vectorizer": str(discovery_dir / "indexes" / "card_tfidf_vectorizer.pkl"),
        "vgae_embedding_index": str(discovery_dir / "indexes" / "vgae_embedding_index.tsv"),
        "vgae_nearest_neighbors": str(discovery_dir / "indexes" / "vgae_nearest_neighbors.pkl"),
        "source_cards": str(cards_path),
        "source_embeddings": str(embedding_path),
    }
    write_json(discovery_dir / "retrieval_manifest.json", manifest)

    preview = cards[["card_id", "card_type", "entity_id", "threshold", "method"]].head(25)
    preview.to_csv(discovery_dir / "indexes" / "retrieval_preview.tsv", sep="\t", index=False)

    report = discovery_dir / "reports" / "NGRAPH_RETRIEVAL_INDEX_REPORT.md"
    with report.open("w", encoding="utf-8") as handle:
        handle.write("# NGraph Retrieval Index Report\n\n")
        handle.write(f"- Generated: {pd.Timestamp.utcnow():%Y-%m-%d %H:%M:%S UTC}\n")
        handle.write(f"- Seed: `{SEED}`\n")
        handle.write(f"- Card count: {len(cards)}\n")
        handle.write(f"- Embedding count: {len(embeddings)}\n")
        handle.write("\n## Manifest\n\n")
        handle.write(markdown_table(pd.DataFrame([manifest])))
        handle.write("\n")

    logger.info("Retrieval index complete")
    logger.info("Report written: %s", report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
