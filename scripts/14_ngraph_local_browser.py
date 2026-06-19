#!/usr/bin/env python3
"""Local browser for the NGraph deep knowledge discovery artifacts."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import logging
import os
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import networkx as nx
import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ngraph_discovery_common import combo_root, deep_modules_root, knowledge_root, read_json, read_table, safe_slug  # noqa: E402


SEED = 42
np.random.seed(SEED)

PRIMARY_THRESHOLD = "prev_5"
PRIMARY_METHOD = "pearson"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def setup_logger(log_path: Path) -> logging.Logger:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(log_path.stem)
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def load_query_module():
    path = SCRIPT_DIR / "13_ngraph_query_engine.py"
    spec = importlib.util.spec_from_file_location("ngraph_query_engine_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load query engine module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def optional_table(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, sep="\t")


def optional_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_value(value: Any) -> Any:
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if pd.isna(value):
        return None
    return value


def dataframe_records(df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    frame = df.copy()
    if limit is not None:
        frame = frame.head(limit)
    records = []
    for row in frame.to_dict(orient="records"):
        records.append({key: normalize_value(value) for key, value in row.items()})
    return records


def truncate(text: Any, limit: int = 180) -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= limit:
        return s
    return s[: max(0, limit - 1)] + "…"


def color_for_type(node_type: str) -> str:
    colors = {
        "taxon": "#2b8a3e",
        "site": "#1c7ed6",
        "module": "#f08c00",
        "super_site": "#7048e8",
        "focus": "#d9480f",
        "unknown": "#495057",
    }
    return colors.get(node_type, colors["unknown"])


def ensure_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def scale_positions(pos: Dict[str, np.ndarray], width: int, height: int, padding: int = 60) -> Dict[str, Tuple[float, float]]:
    if not pos:
        return {}
    xs = np.array([v[0] for v in pos.values()], dtype=float)
    ys = np.array([v[1] for v in pos.values()], dtype=float)
    x_lo, x_hi = float(np.nanmin(xs)), float(np.nanmax(xs))
    y_lo, y_hi = float(np.nanmin(ys)), float(np.nanmax(ys))
    if x_hi == x_lo:
        x_hi = x_lo + 1.0
    if y_hi == y_lo:
        y_hi = y_lo + 1.0
    scaled = {}
    for key, (x, y) in pos.items():
        sx = padding + (float(x) - x_lo) / (x_hi - x_lo) * max(1, width - 2 * padding)
        sy = padding + (float(y) - y_lo) / (y_hi - y_lo) * max(1, height - 2 * padding)
        scaled[key] = (sx, height - sy)
    return scaled


def build_svg_graph(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], title: str, width: int = 1180, height: int = 720) -> str:
    graph = nx.Graph()
    for node in nodes:
        graph.add_node(node["id"], **node)
    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], **edge)

    if len(graph) == 0:
        return f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'><text x='40' y='60' font-size='18'>No graph data available.</text></svg>"

    if graph.number_of_edges() > 0:
        raw_pos = nx.spring_layout(graph, seed=SEED, weight="weight")
    else:
        raw_pos = nx.circular_layout(graph)
    pos = scale_positions(raw_pos, width, height)

    deg = dict(graph.degree())
    max_deg = max(deg.values()) if deg else 1
    parts = [
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='{html.escape(title)}'>",
        "<style>text{font-family:Arial,Helvetica,sans-serif}.edge{stroke:#adb5bd;stroke-width:1.4;opacity:.55}.node-label{font-size:12px;fill:#1f2933}.legend{font-size:12px;fill:#495057}</style>",
        f"<rect x='0' y='0' width='{width}' height='{height}' rx='18' fill='#f8f9fa'/>",
        f"<text x='24' y='32' class='legend'>{html.escape(title)}</text>",
    ]

    for edge in edges:
        a = edge["source"]
        b = edge["target"]
        if a not in pos or b not in pos:
            continue
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        weight = float(edge.get("weight", edge.get("spectral_similarity", edge.get("edge_jaccard", 0.4))) or 0.4)
        opacity = min(0.9, max(0.15, 0.15 + weight * 0.75))
        stroke_width = 1.0 + min(5.0, max(0.0, weight * 4.0))
        parts.append(
            f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' class='edge' stroke-width='{stroke_width:.2f}' stroke-opacity='{opacity:.2f}'/>"
        )

    for node in nodes:
        node_id = node["id"]
        if node_id not in pos:
            continue
        x, y = pos[node_id]
        node_type = str(node.get("type", "unknown"))
        color = node.get("color") or color_for_type(node_type)
        label = str(node.get("label", node_id))
        size = float(node.get("size", 8))
        radius = max(5.0, min(20.0, size))
        tooltip = html.escape(" | ".join([label, node_type, node_id]))
        highlight = bool(node.get("highlight"))
        stroke = "#111827" if highlight else "#ffffff"
        stroke_width = 2.6 if highlight else 1.2
        parts.append(f"<g><title>{tooltip}</title><circle cx='{x:.2f}' cy='{y:.2f}' r='{radius:.2f}' fill='{color}' stroke='{stroke}' stroke-width='{stroke_width}'/></g>")
        show_label = highlight or deg.get(node_id, 0) >= max(1, max_deg // 3)
        if show_label:
            parts.append(f"<text x='{x + radius + 4:.2f}' y='{y + 4:.2f}' class='node-label'>{html.escape(label)}</text>")

    legend_x = 24
    legend_y = height - 28
    for idx, (name, color) in enumerate([
        ("taxon", color_for_type("taxon")),
        ("site", color_for_type("site")),
        ("module", color_for_type("module")),
        ("focus", color_for_type("focus")),
    ]):
        x = legend_x + idx * 104
        parts.append(f"<circle cx='{x}' cy='{legend_y}' r='6' fill='{color}'/>")
        parts.append(f"<text x='{x + 12}' y='{legend_y + 4}' class='legend'>{name}</text>")

    parts.append("</svg>")
    return "".join(parts)


def build_embedding_svg(frame: pd.DataFrame, focus_id: Optional[str] = None, width: int = 1180, height: int = 720) -> str:
    if frame is None or frame.empty:
        return f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'><text x='40' y='60' font-size='18'>No embedding data available.</text></svg>"

    numeric_cols = [c for c in frame.columns if c.startswith("z_") or c.startswith("embedding_") or c.startswith("pca_")]
    if len(numeric_cols) < 2:
        return f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg'><text x='40' y='60' font-size='18'>Embedding table lacks at least two numeric axes.</text></svg>"

    x_col, y_col = numeric_cols[0], numeric_cols[1]
    xs = ensure_numeric(frame[x_col]).fillna(0.0)
    ys = ensure_numeric(frame[y_col]).fillna(0.0)
    data = frame.copy()
    data["_x"] = xs
    data["_y"] = ys
    x_lo, x_hi = float(data["_x"].min()), float(data["_x"].max())
    y_lo, y_hi = float(data["_y"].min()), float(data["_y"].max())
    if x_hi == x_lo:
        x_hi = x_lo + 1.0
    if y_hi == y_lo:
        y_hi = y_lo + 1.0
    pad = 58
    parts = [
        f"<svg width='{width}' height='{height}' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' role='img'>",
        "<style>text{font-family:Arial,Helvetica,sans-serif}.pt{opacity:.8}.axis{stroke:#adb5bd;stroke-width:1}</style>",
        f"<rect x='0' y='0' width='{width}' height='{height}' rx='18' fill='#f8f9fa'/>",
        f"<text x='24' y='32' font-size='14' fill='#495057'>Embedding manifold: {html.escape(x_col)} vs {html.escape(y_col)}</text>",
        f"<line x1='{pad}' y1='{height - pad}' x2='{width - pad}' y2='{height - pad}' class='axis'/>",
        f"<line x1='{pad}' y1='{pad}' x2='{pad}' y2='{height - pad}' class='axis'/>",
    ]
    for _, row in data.iterrows():
        x = pad + (row["_x"] - x_lo) / (x_hi - x_lo) * (width - 2 * pad)
        y = height - (pad + (row["_y"] - y_lo) / (y_hi - y_lo) * (height - 2 * pad))
        node_id = str(row.get("node_id", row.get("taxon", row.get("core", ""))))
        node_type = str(row.get("node_type", row.get("card_type", "unknown")))
        color = color_for_type(node_type)
        label = str(row.get("label", node_id))
        highlight = bool(focus_id and node_id == focus_id)
        radius = 6.0 if not highlight else 10.0
        parts.append(
            f"<g><title>{html.escape(node_id)} | {html.escape(label)}</title><circle class='pt' cx='{x:.2f}' cy='{y:.2f}' r='{radius:.2f}' fill='{color}' stroke='#111827' stroke-width='{2.0 if highlight else 0.8}'/></g>"
        )
        if highlight:
            parts.append(f"<text x='{x + 12:.2f}' y='{y + 4:.2f}' font-size='12' fill='#111827'>{html.escape(label)}</text>")
    parts.append("</svg>")
    return "".join(parts)


def load_text_table(path: Path) -> pd.DataFrame:
    return optional_table(path)


class NGraphBrowser:
    def __init__(self, branch: str):
        self.branch = branch
        self.discovery_dir = knowledge_root(branch)
        self.deep_modules_dir = deep_modules_root(branch)
        self.threshold_dir = PROJECT_ROOT / "results" / "ngraph" / branch / PRIMARY_THRESHOLD
        self.global_dir = PROJECT_ROOT / "results" / "ngraph"
        self.query_module = load_query_module()
        self.query_data = self.query_module.load_inputs(branch)
        self.cards = load_text_table(self.discovery_dir / "indexes" / "card_index.tsv")
        self.cards = self.cards.reset_index(drop=True)
        self.cards["__row"] = np.arange(len(self.cards))
        self.card_matrix = None
        self.card_vectorizer = None
        try:
            from scipy.sparse import load_npz
            import pickle

            matrix_path = self.discovery_dir / "indexes" / "card_tfidf_matrix.npz"
            vectorizer_path = self.discovery_dir / "indexes" / "card_tfidf_vectorizer.pkl"
            if matrix_path.exists() and vectorizer_path.exists():
                self.card_matrix = load_npz(matrix_path)
                with vectorizer_path.open("rb") as handle:
                    self.card_vectorizer = pickle.load(handle)
        except Exception:
            self.card_matrix = None
            self.card_vectorizer = None
        self.vgae_embeddings = load_text_table(self.discovery_dir / "indexes" / "vgae_embedding_index.tsv")
        self.link_predictions = load_text_table(self.discovery_dir / "link_prediction_top_candidates.tsv")
        self.sample_abundance = load_text_table(self.discovery_dir / "tables" / "sample_taxon_abundance_long.tsv")
        self.sample_clr = load_text_table(self.discovery_dir / "tables" / "sample_taxon_clr_long.tsv")
        self.evidence_inventory = load_text_table(self.discovery_dir / "tables" / "evidence_card_inventory.tsv")
        self.query_results = load_text_table(self.discovery_dir / "query_results.tsv")
        self.query_manifest = optional_json(self.discovery_dir / "query_manifest.json")
        self.discovery_manifest = optional_json(self.discovery_dir / "evidence_card_manifest.json")
        self.link_manifest = optional_json(self.discovery_dir / "link_prediction_manifest.json")
        self.retrieval_manifest = optional_json(self.discovery_dir / "retrieval_manifest.json")
        self.all_similarity = load_text_table(PROJECT_ROOT / "results" / "ngraph" / branch / "tables" / "ngraph_all_threshold_graph_similarity.tsv")
        self.all_site_summary = load_text_table(PROJECT_ROOT / "results" / "ngraph" / branch / "tables" / "ngraph_all_threshold_site_graph_summary.tsv")
        self.super_nodes = load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_nodes.tsv")
        self.super_edges = load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_edges.tsv")
        self.super_nodes_by_method = {
            "all": self.super_nodes,
            "spearman": load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_nodes_spearman.tsv"),
            "mi_aracne": load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_nodes_mi_aracne.tsv"),
        }
        self.super_edges_by_method = {
            "all": self.super_edges,
            "spearman": load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_edges_spearman.tsv"),
            "mi_aracne": load_text_table(PROJECT_ROOT / "results" / "ngraph" / "tables" / "ngraph_super_graph_edges_mi_aracne.tsv"),
        }
        self.primary_combo = {
            "threshold": PRIMARY_THRESHOLD,
            "method": PRIMARY_METHOD,
        }

    def summary(self) -> Dict[str, Any]:
        card_counts = self.cards.groupby("card_type").size().sort_values(ascending=False).reset_index(name="count") if not self.cards.empty else pd.DataFrame()
        link_counts = self.link_predictions.groupby("relation_type").size().sort_values(ascending=False).reset_index(name="count") if not self.link_predictions.empty else pd.DataFrame()
        query_counts = self.query_results.copy()
        card_thresholds = sorted(self.cards["threshold"].dropna().astype(str).unique().tolist()) if not self.cards.empty and "threshold" in self.cards.columns else []
        card_methods = sorted(self.cards["method"].dropna().astype(str).unique().tolist()) if not self.cards.empty and "method" in self.cards.columns else []
        card_relations = sorted(self.cards["relation_type"].dropna().astype(str).unique().tolist()) if not self.cards.empty and "relation_type" in self.cards.columns else []
        reports = []
        for name in sorted((self.discovery_dir / "reports").glob("*.md")):
            reports.append({"name": name.name, "path": str(name)})
        phase_status = {
            "link_prediction": "complete" if not self.link_predictions.empty else "missing",
            "evidence_cards": "complete" if not self.cards.empty else "missing",
            "retrieval_index": "complete" if self.card_matrix is not None else "missing",
            "query_engine": "complete" if not self.query_results.empty else "missing",
            "browser": "complete",
        }
        return {
            "branch": self.branch,
            "seed": SEED,
            "primary_threshold": PRIMARY_THRESHOLD,
            "primary_method": PRIMARY_METHOD,
            "paths": {
                "discovery_dir": str(self.discovery_dir),
                "deep_modules_dir": str(self.deep_modules_dir),
                "threshold_dir": str(self.threshold_dir),
            },
            "counts": {
                "cards": int(len(self.cards)),
                "vgae_embeddings": int(len(self.vgae_embeddings)),
                "link_predictions": int(len(self.link_predictions)),
                "sample_abundance_rows": int(len(self.sample_abundance)),
                "sample_clr_rows": int(len(self.sample_clr)),
                "query_results": int(len(self.query_results)),
                "reports": int(len(reports)),
            },
            "card_counts": dataframe_records(card_counts),
            "link_counts": dataframe_records(link_counts),
            "query_counts": dataframe_records(query_counts),
            "card_thresholds": card_thresholds,
            "card_methods": card_methods,
            "card_relations": card_relations,
            "reports": reports,
            "phase_status": phase_status,
            "questions": list(self.query_module.CANONICAL_QUERIES),
            "llm_provider_default": os.environ.get("NG_LLM_PROVIDER", "local"),
            "combos": self.available_combos(),
        }

    def available_combos(self) -> List[Dict[str, Any]]:
        combos = []
        for thr_dir in sorted((PROJECT_ROOT / "results" / "ngraph" / self.branch / "deep_modules").glob("prev_*")):
            if not thr_dir.is_dir():
                continue
            for method_dir in sorted(thr_dir.iterdir()):
                if method_dir.is_dir():
                    combos.append({"threshold": thr_dir.name, "method": method_dir.name})
        return combos

    @lru_cache(maxsize=32)
    def combo_context(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD) -> Dict[str, pd.DataFrame]:
        root = combo_root(self.branch, threshold, method, kind="deep_modules")
        if not root.exists():
            raise FileNotFoundError(f"Missing combo directory: {root}")
        context = {
            "taxon_nodes": load_text_table(root / "tables" / "hetero_taxon_nodes.tsv"),
            "site_nodes": load_text_table(root / "tables" / "hetero_site_nodes.tsv"),
            "taxon_site_edges": load_text_table(root / "tables" / "hetero_taxon_site_edges.tsv"),
            "taxon_taxon_edges": load_text_table(root / "tables" / "hetero_taxon_taxon_edges.tsv"),
            "vgae_modules": load_text_table(root / "tables" / "vgae_taxon_modules.tsv"),
            "diffpool_modules": load_text_table(root / "tables" / "diffpool_consensus_modules.tsv"),
            "vgae_run_summary": load_text_table(root / "tables" / "vgae_run_summary.tsv"),
            "diffpool_run_summary": load_text_table(root / "tables" / "diffpool_run_summary.tsv"),
            "vgae_embeddings": load_text_table(root / "tables" / "vgae_embeddings.tsv"),
            "link_taxon_taxon": load_text_table(root / "tables" / "ngraph_taxon_taxon_link_predictions.tsv"),
            "link_taxon_site": load_text_table(root / "tables" / "ngraph_taxon_site_link_predictions.tsv"),
        }
        if not context["taxon_nodes"].empty:
            taxon_cols = [c for c in ["taxon", "functional_group", "ecological_role", "tea_primary", "guild_tier", "domain", "phylum", "class"] if c in context["taxon_nodes"].columns]
            context["taxon_nodes"] = context["taxon_nodes"][taxon_cols + [c for c in context["taxon_nodes"].columns if c not in taxon_cols]].copy()
        return context

    def semantic_cards(self, query: str, top_k: int = 15) -> pd.DataFrame:
        if self.card_matrix is None or self.card_vectorizer is None or self.cards.empty:
            frame = self.cards.copy()
            if query:
                mask = frame.apply(lambda row: query.lower() in " ".join(str(row.get(col, "")) for col in ["title", "summary", "evidence", "entity_id"]).lower(), axis=1)
                frame = frame[mask]
            return frame.head(top_k)
        q_vec = self.card_vectorizer.transform([query])
        scores = (self.card_matrix @ q_vec.T).toarray().ravel()
        out = self.cards.copy()
        out["semantic_score"] = scores
        if query:
            out = out.sort_values(["semantic_score", "card_type", "title"], ascending=[False, True, True])
        else:
            out = out.sort_values(["semantic_score", "title"], ascending=[False, True])
        return out.head(top_k)

    def filter_cards(self, query: str = "", card_type: str = "", threshold: str = "", method: str = "", relation_type: str = "", limit: int = 50) -> pd.DataFrame:
        frame = self.cards.copy()
        if card_type:
            frame = frame[frame["card_type"].astype(str) == card_type]
        if threshold:
            frame = frame[frame["threshold"].astype(str) == str(threshold)]
        if method:
            frame = frame[frame["method"].astype(str) == str(method)]
        if relation_type:
            frame = frame[frame["relation_type"].astype(str) == relation_type]
        if query:
            q = query.lower().strip()
            if self.card_matrix is not None and self.card_vectorizer is not None and len(self.cards) == self.card_matrix.shape[0]:
                semantic = self.semantic_cards(query, top_k=len(self.cards))
                merged = semantic[semantic["card_id"].isin(frame["card_id"])]
                frame = merged
            else:
                mask = frame.apply(
                    lambda row: q in " ".join(
                        str(row.get(col, "")) for col in ["card_id", "entity_id", "title", "summary", "evidence", "core", "taxon", "module", "relation_type"]
                    ).lower(),
                    axis=1,
                )
                frame = frame[mask]
        if "semantic_score" in frame.columns:
            frame = frame.sort_values(["semantic_score", "title"], ascending=[False, True])
        else:
            frame = frame.sort_values(["card_type", "title"], ascending=[True, True])
        return frame.head(limit)

    def module_summary(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD, kind: str = "vgae", module_id: str = "") -> Tuple[pd.DataFrame, pd.DataFrame, str]:
        context = self.combo_context(threshold, method)
        taxon_nodes = context["taxon_nodes"].copy()
        module_col = "module_kmeans" if kind == "vgae" else "consensus_module"
        if module_col not in (context["vgae_modules"].columns if kind == "vgae" else context["diffpool_modules"].columns):
            return pd.DataFrame(), pd.DataFrame(), ""
        if kind == "vgae":
            modules = context["vgae_modules"].copy()
            modules = modules.rename(columns={"module_kmeans": "module_id"})
            taxon_nodes = taxon_nodes.merge(modules[["taxon", "module_id"]], on="taxon", how="left")
        else:
            modules = context["diffpool_modules"].copy()
            modules = modules.rename(columns={"consensus_module": "module_id"})
            taxon_nodes = taxon_nodes.merge(modules[["taxon", "module_id"]], on="taxon", how="left")
        if taxon_nodes.empty:
            return pd.DataFrame(), pd.DataFrame(), ""
        focus_df = taxon_nodes.copy()
        if module_id:
            focus_df = focus_df[focus_df["module_id"].astype(str) == str(module_id)]
        if focus_df.empty:
            focus_df = taxon_nodes.copy()
        summary = (
            focus_df.groupby("module_id")
            .agg(
                taxa=("taxon", "count"),
                top_functional_group=("functional_group", lambda s: s.dropna().astype(str).value_counts().index[0] if s.dropna().size else ""),
                top_ecological_role=("ecological_role", lambda s: s.dropna().astype(str).value_counts().index[0] if s.dropna().size else ""),
            )
            .reset_index()
        )
        if kind == "vgae":
            summary = summary.merge(
                modules.groupby("module_id").agg(
                    mean_silhouette=("silhouette", "mean"),
                    mean_entropy_proxy=("module_entropy_proxy", "mean"),
                    module_count=("module_count", "max"),
                ).reset_index(),
                on="module_id",
                how="left",
            )
        else:
            summary = summary.merge(
                modules.groupby("module_id").agg(
                    mean_assignment_entropy=("mean_assignment_entropy", "mean"),
                    sites_present=("sites_present", "max"),
                ).reset_index(),
                on="module_id",
                how="left",
            )
        summary = summary.sort_values(["taxa", "module_id"], ascending=[False, True])
        if module_id:
            focus_rows = focus_df.sort_values(["taxon"]).copy()
        else:
            first_module = summary["module_id"].iloc[0] if len(summary) else ""
            focus_rows = focus_df[focus_df["module_id"].astype(str) == str(first_module)].sort_values(["taxon"]).copy() if first_module else focus_df.head(0)
            module_id = str(first_module)
        return summary, focus_rows, module_id

    def build_super_graph_payload(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD) -> Dict[str, Any]:
        frame = self.all_similarity.copy()
        if not frame.empty:
            frame["threshold"] = frame["threshold"].astype(str)
            frame = frame[frame["threshold"] == str(threshold)]
            frame = frame[frame["method"].astype(str) == str(method)]
        if frame.empty:
            frame = self.super_edges_by_method.get(method, self.super_edges).copy()
        nodes = self.all_site_summary.copy()
        if not nodes.empty:
            nodes["threshold"] = nodes["threshold"].astype(str)
            nodes = nodes[nodes["threshold"] == str(threshold)]
            nodes = nodes[nodes["method"].astype(str) == str(method)]
        if nodes.empty:
            nodes = self.super_nodes_by_method.get(method, self.super_nodes).copy()
        graph_nodes = []
        for _, row in nodes.iterrows():
            node_id = str(row.get("core", row.get("name", "")))
            if not node_id:
                continue
            label = node_id
            if "core" in row and not pd.isna(row.get("core")):
                label = str(row.get("core"))
            size_source = row.get("components", row.get("leiden_module", 1))
            size_value = pd.to_numeric(pd.Series([size_source]), errors="coerce").iloc[0]
            if pd.isna(size_value):
                size_value = 1.0
            size = 9 + float(size_value) * 0.15
            graph_nodes.append(
                {
                    "id": node_id,
                    "label": f"{label}",
                    "type": "site",
                    "size": size,
                    "color": color_for_type("site"),
                    "highlight": False,
                }
            )
        graph_edges = []
        for _, row in frame.iterrows():
            source = str(row.get("core_a", row.get("from", row.get("source", ""))))
            target = str(row.get("core_b", row.get("to", row.get("target", ""))))
            if not source or not target:
                continue
            weight = float(row.get("super_weight", row.get("weight", row.get("spectral_similarity", row.get("edge_jaccard", 0.4)))) or 0.4)
            graph_edges.append({"source": source, "target": target, "weight": weight})
            if source not in {n["id"] for n in graph_nodes}:
                graph_nodes.append({"id": source, "label": source, "type": "site", "size": 9, "color": color_for_type("site")})
            if target not in {n["id"] for n in graph_nodes}:
                graph_nodes.append({"id": target, "label": target, "type": "site", "size": 9, "color": color_for_type("site")})
        svg = build_svg_graph(graph_nodes, graph_edges, f"Super graph {threshold} / {method}")
        return {
            "title": f"Site similarity super graph ({threshold} / {method})",
            "nodes": graph_nodes,
            "edges": graph_edges,
            "svg": svg,
            "rows": dataframe_records(frame, limit=250),
            "summary_rows": dataframe_records(nodes, limit=100),
        }

    def build_taxon_graph_payload(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD, focus: str = "", limit: int = 24) -> Dict[str, Any]:
        context = self.combo_context(threshold, method)
        taxon_nodes = context["taxon_nodes"].copy()
        link_taxon_taxon = context["link_taxon_taxon"].copy()
        taxon_site_edges = context["taxon_site_edges"].copy()
        taxon_taxon_edges = context["taxon_taxon_edges"].copy()
        vgae_modules = context["vgae_modules"].copy()
        diffpool_modules = context["diffpool_modules"].copy()
        if taxon_nodes.empty:
            return {"title": "Taxon graph unavailable", "nodes": [], "edges": [], "svg": build_svg_graph([], [], "Taxon graph unavailable")}
        if not focus:
            if not self.cards.empty and "entity_id" in self.cards.columns:
                candidates = self.cards[self.cards["card_type"].astype(str) == "taxon"]["entity_id"].dropna().astype(str).head(1).tolist()
                focus = candidates[0] if candidates else str(taxon_nodes["taxon"].iloc[0])
            else:
                focus = str(taxon_nodes["taxon"].iloc[0])
        focus = str(focus)
        graph_nodes: Dict[str, Dict[str, Any]] = {}
        graph_edges: List[Dict[str, Any]] = []

        def add_node(node_id: str, node_type: str, label: Optional[str] = None, highlight: bool = False, size: float = 8.0):
            if not node_id:
                return
            if node_id not in graph_nodes:
                graph_nodes[node_id] = {
                    "id": node_id,
                    "label": label or node_id,
                    "type": node_type,
                    "size": size,
                    "color": color_for_type(node_type),
                    "highlight": highlight,
                }
            else:
                if highlight:
                    graph_nodes[node_id]["highlight"] = True

        add_node(focus, "taxon", focus, True, 12.0)
        if "taxon" in taxon_nodes.columns:
            taxon_rows = taxon_nodes[taxon_nodes["taxon"].astype(str) == focus]
        else:
            taxon_rows = pd.DataFrame()
        if taxon_rows.empty:
            taxon_rows = taxon_nodes.head(1)
            focus = str(taxon_rows["taxon"].iloc[0])
            add_node(focus, "taxon", focus, True, 12.0)
        if not vgae_modules.empty and {"taxon", "module_kmeans"}.issubset(vgae_modules.columns):
            matches = vgae_modules[vgae_modules["taxon"].astype(str) == focus]
            if not matches.empty:
                module_id = str(matches["module_kmeans"].iloc[0])
                add_node(f"vgae:{module_id}", "module", f"VGAE {module_id}", False, 10.0)
                graph_edges.append({"source": focus, "target": f"vgae:{module_id}", "weight": 0.95})
        if not diffpool_modules.empty and {"taxon", "consensus_module"}.issubset(diffpool_modules.columns):
            matches = diffpool_modules[diffpool_modules["taxon"].astype(str) == focus]
            if not matches.empty:
                module_id = str(matches["consensus_module"].iloc[0])
                add_node(f"diffpool:{module_id}", "module", f"DiffPool {module_id}", False, 10.0)
                graph_edges.append({"source": focus, "target": f"diffpool:{module_id}", "weight": 0.85})
        if not link_taxon_taxon.empty:
            cols = [c for c in ["taxon_from", "taxon_to", "latent_score", "cosine_similarity", "relation_type"] if c in link_taxon_taxon.columns]
            rows = link_taxon_taxon.copy()
            if "taxon_from" in rows.columns:
                mask = (rows["taxon_from"].astype(str) == focus) | (rows["taxon_to"].astype(str) == focus)
                rows = rows[mask]
            rows = rows.sort_values("latent_score", ascending=False).head(limit)
            for _, row in rows.iterrows():
                a = str(row.get("taxon_from", ""))
                b = str(row.get("taxon_to", ""))
                other = b if a == focus else a
                if not other:
                    continue
                add_node(other, "taxon", other, False, 8.0)
                weight = float(row.get("latent_score", row.get("cosine_similarity", 0.5)) or 0.5)
                graph_edges.append({"source": focus, "target": other, "weight": weight})
        if not taxon_site_edges.empty and "taxon" in taxon_site_edges.columns:
            rows = taxon_site_edges[taxon_site_edges["taxon"].astype(str) == focus].copy().head(limit)
            for _, row in rows.iterrows():
                site = str(row.get("core", ""))
                if not site:
                    continue
                add_node(site, "site", site, False, 9.5)
                weight = float(row.get("prevalence", row.get("mean_tax_abund_tad", 0.4)) or 0.4)
                graph_edges.append({"source": focus, "target": site, "weight": min(1.0, weight)})
        if not taxon_taxon_edges.empty:
            rows = taxon_taxon_edges.copy()
            if {"taxon_from", "taxon_to"}.issubset(rows.columns):
                rows = rows[(rows["taxon_from"].astype(str) == focus) | (rows["taxon_to"].astype(str) == focus)]
            rows = rows.sort_values("weight", ascending=False).head(limit)
            for _, row in rows.iterrows():
                a = str(row.get("taxon_from", ""))
                b = str(row.get("taxon_to", ""))
                other = b if a == focus else a
                if not other:
                    continue
                add_node(other, "taxon", other, False, 8.0)
                graph_edges.append({"source": focus, "target": other, "weight": float(row.get("weight", 0.4) or 0.4)})
        svg = build_svg_graph(list(graph_nodes.values()), graph_edges, f"Taxon graph around {focus}")
        return {
            "title": f"Taxon-centric graph around {focus}",
            "focus": focus,
            "nodes": list(graph_nodes.values()),
            "edges": graph_edges,
            "svg": svg,
            "taxon_row": dataframe_records(taxon_rows, limit=1),
            "predicted_links": dataframe_records(link_taxon_taxon[(link_taxon_taxon["taxon_from"].astype(str) == focus) | (link_taxon_taxon["taxon_to"].astype(str) == focus)] if not link_taxon_taxon.empty and "taxon_from" in link_taxon_taxon.columns else pd.DataFrame(), limit=limit),
        }

    def build_site_graph_payload(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD, focus: str = "", limit: int = 24) -> Dict[str, Any]:
        context = self.combo_context(threshold, method)
        site_nodes = context["site_nodes"].copy()
        taxon_site_edges = context["taxon_site_edges"].copy()
        taxon_nodes = context["taxon_nodes"].copy()
        if site_nodes.empty:
            return {"title": "Site graph unavailable", "nodes": [], "edges": [], "svg": build_svg_graph([], [], "Site graph unavailable")}
        if not focus:
            focus = str(site_nodes["core"].iloc[0]) if "core" in site_nodes.columns else str(site_nodes.iloc[0, 0])
        focus = str(focus)
        graph_nodes: Dict[str, Dict[str, Any]] = {}
        graph_edges: List[Dict[str, Any]] = []

        def add_node(node_id: str, node_type: str, label: Optional[str] = None, highlight: bool = False, size: float = 8.0):
            if not node_id:
                return
            if node_id not in graph_nodes:
                graph_nodes[node_id] = {
                    "id": node_id,
                    "label": label or node_id,
                    "type": node_type,
                    "size": size,
                    "color": color_for_type(node_type),
                    "highlight": highlight,
                }
            else:
                if highlight:
                    graph_nodes[node_id]["highlight"] = True

        add_node(focus, "site", focus, True, 12.0)
        if "core" in site_nodes.columns:
            site_rows = site_nodes[site_nodes["core"].astype(str) == focus]
        else:
            site_rows = pd.DataFrame()
        if site_rows.empty:
            site_rows = site_nodes.head(1)
            focus = str(site_rows["core"].iloc[0]) if "core" in site_rows.columns else str(site_rows.iloc[0, 0])
            add_node(focus, "site", focus, True, 12.0)
        if not taxon_site_edges.empty and "core" in taxon_site_edges.columns:
            rows = taxon_site_edges[taxon_site_edges["core"].astype(str) == focus].copy()
            if "mean_tax_abund_tad" in rows.columns:
                rows = rows.sort_values("mean_tax_abund_tad", ascending=False)
            elif "prevalence" in rows.columns:
                rows = rows.sort_values("prevalence", ascending=False)
            rows = rows.head(limit)
            for _, row in rows.iterrows():
                taxon = str(row.get("taxon", ""))
                if not taxon:
                    continue
                add_node(taxon, "taxon", taxon, False, 8.0)
                weight = float(row.get("mean_tax_abund_tad", row.get("prevalence", 0.4)) or 0.4)
                graph_edges.append({"source": focus, "target": taxon, "weight": min(1.0, weight / (abs(weight) + 1.0))})
        svg = build_svg_graph(list(graph_nodes.values()), graph_edges, f"Site graph around {focus}")
        return {
            "title": f"Site-centric graph around {focus}",
            "focus": focus,
            "nodes": list(graph_nodes.values()),
            "edges": graph_edges,
            "svg": svg,
            "site_row": dataframe_records(site_rows, limit=1),
            "taxa": dataframe_records(rows if 'rows' in locals() else pd.DataFrame(), limit=limit),
        }

    def build_module_payload(self, threshold: str = PRIMARY_THRESHOLD, method: str = PRIMARY_METHOD, kind: str = "vgae", module_id: str = "", limit: int = 40) -> Dict[str, Any]:
        summary, focus_rows, focus_module = self.module_summary(threshold, method, kind=kind, module_id=module_id)
        if summary.empty:
            return {"title": "Module summary unavailable", "summary": [], "members": [], "svg": build_svg_graph([], [], "Module graph unavailable")}
        if not focus_module:
            focus_module = str(summary["module_id"].iloc[0])
        focus_rows = focus_rows.copy()
        if focus_rows.empty:
            focus_rows = summary.head(0)
        graph_nodes: List[Dict[str, Any]] = []
        graph_edges: List[Dict[str, Any]] = []
        module_node_id = f"{kind}:{focus_module}"
        graph_nodes.append({"id": module_node_id, "label": f"{kind.upper()} {focus_module}", "type": "module", "size": 12.0, "color": color_for_type("module"), "highlight": True})
        for _, row in focus_rows.head(limit).iterrows():
            taxon = str(row.get("taxon", ""))
            if not taxon:
                continue
            graph_nodes.append({"id": taxon, "label": taxon, "type": "taxon", "size": 8.0, "color": color_for_type("taxon")})
            graph_edges.append({"source": module_node_id, "target": taxon, "weight": 0.9})
        svg = build_svg_graph(graph_nodes, graph_edges, f"{kind.upper()} module {focus_module}")
        members = dataframe_records(focus_rows, limit=limit)
        return {
            "title": f"{kind.upper()} module {focus_module}",
            "module_id": focus_module,
            "kind": kind,
            "summary": dataframe_records(summary, limit=100),
            "members": members,
            "svg": svg,
        }

    def build_embedding_payload(self, focus: str = "", limit: int = 800) -> Dict[str, Any]:
        frame = self.vgae_embeddings.copy()
        if frame.empty:
            return {"title": "Embedding unavailable", "svg": build_embedding_svg(frame), "rows": []}
        if focus:
            focus = str(focus)
        svg = build_embedding_svg(frame.head(limit), focus_id=focus)
        return {
            "title": "VGAE embedding manifold",
            "focus": focus,
            "svg": svg,
            "rows": dataframe_records(frame, limit=limit),
        }

    def query(self, query: str, context_taxa: Optional[List[str]] = None, llm_provider: Optional[str] = None) -> Dict[str, Any]:
        result = self.query_module.run_query(query, self.query_data, context_taxa=context_taxa, llm_provider=llm_provider)
        serializable = dict(result)
        for key in ["semantic_hits", "top_taxa", "link_hits", "retrieved_cards", "retrieved_links"]:
            if key in serializable and isinstance(serializable[key], pd.DataFrame):
                serializable[key] = dataframe_records(serializable[key], limit=len(serializable[key]))
        if "capability_tables" in serializable:
            serializable["capability_tables"] = {
                key: dataframe_records(value, limit=len(value)) if isinstance(value, pd.DataFrame) else value
                for key, value in serializable["capability_tables"].items()
            }
        serializable["markdown"] = self.query_module.render_answer(result)
        return serializable

    def health(self) -> Dict[str, Any]:
        provider = os.environ.get("NG_LLM_PROVIDER", "local").strip().lower() or "local"
        api_key_present = bool((os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip())
        return {
            "status": "ok",
            "branch": self.branch,
            "project_root": str(PROJECT_ROOT),
            "discovery_dir": str(self.discovery_dir),
            "cards": int(len(self.cards)),
            "link_predictions": int(len(self.link_predictions)),
            "query_results": int(len(self.query_results)),
            "llm_provider_default": provider,
            "gemini_key_present": api_key_present,
            "gemini_model": os.environ.get("NG_GEMINI_MODEL", "gemini-3.1-flash-lite"),
        }

    def report_names(self) -> List[str]:
        reports = []
        if self.discovery_dir.exists():
            for path in sorted((self.discovery_dir / "reports").glob("*.md")):
                reports.append(path.name)
        return reports

    def report_text(self, name: str) -> str:
        safe = Path(name).name
        path = self.discovery_dir / "reports" / safe
        if not path.exists():
            raise FileNotFoundError(f"Unknown report: {name}")
        return path.read_text(encoding="utf-8")


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NGraph Local Browser</title>
  <style>
    :root {
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --line: #334155;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #22c55e;
      --accent-2: #38bdf8;
      --warning: #f59e0b;
      --danger: #fb7185;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #020617 0%, #0f172a 35%, #111827 100%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(16px);
      background: rgba(2, 6, 23, 0.92);
      border-bottom: 1px solid rgba(148, 163, 184, 0.18);
      padding: 18px 24px;
    }
    .title {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
    }
    .title h1 {
      margin: 0;
      font-size: 24px;
      letter-spacing: 0.02em;
    }
    .title .meta {
      color: var(--muted);
      font-size: 13px;
      text-align: right;
    }
    .title .meta-stack {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 8px;
    }
    nav {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 14px;
    }
    nav a {
      text-decoration: none;
      color: var(--text);
      background: rgba(148, 163, 184, 0.12);
      border: 1px solid rgba(148, 163, 184, 0.18);
      padding: 8px 12px;
      border-radius: 999px;
      font-size: 13px;
    }
    main {
      padding: 22px 24px 40px;
      max-width: 1500px;
      margin: 0 auto;
    }
    section {
      margin-bottom: 24px;
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 20px;
      background: rgba(15, 23, 42, 0.76);
      box-shadow: 0 20px 45px rgba(2, 6, 23, 0.28);
      overflow: hidden;
    }
    .section-head {
      padding: 18px 20px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.12);
    }
    .section-head h2 {
      margin: 0 0 6px;
      font-size: 18px;
    }
    .section-head p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .section-body {
      padding: 18px 20px 22px;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .stat {
      background: rgba(15, 23, 42, 0.86);
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 16px;
      padding: 14px;
    }
    .stat .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }
    .stat .value { font-size: 28px; margin-top: 6px; font-weight: 700; }
    .grid-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .grid-3 {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
    }
    .panel {
      background: rgba(2, 6, 23, 0.55);
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 16px;
      padding: 16px;
    }
    .panel h3 {
      margin: 0 0 12px;
      font-size: 15px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 14px;
      align-items: center;
    }
    input, select, textarea, button {
      font: inherit;
      border-radius: 12px;
      border: 1px solid rgba(148, 163, 184, 0.2);
      background: #0b1220;
      color: var(--text);
      padding: 10px 12px;
    }
    input, select, textarea { min-width: 180px; }
    textarea { width: 100%; min-height: 100px; resize: vertical; }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(56, 189, 248, 0.95));
      color: #07111f;
      font-weight: 700;
      border: none;
      padding: 10px 14px;
    }
    button.secondary {
      background: rgba(148, 163, 184, 0.16);
      color: var(--text);
      border: 1px solid rgba(148, 163, 184, 0.22);
    }
    .muted { color: var(--muted); }
    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 0; }
    .chip {
      border-radius: 999px;
      padding: 6px 10px;
      background: rgba(148, 163, 184, 0.12);
      border: 1px solid rgba(148, 163, 184, 0.16);
      font-size: 12px;
    }
    .table-wrap { overflow-x: auto; border-radius: 14px; border: 1px solid rgba(148, 163, 184, 0.12); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead th {
      position: sticky; top: 0;
      background: rgba(15, 23, 42, 0.98);
      color: #cbd5e1;
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.16);
      white-space: nowrap;
    }
    tbody td {
      padding: 9px 12px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.08);
      vertical-align: top;
    }
    tbody tr:hover { background: rgba(148, 163, 184, 0.08); }
    .svg-box {
      width: 100%;
      min-height: 320px;
      overflow: auto;
      border-radius: 16px;
      border: 1px solid rgba(148, 163, 184, 0.12);
      background: rgba(2, 6, 23, 0.6);
    }
    .svg-box svg { display: block; width: 100%; height: auto; }
    .report-box {
      width: 100%;
      min-height: 260px;
      max-height: 520px;
      overflow: auto;
      white-space: pre-wrap;
      background: #08111f;
      border: 1px solid rgba(148, 163, 184, 0.12);
      border-radius: 16px;
      padding: 14px;
      color: #d1d5db;
    }
    .status-banner {
      margin: 14px 24px 0;
      max-width: 1500px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(148, 163, 184, 0.18);
      background: rgba(15, 23, 42, 0.82);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .status-banner.ok {
      border-color: rgba(34, 197, 94, 0.35);
      color: #bbf7d0;
    }
    .status-banner.warning {
      border-color: rgba(245, 158, 11, 0.38);
      color: #fde68a;
    }
    .status-banner.error {
      border-color: rgba(251, 113, 133, 0.4);
      color: #fecdd3;
    }
    .two-col {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 16px;
    }
    @media (max-width: 1050px) {
      .grid-2, .two-col { grid-template-columns: 1fr; }
      .title { align-items: flex-start; flex-direction: column; }
      .title .meta { text-align: left; }
    }
  </style>
</head>
<body>
  <header>
    <div class="title">
      <div>
        <h1>NGraph Local Browser</h1>
        <div class="muted">Deep knowledge discovery, local-first, bound to 0.0.0.0 for network access.</div>
      </div>
      <div class="meta-stack">
        <div class="meta" id="header-meta">Loading summary...</div>
        <div class="chip-row" id="llm-status"></div>
      </div>
    </div>
    <nav>
      <a href="#overview">Overview</a>
      <a href="#cards">Evidence Cards</a>
      <a href="#links">Predicted Links</a>
      <a href="#supergraph">Super Graph</a>
      <a href="#modules">Modules</a>
      <a href="#embeddings">Embeddings</a>
      <a href="#query">Query Console</a>
      <a href="#reports">Reports</a>
    </nav>
  </header>
  <div id="browser-status" class="status-banner">Loading browser...</div>
  <script>
    (function () {
      var el = document.getElementById("browser-status");
      if (el) {
        el.textContent = "Browser JS bootstrap active. Loading summary...";
        el.className = "status-banner ok";
      }
      window.__ngraphBrowserBootstrap = true;
    })();
  </script>
  <main>
    <section id="overview">
      <div class="section-head">
        <h2>Overview</h2>
        <p>Top-level counts, phase status, and current artifact locations.</p>
      </div>
      <div class="section-body">
        <div class="stats" id="stats"></div>
        <div class="grid-2">
          <div class="panel">
            <h3>Phase Status</h3>
            <div id="phase-status" class="chip-row"></div>
          </div>
          <div class="panel">
            <h3>Canonical Questions</h3>
            <div id="questions" class="chip-row"></div>
          </div>
        </div>
      </div>
    </section>

    <section id="cards">
      <div class="section-head">
        <h2>Evidence Cards</h2>
        <p>Browse taxon, site, module, and predicted-link cards with local semantic ranking.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <input id="card-query" type="text" placeholder="Search cards..." />
          <select id="card-type"><option value="">All card types</option></select>
          <select id="card-threshold"><option value="">All thresholds</option></select>
          <select id="card-method"><option value="">All methods</option></select>
          <select id="card-relation"><option value="">All relation types</option></select>
          <button onclick="loadCards()">Search</button>
        </div>
        <div class="table-wrap" id="cards-table"></div>
      </div>
    </section>

    <section id="links">
      <div class="section-head">
        <h2>Predicted Links</h2>
        <p>Browse learned taxon-taxon and taxon-site hypotheses. Select a focus node to rebuild the local graph.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <select id="link-threshold"><option value="prev_5">prev_5</option></select>
          <select id="link-method"><option value="pearson">pearson</option></select>
          <select id="link-relation"><option value="">All relations</option></select>
          <input id="link-focus" type="text" placeholder="Focus taxon or site" />
          <button onclick="loadLinks()">Refresh links</button>
          <button class="secondary" onclick="loadGraph('taxon')">Build taxon graph</button>
          <button class="secondary" onclick="loadGraph('site')">Build site graph</button>
        </div>
        <div class="grid-2">
          <div class="table-wrap" id="links-table"></div>
          <div class="svg-box" id="graph-box"></div>
        </div>
      </div>
    </section>

    <section id="supergraph">
      <div class="section-head">
        <h2>Super Graph</h2>
        <p>Graph-of-graphs / site similarity viewer with threshold and method selection.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <select id="super-threshold"></select>
          <select id="super-method"></select>
          <button onclick="loadSuperGraph()">Refresh super graph</button>
        </div>
        <div class="grid-2">
          <div class="svg-box" id="supergraph-box"></div>
          <div class="table-wrap" id="supergraph-table"></div>
        </div>
      </div>
    </section>

    <section id="modules">
      <div class="section-head">
        <h2>Modules</h2>
        <p>Browse VGAE and DiffPool modules, membership lists, and their learned structure.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <select id="module-kind"><option value="vgae">VGAE</option><option value="diffpool">DiffPool</option></select>
          <select id="module-threshold"></select>
          <select id="module-method"></select>
          <select id="module-id"></select>
          <button onclick="loadModules()">Refresh modules</button>
        </div>
        <div class="grid-2">
          <div class="svg-box" id="module-box"></div>
          <div class="table-wrap" id="module-table"></div>
        </div>
      </div>
    </section>

    <section id="embeddings">
      <div class="section-head">
        <h2>Embedding Manifold</h2>
        <p>Inspect the learned VGAE latent space and highlight any node by ID.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <input id="embedding-focus" type="text" placeholder="Focus node ID" />
          <button onclick="loadEmbeddings()">Refresh embedding view</button>
        </div>
        <div class="svg-box" id="embedding-box"></div>
      </div>
    </section>

    <section id="query">
      <div class="section-head">
        <h2>Query Console</h2>
        <p>Run the local natural-language query engine against the learned network and evidence cards.</p>
      </div>
        <div class="section-body">
          <div class="panel" style="margin-bottom: 16px;">
            <textarea id="query-text" placeholder="Ask about taxa, modules, transitions, seeding, or functional capabilities."></textarea>
            <div class="controls" style="margin-top: 10px;">
              <label style="display:flex; align-items:center; gap:8px;">
                <span class="muted">Mode</span>
                <select id="query-provider">
                  <option value="local">Local retrieval</option>
                  <option value="gemini">Gemini synthesis</option>
                </select>
              </label>
              <button onclick="runQuery()">Run query</button>
              <button class="secondary" onclick="setCanonicalQuery(0)">Transition</button>
              <button class="secondary" onclick="setCanonicalQuery(1)">Seeding</button>
              <button class="secondary" onclick="setCanonicalQuery(2)">Function</button>
            </div>
        </div>
        <div class="two-col">
          <div class="panel">
            <h3>Answer</h3>
            <div id="query-answer" class="report-box"></div>
          </div>
          <div class="panel">
            <h3>Semantic Hits</h3>
            <div class="table-wrap" id="query-table"></div>
          </div>
        </div>
        <div class="two-col" style="margin-top: 16px;">
          <div class="panel">
            <h3>Retrieved Evidence</h3>
            <div class="table-wrap" id="retrieval-table"></div>
          </div>
          <div class="panel">
            <h3>Prompt Preview</h3>
            <div id="query-prompt" class="report-box"></div>
          </div>
        </div>
        <div class="panel" style="margin-top: 16px;">
          <h3>Query Debug</h3>
          <div id="query-debug" class="report-box"></div>
        </div>
      </div>
    </section>

    <section id="reports">
      <div class="section-head">
        <h2>Reports</h2>
        <p>Open the generated markdown reports directly in the browser.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <select id="report-select"></select>
          <button onclick="loadReport()">Load report</button>
        </div>
        <div class="report-box" id="report-box">Select a report to view its contents.</div>
      </div>
    </section>
  </main>

  <script>
    const PRIMARY_THRESHOLD = "prev_5";
    const PRIMARY_METHOD = "pearson";
    window.__ngraphBrowserMainScript = true;
    const state = {
      summary: null,
      cards: [],
      questions: [],
      llmProvider: "local",
    };

    function escapeHtml(text) {
      return String(text == null ? "" : text).replace(/[&<>"']/g, (m) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[m]));
    }

    function tableHtml(rows, maxRows = 80) {
      if (!rows || rows.length === 0) {
        return '<div class="panel"><div class="muted">No rows.</div></div>';
      }
      const cols = Object.keys(rows[0]);
      const body = rows.slice(0, maxRows).map(row => {
        const cells = cols.map(col => `<td>${escapeHtml(row[col] == null ? "" : row[col])}</td>`).join("");
        return `<tr>${cells}</tr>`;
      }).join("");
      return `<table><thead><tr>${cols.map(col => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function chip(text, color = "") {
      const style = color ? ` style="border-color:${color}; color:${color};"` : "";
      return `<span class="chip"${style}>${escapeHtml(text)}</span>`;
    }

    function renderLlmStatus(payload = {}) {
      const provider = payload.llm_provider || state.llmProvider || "local";
      const status = payload.llm_status || (provider === "gemini" ? "not_run" : "local");
      const model = payload.llm_model || "";
      const parts = [
        chip(`Mode: ${provider}` , provider === "gemini" ? "var(--accent-2)" : "var(--accent)"),
        chip(`LLM: ${status}`, status === "ok" ? "var(--accent)" : (status && status !== "local" ? "var(--warning)" : "var(--accent)")),
      ];
      if (model) {
        parts.push(chip(`Model: ${model}`, "var(--accent-2)"));
      }
      document.getElementById("llm-status").innerHTML = parts.join("");
    }

    function setBrowserStatus(message, kind = "info") {
      const el = document.getElementById("browser-status");
      if (!el) return;
      el.className = kind ? `status-banner ${kind}` : "status-banner";
      el.textContent = message;
    }

    function handleBrowserError(prefix, err) {
      const message = `${prefix}: ${err && err.message ? err.message : String(err)}`;
      setBrowserStatus(message, "error");
      console.error(prefix, err);
    }

    async function safeLoad(label, fn) {
      try {
        await fn();
        return true;
      } catch (err) {
        handleBrowserError(label, err);
        return false;
      }
    }

    function bindEvent(id, eventName, handler) {
      const el = document.getElementById(id);
      if (!el) {
        console.warn(`Missing element for ${id}`);
        return;
      }
      el.addEventListener(eventName, handler);
    }

    async function fetchJson(url) {
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`${res.status} ${res.statusText}`);
      }
      return await res.json();
    }

    function populateSelect(id, values, includeAll = true, placeholder = "") {
      const el = document.getElementById(id);
      el.innerHTML = "";
      if (includeAll) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = placeholder || "All";
        el.appendChild(opt);
      }
      values.filter(Boolean).forEach(value => {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = value;
        el.appendChild(opt);
      });
    }

    async function init() {
      setBrowserStatus("Main browser script active. Loading summary and panels...", "info");
      const summary = await fetchJson("/api/summary");
      state.summary = summary;
      state.questions = summary.questions || [];
      state.llmProvider = summary.llm_provider_default || "local";
      document.getElementById("header-meta").textContent = `${summary.branch} | ${summary.primary_threshold} / ${summary.primary_method}`;
      renderLlmStatus({ llm_provider: state.llmProvider, llm_status: state.llmProvider === "gemini" ? "pending_key" : "local" });
      const counts = summary.counts || {};
      const stats = [
        ["Cards", counts.cards || 0],
        ["Embeddings", counts.vgae_embeddings || 0],
        ["Predicted links", counts.link_predictions || 0],
        ["Query rows", counts.query_results || 0],
        ["Reports", counts.reports || 0],
        ["Combos", (summary.combos || []).length],
      ];
      document.getElementById("stats").innerHTML = stats.map(([label, value]) => `<div class="stat"><div class="label">${escapeHtml(label)}</div><div class="value">${escapeHtml(value)}</div></div>`).join("");
      document.getElementById("phase-status").innerHTML = Object.entries(summary.phase_status || {}).map(([k, v]) => chip(`${k}: ${v}`, v === "complete" ? "var(--accent)" : "var(--warning)")).join("");
      document.getElementById("questions").innerHTML = state.questions.map((q, i) => `<span class="chip" style="cursor:pointer" onclick="setCanonicalQuery(${i})">${escapeHtml(q)}</span>`).join("");

      populateSelect("card-type", (summary.card_counts || []).map(x => x.card_type), true, "All card types");
      populateSelect("card-threshold", summary.card_thresholds || [], true, "All thresholds");
      populateSelect("card-method", summary.card_methods || [], true, "All methods");
      populateSelect("card-relation", summary.card_relations || [], true, "All relation types");
      populateSelect("link-relation", (summary.link_counts || []).map(x => x.relation_type), true, "All relations");
      populateSelect("link-threshold", [...new Set((summary.combos || []).map(x => x.threshold))], false);
      populateSelect("link-method", [...new Set((summary.combos || []).map(x => x.method))], false);
      populateSelect("super-threshold", [...new Set((summary.combos || []).map(x => x.threshold))], false);
      populateSelect("super-method", [...new Set((summary.combos || []).map(x => x.method))], false);
      populateSelect("module-threshold", [...new Set((summary.combos || []).map(x => x.threshold))], false);
      populateSelect("module-method", [...new Set((summary.combos || []).map(x => x.method))], false);
      document.getElementById("module-kind").value = "vgae";

      const reportSelect = document.getElementById("report-select");
      reportSelect.innerHTML = (summary.reports || []).map(r => `<option value="${escapeHtml(r.name)}">${escapeHtml(r.name)}</option>`).join("");
      if (summary.reports && summary.reports.length > 0) {
        reportSelect.value = summary.reports[0].name;
      }

      document.getElementById("card-threshold").value = "";
      document.getElementById("card-method").value = "";
      document.getElementById("card-relation").value = "";
      document.getElementById("link-threshold").value = summary.primary_threshold || PRIMARY_THRESHOLD;
      document.getElementById("link-method").value = summary.primary_method || PRIMARY_METHOD;
      document.getElementById("super-threshold").value = summary.primary_threshold || PRIMARY_THRESHOLD;
      document.getElementById("super-method").value = summary.primary_method || PRIMARY_METHOD;
      document.getElementById("module-threshold").value = summary.primary_threshold || PRIMARY_THRESHOLD;
      document.getElementById("module-method").value = summary.primary_method || PRIMARY_METHOD;
      document.getElementById("query-provider").value = state.llmProvider;

      const loaders = [
        safeLoad("Cards panel", loadCards),
        safeLoad("Links panel", loadLinks),
        safeLoad("Super graph panel", loadSuperGraph),
        safeLoad("Modules panel", loadModules),
        safeLoad("Embedding panel", loadEmbeddings),
        safeLoad("Report panel", loadReport),
      ];
      await Promise.all(loaders);
      setBrowserStatus("Panels loaded. Query example will run in the background.", "ok");
      setTimeout(() => {
        safeLoad("Example query", loadQueryExample);
      }, 0);
    }

    async function loadCards() {
      const q = document.getElementById("card-query").value || "";
      const params = new URLSearchParams({
        query: q,
        card_type: document.getElementById("card-type").value || "",
        threshold: document.getElementById("card-threshold").value || "",
        method: document.getElementById("card-method").value || "",
        relation_type: document.getElementById("card-relation").value || "",
        limit: "80",
      });
      const data = await fetchJson(`/api/cards?${params.toString()}`);
      document.getElementById("cards-table").innerHTML = tableHtml(data.rows);
    }

    async function loadLinks() {
      const params = new URLSearchParams({
        threshold: document.getElementById("link-threshold").value || "prev_5",
        method: document.getElementById("link-method").value || "pearson",
        relation_type: document.getElementById("link-relation").value || "",
        focus: document.getElementById("link-focus").value || "",
        limit: "80",
      });
      const data = await fetchJson(`/api/links?${params.toString()}`);
      document.getElementById("links-table").innerHTML = tableHtml(data.rows);
      document.getElementById("graph-box").innerHTML = data.graph_svg || "";
    }

    async function loadSuperGraph() {
      const params = new URLSearchParams({
        threshold: document.getElementById("super-threshold").value || "prev_5",
        method: document.getElementById("super-method").value || "pearson",
      });
      const data = await fetchJson(`/api/supergraph?${params.toString()}`);
      document.getElementById("supergraph-box").innerHTML = data.svg || "";
      document.getElementById("supergraph-table").innerHTML = tableHtml(data.rows || []);
    }

    async function loadModules() {
      const params = new URLSearchParams({
        threshold: document.getElementById("module-threshold").value || "prev_5",
        method: document.getElementById("module-method").value || "pearson",
        kind: document.getElementById("module-kind").value || "vgae",
        module_id: document.getElementById("module-id").value || "",
        limit: "60",
      });
      const data = await fetchJson(`/api/modules?${params.toString()}`);
      const options = (data.summary || []).map(row => `<option value="${escapeHtml(row.module_id)}">${escapeHtml(row.module_id)} (${escapeHtml(row.taxa)})</option>`).join("");
      document.getElementById("module-id").innerHTML = options || "<option value=''>No modules</option>";
      if (data.module_id) {
        document.getElementById("module-id").value = data.module_id;
      }
      document.getElementById("module-box").innerHTML = data.svg || "";
      document.getElementById("module-table").innerHTML = tableHtml(data.members || []);
      document.getElementById("embedding-focus").value = data.focus_taxon || document.getElementById("embedding-focus").value;
    }

    async function loadEmbeddings() {
      const params = new URLSearchParams({
        focus: document.getElementById("embedding-focus").value || "",
      });
      const data = await fetchJson(`/api/embedding?${params.toString()}`);
      document.getElementById("embedding-box").innerHTML = data.svg || "";
    }

    async function runQuery() {
      const query = document.getElementById("query-text").value.trim();
      if (!query) return;
      const provider = document.getElementById("query-provider").value || "local";
      state.llmProvider = provider;
      const params = new URLSearchParams({ query, llm_provider: provider });
      document.getElementById("query-answer").textContent = "Running query...";
      document.getElementById("query-debug").textContent = "Waiting for response...";
      try {
        const data = await fetchJson(`/api/query?${params.toString()}`);
        renderLlmStatus(data);
        document.getElementById("query-answer").textContent = data.markdown || "";
        document.getElementById("query-table").innerHTML = tableHtml(data.semantic_hits || []);
        document.getElementById("retrieval-table").innerHTML = tableHtml(data.retrieved_cards || []);
        document.getElementById("query-prompt").textContent = data.retrieval_prompt || (data.retrieval_bundle && data.retrieval_bundle.prompt_preview) || "";
        const debugLines = [
          `provider: ${data.llm_provider || "local"}`,
          `status: ${data.llm_status || ""}`,
          `model: ${data.llm_model || ""}`,
        ];
        if (data.llm_answer) {
          debugLines.push("");
          debugLines.push("LLM answer:");
          debugLines.push(String(data.llm_answer));
        }
        if (data.llm_raw_text) {
          debugLines.push("");
          debugLines.push("Raw LLM text:");
          debugLines.push(String(data.llm_raw_text));
        }
        document.getElementById("query-debug").textContent = debugLines.join("\\n");
        if (data.context_taxa && data.context_taxa.length > 0) {
          document.getElementById("embedding-focus").value = data.context_taxa[0];
        }
      } catch (err) {
        document.getElementById("query-answer").textContent = `Query failed: ${err.message}`;
        document.getElementById("query-debug").textContent = `provider: ${provider}\\nerror: ${err.message}`;
        handleBrowserError("Query", err);
      }
    }

    async function loadQueryExample() {
      if (!state.questions.length) return;
      document.getElementById("query-text").value = state.questions[0];
      await runQuery();
    }

    function setCanonicalQuery(index) {
      if (!state.questions[index]) return;
      document.getElementById("query-text").value = state.questions[index];
      runQuery();
    }

    async function loadReport() {
      const name = document.getElementById("report-select").value;
      if (!name) {
        document.getElementById("report-box").textContent = "No report selected.";
        return;
      }
      const data = await fetchJson(`/api/report?name=${encodeURIComponent(name)}`);
      document.getElementById("report-box").textContent = data.content || "";
    }

    async function loadGraph(kind) {
      const params = new URLSearchParams({
        kind,
        threshold: document.getElementById("link-threshold").value || "prev_5",
        method: document.getElementById("link-method").value || "pearson",
        focus: document.getElementById("link-focus").value || "",
      });
      const data = await fetchJson(`/api/graph?${params.toString()}`);
      document.getElementById("graph-box").innerHTML = data.svg || "";
    }

    bindEvent("module-kind", "change", loadModules);
    bindEvent("module-id", "change", loadModules);
    bindEvent("super-threshold", "change", loadSuperGraph);
    bindEvent("super-method", "change", loadSuperGraph);
    bindEvent("link-threshold", "change", loadLinks);
    bindEvent("link-method", "change", loadLinks);
    bindEvent("link-relation", "change", loadLinks);
    bindEvent("card-type", "change", loadCards);
    bindEvent("card-threshold", "change", loadCards);
    bindEvent("card-method", "change", loadCards);
    bindEvent("card-relation", "change", loadCards);
    bindEvent("report-select", "change", loadReport);

    window.addEventListener("error", (event) => {
      handleBrowserError("Browser error", event.error || new Error(event.message || "Unknown browser error"));
    });
    window.addEventListener("unhandledrejection", (event) => {
      handleBrowserError("Unhandled promise rejection", event.reason || new Error("Unknown promise rejection"));
    });

    init().catch(err => {
      document.body.insertAdjacentHTML("afterbegin", `<div style="padding:16px;background:#7f1d1d;color:#fff">Browser failed to load: ${escapeHtml(err.message)}</div>`);
      console.error(err);
      setBrowserStatus(`Browser failed to load: ${err.message}`, "error");
    });
  </script>
</body>
</html>
"""


class BrowserHandler(BaseHTTPRequestHandler):
    app: NGraphBrowser

    def log_message(self, format: str, *args: Any) -> None:
        self.server.app.logger.info("%s - %s", self.client_address[0], format % args)

    def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, default=normalize_value, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        app = self.server.app

        try:
            if path == "/":
                self.send_text(HTML_PAGE, content_type="text/html; charset=utf-8")
                return
            if path == "/api/summary":
                self.send_json(app.summary())
                return
            if path == "/api/health":
                self.send_json(app.health())
                return
            if path == "/api/cards":
                rows = app.filter_cards(
                    query=params.get("query", [""])[0],
                    card_type=params.get("card_type", [""])[0],
                    threshold=params.get("threshold", [""])[0],
                    method=params.get("method", [""])[0],
                    relation_type=params.get("relation_type", [""])[0],
                    limit=int(params.get("limit", ["80"])[0]),
                )
                self.send_json({"rows": dataframe_records(rows, limit=len(rows))})
                return
            if path == "/api/links":
                threshold = params.get("threshold", [PRIMARY_THRESHOLD])[0]
                method = params.get("method", [PRIMARY_METHOD])[0]
                relation_type = params.get("relation_type", [""])[0]
                focus = params.get("focus", [""])[0]
                context = app.combo_context(threshold, method)
                frame = context["link_taxon_taxon"].copy()
                if frame.empty:
                    frame = app.link_predictions.copy()
                if relation_type and "relation_type" in frame.columns:
                    frame = frame[frame["relation_type"].astype(str) == relation_type]
                if focus and {"taxon_from", "taxon_to"}.issubset(frame.columns):
                    mask = (frame["taxon_from"].astype(str) == focus) | (frame["taxon_to"].astype(str) == focus)
                    frame = frame[mask]
                sort_cols = [c for c in ["latent_score", "score", "cosine_similarity", "weight"] if c in frame.columns]
                if sort_cols:
                    frame = frame.sort_values(sort_cols, ascending=False)
                limit = int(params.get("limit", ["80"])[0])
                rows = dataframe_records(frame, limit=limit)
                graph = app.build_taxon_graph_payload(threshold=threshold, method=method, focus=focus, limit=max(16, min(40, limit)))
                self.send_json({"rows": rows, "graph_svg": graph["svg"], "graph_title": graph["title"]})
                return
            if path == "/api/graph":
                kind = params.get("kind", ["taxon"])[0]
                threshold = params.get("threshold", [PRIMARY_THRESHOLD])[0]
                method = params.get("method", [PRIMARY_METHOD])[0]
                focus = params.get("focus", [""])[0]
                if kind == "super":
                    payload = app.build_super_graph_payload(threshold=threshold, method=method)
                elif kind == "site":
                    payload = app.build_site_graph_payload(threshold=threshold, method=method, focus=focus)
                else:
                    payload = app.build_taxon_graph_payload(threshold=threshold, method=method, focus=focus)
                self.send_json(payload)
                return
            if path == "/api/supergraph":
                threshold = params.get("threshold", [PRIMARY_THRESHOLD])[0]
                method = params.get("method", [PRIMARY_METHOD])[0]
                payload = app.build_super_graph_payload(threshold=threshold, method=method)
                self.send_json(payload)
                return
            if path == "/api/modules":
                threshold = params.get("threshold", [PRIMARY_THRESHOLD])[0]
                method = params.get("method", [PRIMARY_METHOD])[0]
                kind = params.get("kind", ["vgae"])[0]
                module_id = params.get("module_id", [""])[0]
                payload = app.build_module_payload(threshold=threshold, method=method, kind=kind, module_id=module_id, limit=int(params.get("limit", ["40"])[0]))
                self.send_json(payload)
                return
            if path == "/api/embedding":
                focus = params.get("focus", [""])[0]
                payload = app.build_embedding_payload(focus=focus)
                self.send_json(payload)
                return
            if path == "/api/query":
                query = params.get("query", [""])[0]
                context_taxa = params.get("context_taxa", [""])[0]
                llm_provider = params.get("llm_provider", [""])[0].strip() or None
                taxa = [item.strip() for item in context_taxa.split(",") if item.strip()] if context_taxa else None
                payload = app.query(query, context_taxa=taxa, llm_provider=llm_provider)
                app.logger.info(
                    "query provider=%s status=%s model=%s query=%s",
                    payload.get("llm_provider", "local"),
                    payload.get("llm_status", ""),
                    payload.get("llm_model", ""),
                    query[:160],
                )
                self.send_json(payload)
                return
            if path == "/api/report":
                name = params.get("name", [""])[0]
                self.send_json({"name": name, "content": app.report_text(name)})
                return
            if path == "/api/reports":
                self.send_json({"reports": app.report_names()})
                return
            self.send_response(404)
            self.end_headers()
        except Exception as exc:  # pragma: no cover - runtime guard
            self.send_json({"error": str(exc), "path": path}, status=500)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("NG_BRANCH", "abundance_thresholding"))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    logger = setup_logger(PROJECT_ROOT / "logs" / "14_ngraph_local_browser.log")
    logger.info("Starting local browser")
    logger.info("Seed: %d", SEED)
    logger.info("Host: %s Port: %d", args.host, args.port)

    app = NGraphBrowser(args.branch)
    app.logger = logger
    handler = BrowserHandler
    handler.app = app
    server = ThreadingHTTPServer((args.host, args.port), handler)
    server.app = app  # type: ignore[attr-defined]

    logger.info("Browser ready: http://%s:%d", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Browser stopped by user")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
