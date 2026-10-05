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
from collections import defaultdict, deque
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

from ngraph_discovery_common import combo_root, deep_modules_root, kg_root, knowledge_root, read_json, read_table, safe_slug  # noqa: E402


from ngraph_kg_connectivity import ConnectivityIndex, CATALOG

SEED = 42
np.random.seed(SEED)


def primary_threshold_label() -> str:
    label = os.environ.get("NG_PRIMARY_THRESHOLD_LABEL")
    if label:
        return label
    raw = os.environ.get("NG_DEEP_KNOWLEDGE_PRIMARY_THRESHOLD", os.environ.get("NG_PRIMARY_THRESHOLD", "5"))
    raw = raw.replace("prev_", "")
    return f"prev_{raw}"


PRIMARY_THRESHOLD = primary_threshold_label()
PRIMARY_METHOD = os.environ.get("NG_DEEP_KNOWLEDGE_PRIMARY_METHOD", os.environ.get("NG_PRIMARY_METHOD", "pearson"))
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
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_ready(item) for item in value.tolist()]
    return normalize_value(value)


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
        "sample": "#0ca678",
        "module": "#f08c00",
        "proxymasurement": "#f59f00",
        "proxymeasurement": "#f59f00",
        "proxyvariable": "#20c997",
        "ontologyterm": "#868e96",
        "dataset": "#adb5bd",
        "analysisrun": "#e8590c",
        "super_site": "#7048e8",
        "focus": "#d9480f",
        "unknown": "#495057",
    }
    return colors.get(str(node_type).lower(), colors["unknown"])


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
    legend_types = ["taxon", "site", "sample", "module", "proxymeasurement", "proxyvariable", "dataset", "analysisrun", "ontologyterm", "focus"]
    legend_items = []
    present_types = {str(node.get("type", "unknown")).lower() for node in nodes}
    for name in legend_types:
        if name == "focus" or name in present_types:
            legend_items.append((name, color_for_type(name)))
    for idx, (name, color) in enumerate(legend_items[:6]):
        x = legend_x + idx * 118
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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return default
        return int(value)
    except Exception:
        return default


class NGraphBrowser:
    def __init__(self, branch: str):
        self.branch = branch
        self.discovery_dir = knowledge_root(branch)
        self.deep_modules_dir = deep_modules_root(branch)
        self.kg_dir = kg_root(branch)
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
        self.kg_nodes = load_text_table(self.kg_dir / "tables" / "kg_nodes.tsv")
        self.kg_edges = load_text_table(self.kg_dir / "tables" / "kg_edges.tsv")
        self.kg_measurements = load_text_table(self.kg_dir / "tables" / "kg_measurements.tsv")
        self.kg_ontology_terms = load_text_table(self.kg_dir / "tables" / "kg_ontology_terms.tsv")
        self.kg_sites = load_text_table(self.kg_dir / "tables" / "kg_sites.tsv")
        self.kg_datasets = load_text_table(self.kg_dir / "tables" / "kg_datasets.tsv")
        self.kg_manifest = optional_json(self.kg_dir / "kg_manifest.json")
        if not self.kg_nodes.empty and "node_id" in self.kg_nodes.columns:
            self.kg_nodes["node_id"] = self.kg_nodes["node_id"].astype(str)
        if not self.kg_edges.empty:
            for col in ["edge_id", "source_id", "target_id", "edge_type"]:
                if col in self.kg_edges.columns:
                    self.kg_edges[col] = self.kg_edges[col].astype(str)
        if not self.kg_measurements.empty and "node_id" in self.kg_measurements.columns:
            self.kg_measurements["node_id"] = self.kg_measurements["node_id"].astype(str)
        self.kg_node_ids = set(self.kg_nodes["node_id"].astype(str).tolist()) if not self.kg_nodes.empty and "node_id" in self.kg_nodes.columns else set()
        self.kg_node_lookup = self.kg_nodes.set_index("node_id", drop=False) if not self.kg_nodes.empty and "node_id" in self.kg_nodes.columns else pd.DataFrame()
        self.kg_edge_lookup = self.kg_edges.set_index("edge_id", drop=False) if not self.kg_edges.empty and "edge_id" in self.kg_edges.columns else pd.DataFrame()
        self.kg_neighbors = defaultdict(list)
        if not self.kg_edges.empty and {"source_id", "target_id"}.issubset(self.kg_edges.columns):
            edge_cols = [c for c in ["edge_id", "edge_type", "source_id", "target_id", "weight", "value"] if c in self.kg_edges.columns]
            for row in self.kg_edges[edge_cols].itertuples(index=False):
                row_dict = row._asdict()
                source = str(row_dict.get("source_id", ""))
                target = str(row_dict.get("target_id", ""))
                if not source or not target:
                    continue
                self.kg_neighbors[source].append(
                    {
                        "neighbor_id": target,
                        "edge_id": row_dict.get("edge_id", ""),
                        "edge_type": row_dict.get("edge_type", ""),
                        "weight": row_dict.get("weight", row_dict.get("value", 1.0)),
                        "direction": "out",
                    }
                )
                self.kg_neighbors[target].append(
                    {
                        "neighbor_id": source,
                        "edge_id": row_dict.get("edge_id", ""),
                        "edge_type": row_dict.get("edge_type", ""),
                        "weight": row_dict.get("weight", row_dict.get("value", 1.0)),
                        "direction": "in",
                    }
                )
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
        kg_node_types = sorted(self.kg_nodes["node_type"].dropna().astype(str).unique().tolist()) if not self.kg_nodes.empty and "node_type" in self.kg_nodes.columns else []
        kg_edge_types = sorted(self.kg_edges["edge_type"].dropna().astype(str).unique().tolist()) if not self.kg_edges.empty and "edge_type" in self.kg_edges.columns else []
        kg_sites = sorted(self.kg_sites["site_id"].dropna().astype(str).unique().tolist()) if not self.kg_sites.empty and "site_id" in self.kg_sites.columns else []
        reports = []
        for name in sorted((self.discovery_dir / "reports").glob("*.md")):
            reports.append({"name": name.name, "path": str(name)})
        phase_status = {
            "link_prediction": "available_exploratory" if not self.link_predictions.empty else "missing",
            "evidence_cards": "available_unvalidated" if not self.cards.empty else "missing",
            "retrieval_index": "available_unvalidated" if self.card_matrix is not None else "missing",
            "query_engine": "available_unvalidated" if not self.query_results.empty else "missing",
            "knowledge_graph": "structural_validation_passed" if optional_json(self.kg_dir / "tables" / "kg_validation.json").get("status") == "structural_validation_passed" else ("available_unvalidated" if not self.kg_nodes.empty else "missing"),
            "browser": "serving",
        }
        return {
            "branch": self.branch,
            "analysis_label": self.analysis_label(),
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
                "kg_nodes": int(len(self.kg_nodes)),
                "kg_edges": int(len(self.kg_edges)),
                "kg_measurements": int(len(self.kg_measurements)),
            },
            "card_counts": dataframe_records(card_counts),
            "link_counts": dataframe_records(link_counts),
            "query_counts": dataframe_records(query_counts),
            "card_thresholds": card_thresholds,
            "card_methods": card_methods,
            "card_relations": card_relations,
            "kg_node_types": kg_node_types,
            "kg_edge_types": kg_edge_types,
            "kg_sites": kg_sites,
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

    def build_kg_payload(self, site: str = "", taxon: str = "", limit: int = 40) -> Dict[str, Any]:
        nodes = self.kg_nodes.copy()
        edges = self.kg_edges.copy()
        if nodes.empty or edges.empty:
            return {
                "title": "Knowledge graph unavailable",
                "svg": build_svg_graph([], [], "Knowledge graph unavailable"),
                "nodes": [],
                "edges": [],
                "measurements": [],
                "summary": [],
            }

        def site_node_id(value: str) -> str:
            value = str(value).strip()
            if not value:
                return ""
            return value if value.startswith("site:") else f"site:{value}"

        def taxon_node_id(value: str) -> str:
            value = str(value).strip()
            if not value:
                return ""
            return value if value.startswith("taxon:") else f"taxon:{value}"

        focus_site = site_node_id(site)
        focus_taxon = taxon_node_id(taxon)
        if not focus_site and not focus_taxon:
            first_site = nodes.loc[nodes["node_type"].astype(str) == "Site", "node_id"].dropna().astype(str)
            if len(first_site) > 0:
                focus_site = str(first_site.iloc[0])

        selected_ids = set()
        if focus_site:
            selected_ids.add(focus_site)
        if focus_taxon:
            selected_ids.add(focus_taxon)

        def add_edges(mask: pd.Series, edge_limit: int = limit) -> pd.DataFrame:
            frame = edges[mask].copy()
            if frame.empty:
                return frame
            sort_cols = [c for c in ["weight", "value", "n_observations"] if c in frame.columns]
            if sort_cols:
                frame = frame.sort_values(sort_cols, ascending=False)
            if edge_limit > 0:
                frame = frame.head(edge_limit)
            selected_ids.update(frame["source_id"].dropna().astype(str).tolist())
            selected_ids.update(frame["target_id"].dropna().astype(str).tolist())
            return frame

        edge_chunks = []
        if focus_site:
            edge_chunks.append(add_edges((edges["edge_type"] == "site_has_sample") & (edges["source_id"].astype(str) == focus_site)))
            sample_ids = edges.loc[(edges["edge_type"] == "site_has_sample") & (edges["source_id"].astype(str) == focus_site), "target_id"].dropna().astype(str).tolist()
            if sample_ids:
                selected_ids.update(sample_ids)
                edge_chunks.append(add_edges((edges["edge_type"] == "sample_observed_taxon") & (edges["source_id"].astype(str).isin(sample_ids))))
                edge_chunks.append(add_edges((edges["edge_type"] == "sample_has_measurement") & (edges["source_id"].astype(str).isin(sample_ids))))
        if focus_taxon:
            edge_chunks.append(add_edges((edges["edge_type"] == "sample_observed_taxon") & (edges["target_id"].astype(str) == focus_taxon)))
            edge_chunks.append(add_edges((edges["edge_type"] == "taxon_member_of_module") & (edges["source_id"].astype(str) == focus_taxon)))
            sample_ids = edges.loc[(edges["edge_type"] == "sample_observed_taxon") & (edges["target_id"].astype(str) == focus_taxon), "source_id"].dropna().astype(str).tolist()
            if sample_ids:
                selected_ids.update(sample_ids)
                edge_chunks.append(add_edges((edges["edge_type"] == "sample_has_measurement") & (edges["source_id"].astype(str).isin(sample_ids))))
        if selected_ids:
            edge_chunks.append(add_edges(edges["source_id"].astype(str).isin(selected_ids) & edges["target_id"].astype(str).isin(selected_ids), edge_limit=2 * limit))

        chunks = [chunk for chunk in edge_chunks if chunk is not None and not chunk.empty]
        selected_edges = pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        if not selected_edges.empty:
            selected_ids.update(selected_edges["source_id"].dropna().astype(str).tolist())
            selected_ids.update(selected_edges["target_id"].dropna().astype(str).tolist())

        selected_nodes = nodes[nodes["node_id"].astype(str).isin(selected_ids)].copy()
        if selected_nodes.empty:
            selected_nodes = nodes[nodes["node_type"].astype(str).isin(["Site", "Sample"])].head(limit).copy()
            selected_ids.update(selected_nodes["node_id"].astype(str).tolist())
            selected_edges = edges[edges["source_id"].astype(str).isin(selected_ids) & edges["target_id"].astype(str).isin(selected_ids)].head(2 * limit).copy()

        graph_nodes = []
        type_sizes = {
            "site": 12.0,
            "sample": 8.5,
            "taxon": 7.5,
            "module": 10.0,
            "proxymasurement": 6.5,
            "proxymeasurement": 6.5,
            "proxyvariable": 6.5,
            "dataset": 6.0,
            "analysisrun": 6.0,
            "ontologyterm": 6.0,
        }
        focus_ids = {focus_site, focus_taxon} - {""}
        for _, row in selected_nodes.iterrows():
            node_id = str(row.get("node_id", ""))
            node_type = str(row.get("node_type", "unknown")).lower()
            graph_nodes.append(
                {
                    "id": node_id,
                    "label": str(row.get("label", node_id)),
                    "type": node_type,
                    "size": type_sizes.get(node_type, 7.0),
                    "color": color_for_type(node_type),
                    "highlight": node_id in focus_ids,
                }
            )

        graph_edges = []
        for _, row in selected_edges.iterrows():
            source = str(row.get("source_id", ""))
            target = str(row.get("target_id", ""))
            if not source or not target:
                continue
            weight = row.get("weight", row.get("value", 0.5))
            try:
                weight = float(weight)
            except Exception:
                weight = 0.5
            graph_edges.append({"source": source, "target": target, "weight": max(0.05, min(1.0, weight))})

        if focus_site and not focus_taxon:
            title = f"Knowledge graph around site {focus_site.replace('site:', '')}"
        elif focus_taxon and not focus_site:
            title = f"Knowledge graph around taxon {focus_taxon.replace('taxon:', '')}"
        else:
            title = "Knowledge graph overview"

        svg = build_svg_graph(graph_nodes, graph_edges, title)
        kg_measurements = self.kg_measurements.copy()
        if "site_id" in kg_measurements.columns and focus_site:
            kg_measurements = kg_measurements[kg_measurements["site_id"].astype(str) == focus_site.replace("site:", "")]
        if "sample_id" in kg_measurements.columns and focus_taxon and not focus_site:
            sample_ids = selected_edges.loc[selected_edges["edge_type"] == "sample_observed_taxon", "source_id"].dropna().astype(str).unique().tolist()
            if sample_ids:
                kg_measurements = kg_measurements[kg_measurements["sample_id"].astype(str).isin(sample_ids)]

        return {
            "title": title,
            "focus_site": focus_site,
            "focus_taxon": focus_taxon,
            "svg": svg,
            "nodes": dataframe_records(selected_nodes, limit=limit * 4),
            "edges": dataframe_records(selected_edges, limit=limit * 4),
            "measurements": dataframe_records(kg_measurements, limit=limit * 4),
            "summary": dataframe_records(
                pd.DataFrame(
                    [
                        ["KG nodes", len(self.kg_nodes)],
                        ["KG edges", len(self.kg_edges)],
                        ["KG measurements", len(self.kg_measurements)],
                        ["Selected nodes", len(selected_nodes)],
                        ["Selected edges", len(selected_edges)],
                        ["Selected measurements", len(kg_measurements)],
                    ],
                    columns=["label", "value"],
                ),
                limit=20,
            ),
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
            "analysis_label": self.analysis_label(),
            "project_root": str(PROJECT_ROOT),
            "discovery_dir": str(self.discovery_dir),
            "kg_dir": str(self.kg_dir),
            "cards": int(len(self.cards)),
            "link_predictions": int(len(self.link_predictions)),
            "query_results": int(len(self.query_results)),
            "kg_nodes": int(len(self.kg_nodes)),
            "kg_edges": int(len(self.kg_edges)),
            "kg_measurements": int(len(self.kg_measurements)),
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

    def resolve_kg_node_id(self, value: str) -> str:
        value = str(value or "").strip()
        if not value:
            return ""
        if value in self.kg_node_ids:
            return value
        if not self.kg_nodes.empty and "label" in self.kg_nodes.columns:
            label_matches = self.kg_nodes[self.kg_nodes["label"].astype(str).str.lower() == value.lower()]
            if len(label_matches) == 1:
                return str(label_matches.iloc[0]["node_id"])
            contains_matches = self.kg_nodes[self.kg_nodes["label"].astype(str).str.contains(value, case=False, na=False, regex=False)]
            if len(contains_matches) == 1:
                return str(contains_matches.iloc[0]["node_id"])
        return value if value.startswith(("site:", "sample:", "taxon:", "module:", "measurement:", "variable:", "dataset:", "analysis:", "ontology:")) else value

    def kg_schema(self) -> Dict[str, Any]:
        if self.kg_nodes.empty:
            return {
                "node_types": [],
                "edge_types": [],
                "metagraph": [],
                "node_counts": [],
                "edge_counts": [],
                "sites": [],
                "datasets": [],
            }
        node_counts = self.kg_nodes.groupby("node_type").size().sort_values(ascending=False).reset_index(name="count") if "node_type" in self.kg_nodes.columns else pd.DataFrame()
        edge_counts = self.kg_edges.groupby("edge_type").size().sort_values(ascending=False).reset_index(name="count") if not self.kg_edges.empty and "edge_type" in self.kg_edges.columns else pd.DataFrame()
        metagraph = pd.DataFrame()
        if not self.kg_edges.empty and {"source_node_type", "edge_type", "target_node_type"}.issubset(self.kg_edges.columns):
            metagraph = (
                self.kg_edges.groupby(["source_node_type", "edge_type", "target_node_type"])
                .size()
                .sort_values(ascending=False)
                .reset_index(name="count")
            )
        return {
            "node_types": dataframe_records(node_counts, limit=len(node_counts)) if not node_counts.empty else [],
            "edge_types": dataframe_records(edge_counts, limit=len(edge_counts)) if not edge_counts.empty else [],
            "metagraph": dataframe_records(metagraph, limit=min(len(metagraph), 250)) if not metagraph.empty else [],
            "sites": dataframe_records(self.kg_sites, limit=len(self.kg_sites)) if not self.kg_sites.empty else [],
            "datasets": dataframe_records(self.kg_datasets, limit=len(self.kg_datasets)) if not self.kg_datasets.empty else [],
            "manifest": self.kg_manifest,
        }

    def kg_search_nodes(self, query: str = "", node_type: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        frame = self.kg_nodes.copy()
        if frame.empty:
            return {"rows": [], "total": 0, "query": query, "node_type": node_type, "offset": offset, "limit": limit}
        if node_type and "node_type" in frame.columns:
            frame = frame[frame["node_type"].astype(str).str.lower() == node_type.lower()]
        q = str(query or "").strip()
        if q:
            text_cols = [c for c in ["node_id", "label", "node_type", "site_id", "taxon", "module_id", "variable", "ontology_prefix", "ontology_scope", "source_table"] if c in frame.columns]
            blob = frame[text_cols].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
            tokens = [tok for tok in q.lower().split() if tok]
            score = pd.Series(np.zeros(len(frame), dtype=float), index=frame.index)
            if "node_id" in frame.columns:
                score = score + (frame["node_id"].astype(str).str.lower() == q.lower()).astype(float) * 12.0
                score = score + frame["node_id"].astype(str).str.lower().str.contains(q.lower(), regex=False, na=False).astype(float) * 6.0
            if "label" in frame.columns:
                score = score + (frame["label"].astype(str).str.lower() == q.lower()).astype(float) * 10.0
                score = score + frame["label"].astype(str).str.lower().str.contains(q.lower(), regex=False, na=False).astype(float) * 5.0
            for token in tokens:
                score = score + blob.str.contains(token, regex=False, na=False).astype(float)
            frame = frame.assign(search_score=score, search_blob=blob)
            frame = frame[frame["search_score"] > 0].sort_values(["search_score", "label", "node_id"], ascending=[False, True, True])
        else:
            sort_cols = [c for c in ["node_type", "label", "node_id"] if c in frame.columns]
            if sort_cols:
                frame = frame.sort_values(sort_cols, ascending=True)
        total = len(frame)
        if offset > 0:
            frame = frame.iloc[offset:]
        if limit > 0:
            frame = frame.head(limit)
        cols = [c for c in ["node_id", "node_type", "label", "search_score", "site_id", "core", "taxon", "module_id", "variable", "ontology_prefix", "source_table", "source_file", "branch"] if c in frame.columns]
        return {
            "rows": dataframe_records(frame[cols], limit=len(frame)) if cols else dataframe_records(frame, limit=len(frame)),
            "total": int(total),
            "query": q,
            "node_type": node_type,
            "offset": offset,
            "limit": limit,
        }

    def kg_node_detail(self, node_id: str) -> Dict[str, Any]:
        node_id = self.resolve_kg_node_id(node_id)
        if not node_id or self.kg_nodes.empty:
            return {"node": None, "incident_edges": [], "neighbors": [], "measurements": [], "node_id": node_id, "status": "missing"}
        node = self.kg_nodes[self.kg_nodes["node_id"].astype(str) == node_id]
        if node.empty:
            return {"node": None, "incident_edges": [], "neighbors": [], "measurements": [], "node_id": node_id, "status": "missing"}
        node_row = node.iloc[[0]].copy()
        incident = self.kg_edges[(self.kg_edges["source_id"].astype(str) == node_id) | (self.kg_edges["target_id"].astype(str) == node_id)].copy()
        incident = incident.sort_values([c for c in ["edge_type", "weight", "value"] if c in incident.columns], ascending=[True, False, False] if any(c in incident.columns for c in ["weight", "value"]) else True)
        neighbor_ids = []
        if not incident.empty:
            neighbor_ids = sorted(set(incident["source_id"].astype(str).tolist() + incident["target_id"].astype(str).tolist()) - {node_id})
        neighbors = self.kg_nodes[self.kg_nodes["node_id"].astype(str).isin(neighbor_ids)].copy() if neighbor_ids else pd.DataFrame()
        measurements = self.kg_measurements[self.kg_measurements["node_id"].astype(str) == node_id].copy() if not self.kg_measurements.empty and "node_id" in self.kg_measurements.columns else pd.DataFrame()
        return {
            "status": "ok",
            "node_id": node_id,
            "node": dataframe_records(node_row, limit=1)[0],
            "incident_edges": dataframe_records(incident, limit=120),
            "neighbors": dataframe_records(neighbors, limit=60),
            "measurements": dataframe_records(measurements, limit=120),
        }

    def kg_elements_for_nodes(self, node_ids: Iterable[str], edge_ids: Iterable[str]) -> Dict[str, Any]:
        node_ids = [str(x) for x in node_ids if str(x)]
        edge_ids = [str(x) for x in edge_ids if str(x)]
        nodes = self.kg_nodes[self.kg_nodes["node_id"].astype(str).isin(node_ids)].copy() if node_ids else pd.DataFrame()
        edges = self.kg_edges[self.kg_edges["edge_id"].astype(str).isin(edge_ids)].copy() if edge_ids else pd.DataFrame()
        node_elements = []
        for _, row in nodes.iterrows():
            node_type = str(row.get("node_type", "unknown")).lower()
            node_id = str(row.get("node_id", ""))
            node_elements.append(
                {
                    "data": {
                        "id": node_id,
                        "label": str(row.get("label", node_id)),
                        "type": node_type,
                        "node_type": str(row.get("node_type", "unknown")),
                        "site_id": row.get("site_id", ""),
                        "core": row.get("core", ""),
                        "taxon": row.get("taxon", ""),
                        "module_id": row.get("module_id", ""),
                        "variable": row.get("variable", ""),
                        "ontology_prefix": row.get("ontology_prefix", ""),
                        "source_table": row.get("source_table", ""),
                        "source_file": row.get("source_file", ""),
                    },
                    "classes": node_type,
                }
            )
        edge_elements = []
        for _, row in edges.iterrows():
            edge_elements.append(
                {
                    "data": {
                        "id": str(row.get("edge_id", "")),
                        "source": str(row.get("source_id", "")),
                        "target": str(row.get("target_id", "")),
                        "label": str(row.get("edge_type", "")),
                        "edge_type": str(row.get("edge_type", "")),
                        "weight": float(row.get("weight", row.get("value", 1.0)) or 1.0),
                        "source_table": row.get("source_table", ""),
                        "source_file": row.get("source_file", ""),
                        "analysis": row.get("analysis", ""),
                    },
                    "classes": str(row.get("edge_type", "")),
                }
            )
        return {"nodes": node_elements, "edges": edge_elements}

    def kg_neighborhood(self, node_id: str = "", depth: int = 1, edge_type: str = "", node_type: str = "", limit: int = 150) -> Dict[str, Any]:
        focus = self.resolve_kg_node_id(node_id)
        if not focus and not self.kg_nodes.empty:
            focus = str(self.kg_nodes.iloc[0]["node_id"])
        if not focus:
            return {"status": "missing", "focus": "", "nodes": [], "edges": [], "elements": [], "summary": []}
        allowed_edge_types = {item.strip().lower() for item in str(edge_type or "").split(",") if item.strip()}
        visited = {focus}
        frontier = {focus}
        edge_ids = []
        for _ in range(max(1, depth)):
            next_frontier = set()
            for current in frontier:
                for item in self.kg_neighbors.get(current, []):
                    if allowed_edge_types and str(item.get("edge_type", "")).lower() not in allowed_edge_types:
                        continue
                    neighbor = str(item.get("neighbor_id", ""))
                    edge_id = str(item.get("edge_id", ""))
                    if neighbor:
                        next_frontier.add(neighbor)
                    if edge_id:
                        edge_ids.append(edge_id)
                    if len(edge_ids) >= limit * 5:
                        break
                if len(edge_ids) >= limit * 5:
                    break
            frontier = next_frontier - visited
            visited.update(next_frontier)
            if len(visited) >= limit:
                break
        if node_type:
            node_frame = self.kg_nodes[self.kg_nodes["node_id"].astype(str).isin(visited) & (self.kg_nodes["node_type"].astype(str).str.lower() == node_type.lower())].copy()
            visited = set(node_frame["node_id"].astype(str).tolist()) | {focus}
        else:
            node_frame = self.kg_nodes[self.kg_nodes["node_id"].astype(str).isin(visited)].copy()
        node_frame = node_frame.head(max(1, min(limit, 1000)))
        retained_ids = set(node_frame["node_id"].astype(str))
        edge_frame = self.kg_edges[self.kg_edges["edge_id"].astype(str).isin(set(edge_ids)) & self.kg_edges["source_id"].astype(str).isin(retained_ids) & self.kg_edges["target_id"].astype(str).isin(retained_ids)].copy()
        if not edge_frame.empty and limit > 0:
            sort_cols = [c for c in ["weight", "value"] if c in edge_frame.columns]
            if sort_cols:
                edge_frame = edge_frame.sort_values(sort_cols, ascending=False)
            edge_frame = edge_frame.head(limit * 5)
        elements = self.kg_elements_for_nodes(node_frame["node_id"].astype(str).tolist(), edge_frame["edge_id"].astype(str).tolist())
        summary = [
            {"label": "Focus", "value": focus},
            {"label": "Depth", "value": depth},
            {"label": "Nodes", "value": len(node_frame)},
            {"label": "Edges", "value": len(edge_frame)},
            {"label": "Filtered edge types", "value": ", ".join(sorted(allowed_edge_types)) if allowed_edge_types else "all"},
        ]
        return {
            "status": "ok",
            "focus": focus,
            "depth": depth,
            "node_type": node_type,
            "edge_type": edge_type,
            "nodes": dataframe_records(node_frame, limit=limit * 2),
            "edges": dataframe_records(edge_frame, limit=limit * 4),
            "elements": elements,
            "summary": summary,
            "truncated": len(node_frame) >= limit or len(edge_frame) >= limit * 5,
        }

    def analysis_label(self):
        manifest = optional_json(PROJECT_ROOT / "results" / "ngraph" / self.branch / "run_manifest.json")
        mode = manifest.get("settings", {}).get("NG_ABUNDANCE_MODE", "tad_only")
        if mode in {"hybrid_aggregated_tad_then_read", "hybrid_tad_then_read"}:
            return "Permissive mixed-abundance sensitivity analysis: TAD where positive, read fallback otherwise"
        return "TAD-only abundance analysis"

    def kg_connectivity(self, source, target, metapath, limit=20):
        if not hasattr(self, "connectivity_index"):
            self.connectivity_index = ConnectivityIndex(self.kg_nodes.to_dict("records"), self.kg_edges.to_dict("records"))
        return self.connectivity_index.search(self.resolve_kg_node_id(source), self.resolve_kg_node_id(target), metapath, limit)

    def kg_path(self, source: str, target: str, max_depth: int = 4, edge_type: str = "") -> Dict[str, Any]:
        source_id = self.resolve_kg_node_id(source)
        target_id = self.resolve_kg_node_id(target)
        if not source_id or not target_id:
            return {"status": "missing", "source": source_id, "target": target_id, "path": [], "nodes": [], "edges": [], "elements": []}
        allowed_edge_types = {item.strip().lower() for item in str(edge_type or "").split(",") if item.strip()}
        queue = deque([(source_id, [source_id], [])])
        visited = {source_id}
        found_nodes = []
        found_edge_ids = []
        while queue:
            current, path_nodes, path_edges = queue.popleft()
            if current == target_id:
                found_nodes = path_nodes
                found_edge_ids = path_edges
                break
            if len(path_nodes) - 1 >= max_depth:
                continue
            for item in self.kg_neighbors.get(current, []):
                if allowed_edge_types and str(item.get("edge_type", "")).lower() not in allowed_edge_types:
                    continue
                neighbor = str(item.get("neighbor_id", ""))
                edge_id = str(item.get("edge_id", ""))
                if not neighbor or neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, path_nodes + [neighbor], path_edges + ([edge_id] if edge_id else [])))
        if not found_nodes:
            return {
                "status": "no_path",
                "source": source_id,
                "target": target_id,
                "max_depth": max_depth,
                "path": [],
                "nodes": [],
                "edges": [],
                "elements": [],
                "summary": [{"label": "Status", "value": "No path found"}],
            }
        nodes = self.kg_nodes[self.kg_nodes["node_id"].astype(str).isin(found_nodes)].copy()
        edges = self.kg_edges[self.kg_edges["edge_id"].astype(str).isin(set(found_edge_ids))].copy()
        elements = self.kg_elements_for_nodes(nodes["node_id"].astype(str).tolist(), edges["edge_id"].astype(str).tolist())
        summary = [
            {"label": "Source", "value": source_id},
            {"label": "Target", "value": target_id},
            {"label": "Depth", "value": max_depth},
            {"label": "Nodes", "value": len(nodes)},
            {"label": "Edges", "value": len(edges)},
        ]
        return {
            "status": "ok",
            "source": source_id,
            "target": target_id,
            "max_depth": max_depth,
            "path": [{"node_id": node_id} for node_id in found_nodes],
            "nodes": dataframe_records(nodes, limit=len(nodes)),
            "edges": dataframe_records(edges, limit=len(edges)),
            "elements": elements,
            "summary": summary,
        }

    def kg_downloads(self) -> Dict[str, Any]:
        files = []
        for rel in [
            "kg_manifest.json",
            "reports/KG_SCHEMA_AND_IMPORT_REPORT.md",
            "tables/kg_substrate_validation.json",
            "tables/kg_proxy_source_observations.tsv",
            "tables/kg_import_coverage.tsv",
            "tables/kg_proxy_matching_coverage.tsv",
            "tables/kg_variable_units.tsv",
            "tables/kg_observations.tsv",
            "tables/kg_unmatched_proxy_observations.tsv",
            "tables/kg_validation.json",
            "tables/mvp_validation_and_demo.json",
            "tables/kg_nodes.tsv",
            "tables/kg_edges.tsv",
            "tables/kg_measurements.tsv",
            "tables/kg_ontology_terms.tsv",
            "tables/kg_sites.tsv",
            "tables/kg_datasets.tsv",
        ]:
            path = self.kg_dir / rel
            files.append({"name": rel, "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0, "path": str(path)})
        return {
            "branch": self.branch,
            "analysis_label": self.analysis_label(),
            "kg_dir": str(self.kg_dir),
            "files": files,
            "manifest": self.kg_manifest,
        }


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NGraph Local Browser</title>
  <style>
    :root {
      --bg: #f6f4ee;
      --panel: #ffffff;
      --panel-2: #f1ede5;
      --line: #d8d0c2;
      --text: #1d2320;
      --muted: #5f6b64;
      --accent: #2f6b4f;
      --accent-2: #8b5e3c;
      --warning: #9a6b2f;
      --danger: #b24b4b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: linear-gradient(180deg, #fbfaf6 0%, #f6f4ee 48%, #ece6dc 100%);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 20;
      backdrop-filter: blur(16px);
      background: linear-gradient(180deg, rgba(30, 70, 52, 0.97), rgba(43, 88, 67, 0.96));
      border-bottom: 1px solid rgba(18, 44, 32, 0.28);
      padding: 18px 24px;
      color: #f8f6f1;
      box-shadow: 0 10px 26px rgba(18, 44, 32, 0.14);
    }
    header a { color: #f8f6f1; }
    header .muted { color: rgba(248, 246, 241, 0.78); }
    header .title h1, header .title .sub { color: #f8f6f1; }
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
      background: #ffffff;
      border: 1px solid rgba(93, 79, 61, 0.16);
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
      border: 1px solid rgba(93, 79, 61, 0.14);
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.92);
      box-shadow: 0 20px 45px rgba(64, 51, 36, 0.08);
      overflow: hidden;
    }
    .section-head {
      padding: 18px 20px 12px;
      border-bottom: 1px solid rgba(93, 79, 61, 0.12);
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
      background: #fffdf9;
      border: 1px solid rgba(93, 79, 61, 0.14);
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
      background: #fffdf9;
      border: 1px solid rgba(93, 79, 61, 0.12);
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
      border: 1px solid rgba(93, 79, 61, 0.18);
      background: #ffffff;
      color: var(--text);
      padding: 10px 12px;
    }
    input, select, textarea { min-width: 180px; }
    textarea { width: 100%; min-height: 100px; resize: vertical; }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, rgba(47, 107, 79, 0.96), rgba(139, 94, 60, 0.92));
      color: #fffdf9;
      font-weight: 700;
      border: none;
      padding: 10px 14px;
    }
    button.secondary {
      background: #f6f2ea;
      color: var(--text);
      border: 1px solid rgba(93, 79, 61, 0.18);
    }
    .muted { color: var(--muted); }
    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 0; }
    .chip {
      border-radius: 999px;
      padding: 6px 10px;
      background: #f8f5ee;
      border: 1px solid rgba(93, 79, 61, 0.16);
      color: var(--text);
      font-size: 12px;
    }
    .table-wrap { overflow-x: auto; border-radius: 14px; border: 1px solid rgba(93, 79, 61, 0.12); background: #fffdf9; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    thead th {
      position: sticky; top: 0;
      background: #f1ede5;
      color: #2e2a25;
      text-align: left;
      padding: 10px 12px;
      border-bottom: 1px solid rgba(93, 79, 61, 0.16);
      white-space: nowrap;
    }
    tbody td {
      padding: 9px 12px;
      border-bottom: 1px solid rgba(93, 79, 61, 0.08);
      vertical-align: top;
    }
    tbody tr:hover { background: rgba(47, 107, 79, 0.05); }
    .svg-box {
      width: 100%;
      min-height: 320px;
      overflow: auto;
      border-radius: 16px;
      border: 1px solid rgba(93, 79, 61, 0.12);
      background: linear-gradient(180deg, #fffdf9, #f8f5ee);
    }
    .svg-box svg { display: block; width: 100%; height: auto; }
    .report-box {
      width: 100%;
      min-height: 260px;
      max-height: 520px;
      overflow: auto;
      white-space: pre-wrap;
      background: #fffdf9;
      border: 1px solid rgba(93, 79, 61, 0.12);
      border-radius: 16px;
      padding: 14px;
      color: var(--text);
    }
    .status-banner {
      margin: 14px 24px 0;
      max-width: 1500px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(93, 79, 61, 0.18);
      background: rgba(255, 253, 249, 0.95);
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }
    .status-banner.ok {
      border-color: rgba(47, 107, 79, 0.35);
      color: #2f6b4f;
    }
    .status-banner.warning {
      border-color: rgba(154, 107, 47, 0.38);
      color: #9a6b2f;
    }
    .status-banner.error {
      border-color: rgba(178, 75, 75, 0.4);
      color: #b24b4b;
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
        <div class="muted">Deep knowledge discovery</div>
        <div id="analysis-policy" class="muted"></div>
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
      <a href="/kg">Knowledge Graph</a>
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

    <section id="knowledge-graph">
      <div class="section-head">
        <h2>Knowledge Graph</h2>
        <p>Browse the site, sample, taxon, module, proxy, and ontology substrate that will anchor the learnable KG.</p>
      </div>
      <div class="section-body">
        <div class="controls">
          <select id="kg-site"><option value="">All sites</option></select>
          <input id="kg-taxon" type="text" placeholder="Focus taxon" />
          <button onclick="loadKG()">Refresh KG</button>
        </div>
        <div class="stats" id="kg-stats"></div>
        <div class="grid-2">
          <div class="svg-box" id="kg-box"></div>
          <div class="table-wrap" id="kg-summary-table"></div>
        </div>
        <div class="grid-2" style="margin-top: 16px;">
          <div class="panel">
            <h3>Selected Nodes</h3>
            <div class="table-wrap" id="kg-nodes-table"></div>
          </div>
          <div class="panel">
            <h3>Selected Edges</h3>
            <div class="table-wrap" id="kg-edges-table"></div>
          </div>
        </div>
        <div class="panel" style="margin-top: 16px;">
          <h3>Measurements</h3>
          <div class="table-wrap" id="kg-measurements-table"></div>
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
      kgSites: [],
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
      state.kgSites = summary.kg_sites || [];
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
      document.getElementById("analysis-policy").textContent = summary.analysis_label || "";
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
      populateSelect("kg-site", state.kgSites || [], true, "All sites");
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
      document.getElementById("kg-site").value = "";
      document.getElementById("kg-taxon").value = "";
      document.getElementById("query-provider").value = state.llmProvider;

      const loaders = [
        safeLoad("Cards panel", loadCards),
        safeLoad("Links panel", loadLinks),
        safeLoad("Super graph panel", loadSuperGraph),
        safeLoad("Modules panel", loadModules),
        safeLoad("Knowledge graph panel", loadKG),
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
        threshold: document.getElementById("link-threshold").value || PRIMARY_THRESHOLD,
        method: document.getElementById("link-method").value || PRIMARY_METHOD,
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
        threshold: document.getElementById("super-threshold").value || PRIMARY_THRESHOLD,
        method: document.getElementById("super-method").value || PRIMARY_METHOD,
      });
      const data = await fetchJson(`/api/supergraph?${params.toString()}`);
      document.getElementById("supergraph-box").innerHTML = data.svg || "";
      document.getElementById("supergraph-table").innerHTML = tableHtml(data.rows || []);
    }

    async function loadModules() {
      const params = new URLSearchParams({
        threshold: document.getElementById("module-threshold").value || PRIMARY_THRESHOLD,
        method: document.getElementById("module-method").value || PRIMARY_METHOD,
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

    async function loadKG() {
      const params = new URLSearchParams({
        site: document.getElementById("kg-site").value || "",
        taxon: document.getElementById("kg-taxon").value || "",
        limit: "60",
      });
      const data = await fetchJson(`/api/kg?${params.toString()}`);
      const summaryRows = data.summary || [];
      document.getElementById("kg-stats").innerHTML = summaryRows.length
        ? summaryRows.map((row) => `<div class="stat"><div class="label">${escapeHtml(row.label)}</div><div class="value">${escapeHtml(row.value)}</div></div>`).join("")
        : "";
      document.getElementById("kg-box").innerHTML = data.svg || "";
      document.getElementById("kg-summary-table").innerHTML = tableHtml(summaryRows);
      document.getElementById("kg-nodes-table").innerHTML = tableHtml(data.nodes || []);
      document.getElementById("kg-edges-table").innerHTML = tableHtml(data.edges || []);
      document.getElementById("kg-measurements-table").innerHTML = tableHtml(data.measurements || []);
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
        threshold: document.getElementById("link-threshold").value || PRIMARY_THRESHOLD,
        method: document.getElementById("link-method").value || PRIMARY_METHOD,
        focus: document.getElementById("link-focus").value || "",
      });
      const data = await fetchJson(`/api/graph?${params.toString()}`);
      document.getElementById("graph-box").innerHTML = data.svg || "";
    }

    bindEvent("module-kind", "change", loadModules);
    bindEvent("module-id", "change", loadModules);
    bindEvent("super-threshold", "change", loadSuperGraph);
    bindEvent("super-method", "change", loadSuperGraph);
    bindEvent("kg-site", "change", loadKG);
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

HTML_PAGE = HTML_PAGE.replace('const PRIMARY_THRESHOLD = "prev_5";', f'const PRIMARY_THRESHOLD = "{PRIMARY_THRESHOLD}";')
HTML_PAGE = HTML_PAGE.replace('const PRIMARY_METHOD = "pearson";', f'const PRIMARY_METHOD = "{PRIMARY_METHOD}";')
HTML_PAGE = HTML_PAGE.replace('value || "prev_5"', 'value || PRIMARY_THRESHOLD')
HTML_PAGE = HTML_PAGE.replace('value || "pearson"', 'value || PRIMARY_METHOD')


def render_kg_page(app: NGraphBrowser, page: str, params: Dict[str, List[str]]) -> str:
    schema = app.kg_schema()
    downloads = app.kg_downloads()
    initial = {
        "query": params.get("q", [""])[0],
        "node_id": params.get("id", [""])[0],
        "source": params.get("source", [""])[0],
        "target": params.get("target", [""])[0],
        "site": params.get("site", [""])[0],
        "taxon": params.get("taxon", [""])[0],
        "node_type": params.get("node_type", [""])[0],
        "edge_type": params.get("edge_type", [""])[0],
        "depth": safe_int(params.get("depth", ["1"])[0], 1),
        "max_depth": safe_int(params.get("max_depth", ["4"])[0], 4),
    }
    page_data = json.dumps(
        {
            "branch": app.branch,
            "primary_threshold": PRIMARY_THRESHOLD,
            "primary_method": PRIMARY_METHOD,
            "schema": schema,
            "downloads": downloads,
            "initial": initial,
        },
        default=normalize_value,
    )

    nav = {
        "/kg": "Overview",
        "/kg/search": "Search",
        "/kg/explore": "Explore",
        "/kg/paths": "Paths",
        "/kg/node": "Node",
        "/kg/downloads": "Downloads",
    }
    active_label = nav.get(page, "Overview")
    nav_html = "".join(
        f"<a class='{'active' if route == page else ''}' href='{route}'>{label}</a>"
        for route, label in nav.items()
    )

    base_css = """
    :root {
      --bg: #f6f4ee;
      --panel: #ffffff;
      --panel-2: #f1ede5;
      --line: #d8d0c2;
      --text: #1d2320;
      --muted: #5f6b64;
      --accent: #2f6b4f;
      --accent-2: #8b5e3c;
      --accent-3: #4d7f63;
      --danger: #b24b4b;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: linear-gradient(180deg, #fbfaf6 0%, #f6f4ee 48%, #ece6dc 100%); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    a { color: inherit; }
    header { position: sticky; top: 0; z-index: 20; backdrop-filter: blur(16px); background: linear-gradient(180deg, rgba(30, 70, 52, 0.97), rgba(43, 88, 67, 0.96)); border-bottom: 1px solid rgba(18, 44, 32, 0.28); padding: 16px 24px; color: #f8f6f1; box-shadow: 0 10px 26px rgba(18, 44, 32, 0.14); }
    header a { color: #f8f6f1; }
    header .muted { color: rgba(248, 246, 241, 0.78); }
    header .title h1, header .title .sub { color: #f8f6f1; }
    .head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
    .head h1 { margin: 0; font-size: 24px; letter-spacing: 0.01em; }
    .head p { margin: 6px 0 0; color: var(--muted); font-size: 13px; }
    .nav { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .nav a { text-decoration: none; padding: 8px 12px; border-radius: 999px; border: 1px solid rgba(93, 79, 61, 0.16); background: #ffffff; color: var(--text); font-size: 13px; box-shadow: 0 1px 0 rgba(93, 79, 61, 0.04); }
    .nav a.active { background: linear-gradient(135deg, rgba(47, 107, 79, 0.12), rgba(139, 94, 60, 0.12)); border-color: rgba(47, 107, 79, 0.3); }
    main { max-width: 1600px; margin: 0 auto; padding: 22px 24px 40px; }
    main.kg-main { max-width: none; width: 100%; margin: 0; padding: 22px 24px 40px; }
    .hero { display: grid; grid-template-columns: 1.25fr 0.75fr; gap: 18px; margin-bottom: 18px; }
    .card, .panel { background: var(--panel); border: 1px solid rgba(93, 79, 61, 0.14); border-radius: 18px; box-shadow: 0 16px 38px rgba(64, 51, 36, 0.08); }
    .card { padding: 18px; }
    .panel { padding: 16px; }
    .title-2 { margin: 0 0 10px; font-size: 18px; }
    .muted { color: var(--muted); }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
    .stat { padding: 14px; border-radius: 16px; border: 1px solid rgba(93, 79, 61, 0.14); background: #fffdf9; }
    .stat .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted); }
    .stat .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
    .grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 14px; }
    input, select, button, textarea { font: inherit; border-radius: 12px; border: 1px solid rgba(93, 79, 61, 0.18); background: #ffffff; color: var(--text); padding: 10px 12px; }
    input, select, textarea { min-width: 180px; }
    textarea { width: 100%; min-height: 100px; resize: vertical; }
    button { cursor: pointer; background: linear-gradient(135deg, rgba(47, 107, 79, 0.96), rgba(139, 94, 60, 0.92)); color: #fffdf9; font-weight: 700; border: none; }
    button.secondary { background: #f6f2ea; color: var(--text); border: 1px solid rgba(93, 79, 61, 0.18); }
    .table-wrap { overflow: auto; border-radius: 14px; border: 1px solid rgba(93, 79, 61, 0.12); background: #fffdf9; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { padding: 9px 11px; border-bottom: 1px solid rgba(93, 79, 61, 0.08); vertical-align: top; }
    th { position: sticky; top: 0; background: #f1ede5; text-align: left; white-space: nowrap; color: #2e2a25; }
    tr:hover td { background: rgba(47, 107, 79, 0.05); }
    .chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 6px 10px; border: 1px solid rgba(93, 79, 61, 0.16); background: #f8f5ee; color: var(--text); font-size: 12px; }
    .graph { min-height: 640px; border-radius: 16px; border: 1px solid rgba(93, 79, 61, 0.12); overflow: hidden; background: linear-gradient(180deg, #fffdf9, #f8f5ee); }
    .graph.small { min-height: 420px; }
    .kg-explore-layout { display: grid; grid-template-columns: minmax(0, 1fr) minmax(520px, 0.95fr); gap: 20px; align-items: stretch; width: 100%; }
    .kg-explore-main { min-width: 0; display: flex; flex-direction: column; }
    .kg-explore-sidebar { min-width: 0; display: flex; flex-direction: column; gap: 14px; transition: width 180ms ease, min-width 180ms ease, opacity 180ms ease, transform 180ms ease; }
    .kg-explore-graph { flex: 1; min-height: 72vh; height: clamp(680px, 74vh, 1120px); }
    .kg-explore-sidebar .report { flex: 0 0 auto; min-height: 280px; max-height: none; }
    .kg-explore-sidebar .panel { flex: 1; display: flex; flex-direction: column; }
    .kg-explore-sidebar .table-wrap { flex: 1; min-height: 260px; max-height: none; overflow: auto; }
    .kg-explore-sidebar.collapsed { min-width: 56px; width: 56px; opacity: 0.98; }
    .kg-explore-sidebar.collapsed .kg-detail-content { display: none; }
    .kg-explore-sidebar.collapsed .kg-detail-toggle { width: 100%; }
    .kg-explore-toggle-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
    .kg-explore-toggle-row .title-2 { margin: 0; }
    .kg-detail-toggle { white-space: nowrap; }
    .shell { display: grid; gap: 16px; }
    .shell.two-col { grid-template-columns: 1.4fr 0.6fr; }
    .shell.three-col { grid-template-columns: 1.1fr 0.65fr 0.65fr; }
    .report { white-space: pre-wrap; overflow: auto; max-height: 520px; border-radius: 14px; padding: 14px; border: 1px solid rgba(93, 79, 61, 0.12); background: #fffdf9; color: var(--text); }
    @media (max-width: 1100px) {
      .hero, .grid-2, .shell.two-col, .shell.three-col, .kg-explore-layout { grid-template-columns: 1fr; }
      .kg-explore-graph { min-height: 58vh; height: 58vh; }
    }
    """

    if page == "/kg":
        body = f"""
        <section class='hero'>
          <div class='card'>
            <h2 class='title-2'>Knowledge Graph Overview</h2>
            <p class='muted'>A browsable, file-backed KG surface for sites, samples, aeDNA taxa, modules, proxy data, and ontology-linked entities.</p>
            <div class='chip-row' id='kg-overview-chips'></div>
            <div class='grid-2' style='margin-top:16px;'>
              <div class='panel'><h3 class='title-2'>Node types</h3><div class='table-wrap' id='kg-node-types'></div></div>
              <div class='panel'><h3 class='title-2'>Edge predicates</h3><div class='table-wrap' id='kg-edge-types'></div></div>
            </div>
          </div>
          <div class='card'>
            <h2 class='title-2'>Quick Links</h2>
            <div class='chip-row'>
              <a class='chip' href='/kg/search'>Search</a>
              <a class='chip' href='/kg/explore'>Explore</a>
              <a class='chip' href='/kg/paths'>Paths</a>
              <a class='chip' href='/kg/node'>Node</a>
              <a class='chip' href='/kg/downloads'>Downloads</a>
            </div>
            <div style='margin-top:16px;' class='panel'>
              <h3 class='title-2'>Metagraph</h3>
              <div class='table-wrap' id='kg-metagraph'></div>
            </div>
          </div>
        </section>
        <section class='card'>
          <h2 class='title-2'>Source Datasets</h2>
          <div class='table-wrap' id='kg-datasets'></div>
        </section>
        """
        script = """
        async function initKgOverview() {
          const schema = (window.__KG_PAGE__ && window.__KG_PAGE__.schema) || {};
          const manifest = (schema.manifest || {});
          const counts = [
            ["Nodes", (manifest.counts && manifest.counts.nodes) || 0],
            ["Edges", (manifest.counts && manifest.counts.edges) || 0],
            ["Measurements", (manifest.counts && manifest.counts.measurements) || 0],
            ["Sites", (manifest.counts && manifest.counts.site_nodes) || 0],
          ];
          document.getElementById("kg-overview-chips").innerHTML = counts.map(([k, v]) => `<span class="chip"><strong>${escapeHtml(k)}:</strong> ${escapeHtml(v)}</span>`).join("");
          document.getElementById("kg-node-types").innerHTML = tableHtml(schema.node_types || []);
          document.getElementById("kg-edge-types").innerHTML = tableHtml(schema.edge_types || []);
          document.getElementById("kg-metagraph").innerHTML = tableHtml((schema.metagraph || []).slice(0, 200));
          document.getElementById("kg-datasets").innerHTML = tableHtml(schema.datasets || []);
        }
        initKgOverview();
        """
    elif page == "/kg/search":
        body = """
        <section class='card'>
          <h2 class='title-2'>Search</h2>
          <div class='controls'>
            <input id='kg-search-q' placeholder='Search nodes by label, id, taxon, site, variable...' />
            <select id='kg-search-type'><option value=''>All types</option></select>
            <input id='kg-search-limit' type='number' min='10' max='200' value='50' style='width:120px;' />
            <button onclick='runKgSearch()'>Search</button>
          </div>
          <div class='grid-2'>
            <div class='table-wrap' id='kg-search-table'></div>
            <div class='panel'>
              <h3 class='title-2'>Node Summary</h3>
              <div class='report' id='kg-search-detail'>Run a search to inspect a node.</div>
            </div>
          </div>
        </section>
        """
        script = """
        function renderSearchRowLink(row) {
          const id = row.node_id || "";
          return `<a href='/kg/node?id=${encodeURIComponent(id)}'>${escapeHtml(id)}</a>`;
        }
        async function runKgSearch() {
          const q = document.getElementById("kg-search-q").value || "";
          const nodeType = document.getElementById("kg-search-type").value || "";
          const limit = document.getElementById("kg-search-limit").value || "50";
          const data = await fetchJson(`/api/kg/search?query=${encodeURIComponent(q)}&node_type=${encodeURIComponent(nodeType)}&limit=${encodeURIComponent(limit)}`);
          const rows = (data.rows || []).map(row => ({
            node_id: renderSearchRowLink(row),
            node_type: row.node_type || "",
            label: row.label || "",
            search_score: row.search_score || "",
            site_id: row.site_id || "",
            taxon: row.taxon || "",
            module_id: row.module_id || "",
            variable: row.variable || "",
          }));
          document.getElementById("kg-search-table").innerHTML = tableHtml(rows);
          if (data.rows && data.rows.length) {
            await loadKgNode(data.rows[0].node_id);
          }
        }
        async function loadKgNode(nodeId) {
          const data = await fetchJson(`/api/kg/node?id=${encodeURIComponent(nodeId)}`);
          const node = data.node || {};
          const lines = [
            `node_id: ${node.node_id || ""}`,
            `node_type: ${node.node_type || ""}`,
            `label: ${node.label || ""}`,
            `site_id: ${node.site_id || ""}`,
            `taxon: ${node.taxon || ""}`,
            `module_id: ${node.module_id || ""}`,
            `variable: ${node.variable || ""}`,
            `source_table: ${node.source_table || ""}`,
            `source_file: ${node.source_file || ""}`,
          ];
          document.getElementById("kg-search-detail").textContent = lines.join("\\n");
        }
        async function initKgSearch() {
          const schema = (window.__KG_PAGE__ && window.__KG_PAGE__.schema) || {};
          document.getElementById("kg-search-type").innerHTML = ["<option value=''>All types</option>", ...(schema.node_types || []).map(row => `<option value='${escapeHtml(row.node_type)}'>${escapeHtml(row.node_type)} (${escapeHtml(row.count)})</option>`)].join("");
          const initial = (window.__KG_PAGE__ && window.__KG_PAGE__.initial) || {};
          document.getElementById("kg-search-q").value = initial.query || "";
          document.getElementById("kg-search-type").value = initial.node_type || "";
          if (initial.query) {
            await runKgSearch();
          } else {
            document.getElementById("kg-search-table").innerHTML = tableHtml([]);
          }
        }
        initKgSearch();
        """
    elif page == "/kg/explore":
        body = """
        <section class='kg-explore-layout'>
          <div class='card kg-explore-main'>
            <h2 class='title-2'>Explore</h2>
            <div class='controls'>
              <input id='kg-focus' placeholder='Node id, site, or taxon' />
              <select id='kg-depth'><option value='1'>1 hop</option><option value='2'>2 hops</option><option value='3'>3 hops</option></select>
              <select id='kg-edge-type'><option value=''>All edges</option></select>
              <select id='kg-node-type'><option value=''>All nodes</option></select>
              <input id='kg-limit' type='number' min='20' max='300' value='150' style='width:120px;' />
              <button onclick='loadKgExplore()'>Refresh</button>
              <button class='secondary' onclick='focusSelectedNode()'>Inspect selected</button>
            </div>
            <div class='graph kg-explore-graph' id='kg-cy'></div>
          </div>
          <div class='card kg-explore-sidebar' id='kg-explore-sidebar'>
            <div class='kg-explore-toggle-row'>
              <h2 class='title-2'>Node Detail</h2>
              <button class='secondary kg-detail-toggle' onclick='toggleKgSidebar()'>Collapse</button>
            </div>
            <div class='kg-detail-content'>
              <div class='report' id='kg-node-detail'>Click a node to inspect it.</div>
              <div class='panel' style='margin-top:14px;'>
                <h3 class='title-2'>Selected neighborhood</h3>
                <div class='table-wrap' id='kg-neighborhood-table'></div>
              </div>
            </div>
          </div>
        </section>
        """
        script = """
        let kgCy = null;
        let kgSelected = null;
        let kgResizeObserver = null;
        let kgSidebarCollapsed = false;
        function cyStyles() {
          return [
            { selector: 'node', style: { 'label': 'data(label)', 'font-size': 10, 'text-wrap': 'wrap', 'text-max-width': 90, 'background-color': '#57b8ff', 'border-width': 1, 'border-color': '#e5e7eb', 'width': 18, 'height': 18 } },
            { selector: 'node.site', style: { 'background-color': '#1d7ed6', 'shape': 'round-rectangle', 'width': 28, 'height': 28 } },
            { selector: 'node.sample', style: { 'background-color': '#0ca678' } },
            { selector: 'node.taxon', style: { 'background-color': '#2b8a3e' } },
            { selector: 'node.module', style: { 'background-color': '#f08c00', 'shape': 'diamond', 'width': 24, 'height': 24 } },
            { selector: 'node.proxymasurement', style: { 'background-color': '#f59f00' } },
            { selector: 'node.proxymeasurement', style: { 'background-color': '#f59f00' } },
            { selector: 'node.proxyvariable', style: { 'background-color': '#20c997' } },
            { selector: 'node.dataset', style: { 'background-color': '#adb5bd' } },
            { selector: 'node.analysisrun', style: { 'background-color': '#e8590c' } },
            { selector: 'node.ontologyterm', style: { 'background-color': '#868e96' } },
            { selector: 'node:selected', style: { 'border-width': 3, 'border-color': '#f7b955' } },
            { selector: 'edge', style: { 'curve-style': 'bezier', 'line-color': '#9db0c8', 'target-arrow-shape': 'triangle', 'target-arrow-color': '#9db0c8', 'opacity': 0.65, 'width': 1.5 } },
            { selector: 'edge.site_has_sample', style: { 'line-color': '#57b8ff' } },
            { selector: 'edge.sample_observed_taxon', style: { 'line-color': '#49d17a' } },
            { selector: 'edge.sample_has_measurement', style: { 'line-color': '#f7b955' } },
            { selector: 'edge.taxon_member_of_module', style: { 'line-color': '#f08c00', 'target-arrow-color': '#f08c00' } },
            { selector: 'edge.measurement_of_variable', style: { 'line-color': '#20c997' } },
            { selector: 'edge.measurement_derived_from_dataset', style: { 'line-color': '#adb5bd' } },
            { selector: 'edge.entity_has_ontology_term', style: { 'line-color': '#868e96' } },
            { selector: '.path-edge', style: { 'line-color': '#f7b955', 'width': 3.5, 'opacity': 1 } },
          ];
        }
        async function renderKgNodeDetail(nodeId) {
          const data = await fetchJson(`/api/kg/node?id=${encodeURIComponent(nodeId)}`);
          const node = data.node || {};
          const detailLines = [
            `node_id: ${node.node_id || ""}`,
            `node_type: ${node.node_type || ""}`,
            `label: ${node.label || ""}`,
            `site_id: ${node.site_id || ""}`,
            `taxon: ${node.taxon || ""}`,
            `module_id: ${node.module_id || ""}`,
            `variable: ${node.variable || ""}`,
            `source_table: ${node.source_table || ""}`,
            `source_file: ${node.source_file || ""}`,
          ];
          document.getElementById("kg-node-detail").textContent = detailLines.join("\\n");
          document.getElementById("kg-neighborhood-table").innerHTML = tableHtml((data.incident_edges || []).slice(0, 80));
        }
        async function loadKgExplore() {
          const focus = document.getElementById("kg-focus").value || "";
          const depth = document.getElementById("kg-depth").value || "1";
          const edgeType = document.getElementById("kg-edge-type").value || "";
          const nodeType = document.getElementById("kg-node-type").value || "";
          const limit = document.getElementById("kg-limit").value || "150";
          const data = await fetchJson(`/api/kg/neighborhood?id=${encodeURIComponent(focus)}&depth=${encodeURIComponent(depth)}&edge_type=${encodeURIComponent(edgeType)}&node_type=${encodeURIComponent(nodeType)}&limit=${encodeURIComponent(limit)}`);
          const elements = (data.elements || {nodes: [], edges: []});
          if (kgCy) {
            kgCy.destroy();
          }
          kgCy = cytoscape({
            container: document.getElementById("kg-cy"),
            elements: [...(elements.nodes || []), ...(elements.edges || [])],
            style: cyStyles(),
            layout: { name: 'cose', animate: false, fit: true, padding: 24 },
            minZoom: 0.2,
            maxZoom: 3
          });
          const kgContainer = document.getElementById("kg-cy");
          if (kgResizeObserver) {
            kgResizeObserver.disconnect();
          }
          if ("ResizeObserver" in window && kgContainer) {
            kgResizeObserver = new ResizeObserver(() => {
              if (kgCy) {
                kgCy.resize();
                kgCy.fit(undefined, 24);
              }
            });
            kgResizeObserver.observe(kgContainer);
            if (kgContainer.parentElement) {
              kgResizeObserver.observe(kgContainer.parentElement);
            }
          } else if (kgCy) {
            window.requestAnimationFrame(() => {
              kgCy.resize();
              kgCy.fit(undefined, 24);
            });
          }
          kgCy.on('tap', 'node', async function(evt) {
            const id = evt.target.id();
            kgSelected = id;
            await renderKgNodeDetail(id);
          });
          if ((elements.nodes || []).length > 0) {
            const first = elements.nodes[0].data.id;
            kgSelected = first;
            await renderKgNodeDetail(first);
          }
          document.getElementById("kg-neighborhood-table").innerHTML = tableHtml(data.nodes || []);
        }
        function focusSelectedNode() {
          if (!kgSelected) return;
          document.getElementById("kg-focus").value = kgSelected;
          loadKgExplore();
        }
        function toggleKgSidebar() {
          kgSidebarCollapsed = !kgSidebarCollapsed;
          const sidebar = document.getElementById("kg-explore-sidebar");
          const button = document.querySelector(".kg-detail-toggle");
          if (sidebar) {
            sidebar.classList.toggle("collapsed", kgSidebarCollapsed);
          }
          if (button) {
            button.textContent = kgSidebarCollapsed ? "Expand" : "Collapse";
          }
          window.requestAnimationFrame(() => {
            if (kgCy) {
              kgCy.resize();
              kgCy.fit(undefined, 24);
            }
          });
        }
        async function initKgExplore() {
          const schema = (window.__KG_PAGE__ && window.__KG_PAGE__.schema) || {};
          document.getElementById("kg-edge-type").innerHTML = ["<option value=''>All edges</option>", ...(schema.edge_types || []).map(row => `<option value='${escapeHtml(row.edge_type)}'>${escapeHtml(row.edge_type)} (${escapeHtml(row.count)})</option>`)].join("");
          document.getElementById("kg-node-type").innerHTML = ["<option value=''>All nodes</option>", ...(schema.node_types || []).map(row => `<option value='${escapeHtml(row.node_type)}'>${escapeHtml(row.node_type)} (${escapeHtml(row.count)})</option>`)].join("");
          const initial = (window.__KG_PAGE__ && window.__KG_PAGE__.initial) || {};
          document.getElementById("kg-focus").value = initial.node_id || initial.site || initial.taxon || "";
          document.getElementById("kg-depth").value = String(initial.depth || 1);
          if (initial.edge_type) document.getElementById("kg-edge-type").value = initial.edge_type;
          if (initial.node_type) document.getElementById("kg-node-type").value = initial.node_type;
          await loadKgExplore();
        }
        window.addEventListener('resize', () => {
          if (kgCy) {
            kgCy.resize();
            kgCy.fit(undefined, 24);
          }
        });
        initKgExplore();
        """
    elif page == "/kg/paths":
        body = """
        <section class='card'>
          <h2 class='title-2'>Typed connectivity search</h2>
          <p>Counts and degree-weighted scores describe connectivity. Open the evidence below to inspect source records. Module membership is exploratory.</p>
          <div class='controls'>
            <select id='kg-metapath'><option value='site_taxon'>Site → sample → taxon</option><option value='taxon_proxy'>Taxon ← sample → measurement → proxy</option><option value='site_module_bridge'>Core sites linked through taxa and a module</option><option value='shared_module'>Taxon → module ← taxon</option></select>
            <button onclick='loadKgConnectivity()'>Search typed connections</button>
          </div>
          <div class='controls'><button onclick='loadKgDemo(0)'>Demo: taxon and SST evidence</button><button onclick='loadKgDemo(1)'>Demo: cores linked through modules</button></div>
          <div id='kg-connectivity-summary'></div>
          <pre id='kg-connectivity-evidence' style='max-height:400px;overflow:auto;white-space:pre-wrap;'></pre>
          <h3 class='title-2'>Shortest path explorer</h3>
          <div class='controls'>
            <input id='kg-path-source' placeholder='Source node id' />
            <input id='kg-path-target' placeholder='Target node id' />
            <select id='kg-path-edge-type'><option value=''>All edges</option></select>
            <input id='kg-path-depth' type='number' min='1' max='8' value='4' style='width:120px;' />
            <button onclick='loadKgPath()'>Find path</button>
          </div>
          <div class='shell two-col'>
            <div class='graph' id='kg-path-cy'></div>
            <div class='panel'>
              <h3 class='title-2'>Path summary</h3>
              <div class='chip-row' id='kg-path-summary'></div>
              <div class='table-wrap' id='kg-path-table' style='margin-top:12px;'></div>
            </div>
          </div>
        </section>
        """
        script = """
        let kgPathCy = null;
        async function loadKgDemo(index) {
          const data = await fetchJson('/api/kg/demo');
          const q = (data.questions || [])[index];
          if (!q) return;
          document.getElementById("kg-path-source").value = q.source;
          document.getElementById("kg-path-target").value = q.target;
          document.getElementById("kg-metapath").value = q.metapath;
          await loadKgConnectivity();
        }
        async function loadKgConnectivity() {
          const source = document.getElementById("kg-path-source").value;
          const target = document.getElementById("kg-path-target").value;
          const metapath = document.getElementById("kg-metapath").value;
          const data = await fetchJson(`/api/kg/connectivity?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&metapath=${encodeURIComponent(metapath)}`);
          document.getElementById("kg-connectivity-summary").textContent = data.status === "missing" ? "Choose existing source and target node IDs or labels." : `Paths: ${data.path_count}; DWPC: ${data.dwpc}; count status: ${data.count_status}; evidence paths shown: ${(data.paths || []).length}`;
          document.getElementById("kg-connectivity-evidence").textContent = JSON.stringify(data.paths || [], null, 2);
        }
        async function loadKgPath() {
          const source = document.getElementById("kg-path-source").value || "";
          const target = document.getElementById("kg-path-target").value || "";
          const edgeType = document.getElementById("kg-path-edge-type").value || "";
          const maxDepth = document.getElementById("kg-path-depth").value || "4";
          const data = await fetchJson(`/api/kg/paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&edge_type=${encodeURIComponent(edgeType)}&max_depth=${encodeURIComponent(maxDepth)}`);
          document.getElementById("kg-path-summary").innerHTML = (data.summary || []).map(row => `<span class="chip"><strong>${escapeHtml(row.label)}:</strong> ${escapeHtml(row.value)}</span>`).join("");
          document.getElementById("kg-path-table").innerHTML = tableHtml(data.edges || []);
          const elements = data.elements || {nodes: [], edges: []};
          if (kgPathCy) kgPathCy.destroy();
          kgPathCy = cytoscape({
            container: document.getElementById("kg-path-cy"),
            elements: [...(elements.nodes || []), ...(elements.edges || [])],
            style: cyStyles().concat([{ selector: '.path-edge', style: { 'line-color': '#f7b955', 'width': 4, 'opacity': 1 } }]),
            layout: { name: 'breadthfirst', directed: false, fit: true, padding: 30 },
          });
        }
        async function initKgPaths() {
          const schema = (window.__KG_PAGE__ && window.__KG_PAGE__.schema) || {};
          document.getElementById("kg-path-edge-type").innerHTML = ["<option value=''>All edges</option>", ...(schema.edge_types || []).map(row => `<option value='${escapeHtml(row.edge_type)}'>${escapeHtml(row.edge_type)} (${escapeHtml(row.count)})</option>`)].join("");
          const initial = (window.__KG_PAGE__ && window.__KG_PAGE__.initial) || {};
          document.getElementById("kg-path-source").value = initial.source || "";
          document.getElementById("kg-path-target").value = initial.target || "";
          if (initial.edge_type) document.getElementById("kg-path-edge-type").value = initial.edge_type;
          document.getElementById("kg-path-depth").value = String(initial.max_depth || 4);
          if (initial.source && initial.target) {
            await loadKgPath();
          }
        }
        initKgPaths();
        """
    elif page == "/kg/node":
        body = """
        <section class='card'>
          <h2 class='title-2'>Node Detail</h2>
          <div class='controls'>
            <input id='kg-node-id' placeholder='Node id' />
            <button onclick='loadKgNodePage()'>Load node</button>
            <a class='chip' href='/kg/explore'>Open explore</a>
          </div>
          <div class='shell two-col'>
            <div>
              <div class='panel'><h3 class='title-2'>Node</h3><div class='report' id='kg-node-info'>Select a node.</div></div>
              <div class='panel' style='margin-top:14px;'><h3 class='title-2'>Incident edges</h3><div class='table-wrap' id='kg-node-edges'></div></div>
            </div>
            <div>
              <div class='panel'><h3 class='title-2'>Measurements</h3><div class='table-wrap' id='kg-node-measurements'></div></div>
              <div class='panel' style='margin-top:14px;'><h3 class='title-2'>Neighbors</h3><div class='table-wrap' id='kg-node-neighbors'></div></div>
            </div>
          </div>
        </section>
        """
        script = """
        async function loadKgNodePage() {
          const id = document.getElementById("kg-node-id").value || "";
          const data = await fetchJson(`/api/kg/node?id=${encodeURIComponent(id)}`);
          const node = data.node || {};
          document.getElementById("kg-node-info").textContent = [
            `node_id: ${node.node_id || ""}`,
            `node_type: ${node.node_type || ""}`,
            `label: ${node.label || ""}`,
            `site_id: ${node.site_id || ""}`,
            `core: ${node.core || ""}`,
            `taxon: ${node.taxon || ""}`,
            `module_id: ${node.module_id || ""}`,
            `variable: ${node.variable || ""}`,
            `source_table: ${node.source_table || ""}`,
            `source_file: ${node.source_file || ""}`,
          ].join("\\n");
          document.getElementById("kg-node-edges").innerHTML = tableHtml(data.incident_edges || []);
          document.getElementById("kg-node-measurements").innerHTML = tableHtml(data.measurements || []);
          document.getElementById("kg-node-neighbors").innerHTML = tableHtml(data.neighbors || []);
        }
        async function initKgNode() {
          const initial = (window.__KG_PAGE__ && window.__KG_PAGE__.initial) || {};
          document.getElementById("kg-node-id").value = initial.node_id || "";
          if (initial.node_id) {
            await loadKgNodePage();
          }
        }
        initKgNode();
        """
    else:
        body = """
        <section class='grid-2'>
          <div class='card'>
            <h2 class='title-2'>Downloads</h2>
            <div class='table-wrap' id='kg-download-table'></div>
          </div>
          <div class='card'>
            <h2 class='title-2'>Manifest</h2>
            <div class='report' id='kg-manifest'></div>
          </div>
        </section>
        """
        script = """
        async function initKgDownloads() {
          const downloads = (window.__KG_PAGE__ && window.__KG_PAGE__.downloads) || {};
          document.getElementById("kg-download-table").innerHTML = tableHtml((downloads.files || []).map(row => ({
            name: `<a href='/kg/file?name=${encodeURIComponent(row.name)}'>${escapeHtml(row.name)}</a>`,
            exists: row.exists,
            size: row.size,
          })));
          document.getElementById("kg-manifest").textContent = JSON.stringify(downloads.manifest || {}, null, 2);
        }
        initKgDownloads();
        """

    template = """
    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8"/>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <title>__TITLE__</title>
      <script src="/assets/vendor/cytoscape.min.js"></script>
      <style>__CSS__</style>
    </head>
    <body>
      <script>window.__KG_PAGE__ = __PAGE_DATA__;</script>
      <header>
        <div class="head">
          <div>
            <h1>__TITLE__</h1>
            <p><strong>__ANALYSIS_LABEL__</strong></p>
            <p>Branch: __BRANCH__ | Threshold: __THRESHOLD__ | Method: __METHOD__ | __ACTIVE__</p>
          </div>
          <div class="chip-row">
            <a class="chip" href="/">NGraph Home</a>
            <a class="chip" href="/kg/downloads">KG Files</a>
          </div>
        </div>
        <div class="nav">__NAV__</div>
      </header>
      <main class="kg-main">
        __BODY__
      </main>
      <script>
      const PAGE = window.__KG_PAGE__ || {};
      function escapeHtml(text) {
        return String(text == null ? "" : text).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
      }
      function tableHtml(rows) {
        if (!rows || !rows.length) return '<div class="muted" style="padding:12px;">No rows.</div>';
        const cols = Object.keys(rows[0]);
        const head = cols.map(c => `<th>${escapeHtml(c)}</th>`).join("");
        const body = rows.map(r => `<tr>${cols.map(c => `<td>${r[c] == null ? "" : r[c]}</td>`).join("")}</tr>`).join("");
        return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      }
      async function fetchJson(url) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return await res.json();
      }
      __SCRIPT__
      </script>
    </body>
    </html>
    """
    html_text = template.replace("__TITLE__", html.escape(active_label + " | NGraph KG"))
    html_text = html_text.replace("__CSS__", base_css)
    html_text = html_text.replace("__PAGE_DATA__", page_data)
    html_text = html_text.replace("__ANALYSIS_LABEL__", html.escape(app.analysis_label()))
    html_text = html_text.replace("__BRANCH__", html.escape(app.branch))
    html_text = html_text.replace("__THRESHOLD__", html.escape(PRIMARY_THRESHOLD))
    html_text = html_text.replace("__METHOD__", html.escape(PRIMARY_METHOD))
    html_text = html_text.replace("__ACTIVE__", html.escape(active_label))
    html_text = html_text.replace("__NAV__", nav_html)
    html_text = html_text.replace("__BODY__", body)
    html_text = html_text.replace("__SCRIPT__", script)
    return html_text


class BrowserHandler(BaseHTTPRequestHandler):
    app: NGraphBrowser

    def log_message(self, format: str, *args: Any) -> None:
        self.server.app.logger.info("%s - %s", self.client_address[0], format % args)

    def send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        data = json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
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
            if path.startswith("/assets/"):
                rel = Path(unquote(path[len("/assets/") :]))
                asset_root = (PROJECT_ROOT / "web_assets").resolve()
                asset_path = (asset_root / rel).resolve()
                if asset_root not in asset_path.parents and asset_path != asset_root:
                    self.send_response(404)
                    self.end_headers()
                    return
                if not asset_path.exists() or not asset_path.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                content_type = "application/octet-stream"
                if asset_path.suffix == ".js":
                    content_type = "application/javascript; charset=utf-8"
                elif asset_path.suffix == ".css":
                    content_type = "text/css; charset=utf-8"
                elif asset_path.suffix == ".svg":
                    content_type = "image/svg+xml"
                self.send_text(asset_path.read_text(encoding="utf-8"), content_type=content_type)
                return
            if path == "/kg/file":
                name = Path(unquote(params.get("name", [""])[0]))
                file_root = app.kg_dir.resolve()
                file_path = (file_root / name).resolve()
                if file_root not in file_path.parents and file_path != file_root:
                    self.send_response(404)
                    self.end_headers()
                    return
                if not file_path.exists() or not file_path.is_file():
                    self.send_response(404)
                    self.end_headers()
                    return
                content_type = "text/plain; charset=utf-8"
                if file_path.suffix == ".json":
                    content_type = "application/json; charset=utf-8"
                elif file_path.suffix in {".tsv", ".txt", ".md"}:
                    content_type = "text/plain; charset=utf-8"
                self.send_text(file_path.read_text(encoding="utf-8"), content_type=content_type)
                return
            if path in {"/kg", "/kg/search", "/kg/explore", "/kg/paths", "/kg/node", "/kg/downloads"}:
                self.send_text(render_kg_page(app, path, params), content_type="text/html; charset=utf-8")
                return
            if path == "/":
                self.send_text(HTML_PAGE, content_type="text/html; charset=utf-8")
                return
            if path == "/api/summary":
                self.send_json(app.summary())
                return
            if path == "/api/health":
                self.send_json(app.health())
                return
            if path == "/api/kg/demo":
                demo = optional_json(app.kg_dir / "tables" / "mvp_validation_and_demo.json")
                self.send_json({"questions": [{"question": q["question"], **{k: q["answer"][k] for k in ["source", "target", "metapath"]}} for q in demo.get("questions", [])]})
                return
            if path == "/api/kg/metapaths":
                self.send_json({"metapaths": {k: [{"predicate": p, "direction": d} for p,d in v] for k,v in CATALOG.items()}})
                return
            if path == "/api/kg/connectivity":
                metapath = params.get("metapath", ["site_taxon"])[0]
                if metapath not in CATALOG:
                    self.send_json({"error": "Unknown metapath", "choices": list(CATALOG)}, status=400)
                    return
                self.send_json(app.kg_connectivity(params.get("source", [""])[0], params.get("target", [""])[0], metapath, safe_int(params.get("limit", ["20"])[0], 20)))
                return
            if path == "/api/kg/schema":
                self.send_json(app.kg_schema())
                return
            if path == "/api/kg/search":
                self.send_json(
                    app.kg_search_nodes(
                        query=params.get("query", [""])[0],
                        node_type=params.get("node_type", [""])[0],
                        limit=safe_int(params.get("limit", ["50"])[0], 50),
                        offset=safe_int(params.get("offset", ["0"])[0], 0),
                    )
                )
                return
            if path == "/api/kg/node":
                self.send_json(app.kg_node_detail(params.get("id", [""])[0]))
                return
            if path == "/api/kg/neighborhood":
                self.send_json(
                    app.kg_neighborhood(
                        node_id=params.get("id", [""])[0],
                        depth=safe_int(params.get("depth", ["1"])[0], 1),
                        edge_type=params.get("edge_type", [""])[0],
                        node_type=params.get("node_type", [""])[0],
                        limit=safe_int(params.get("limit", ["150"])[0], 150),
                    )
                )
                return
            if path == "/api/kg/paths":
                self.send_json(
                    app.kg_path(
                        source=params.get("source", [""])[0],
                        target=params.get("target", [""])[0],
                        max_depth=safe_int(params.get("max_depth", ["4"])[0], 4),
                        edge_type=params.get("edge_type", [""])[0],
                    )
                )
                return
            if path == "/api/kg/downloads":
                self.send_json(app.kg_downloads())
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
                frame = context["link_taxon_site" if relation_type == "taxon_site" else "link_taxon_taxon"].copy()
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
                payload = app.build_embedding_payload(focus=focus, limit=max(1, min(safe_int(params.get("limit", ["800"])[0], 800), 2000)))
                self.send_json(payload)
                return
            if path == "/api/kg":
                site = params.get("site", [""])[0]
                taxon = params.get("taxon", [""])[0]
                limit = int(params.get("limit", ["40"])[0])
                payload = app.build_kg_payload(site=site, taxon=taxon, limit=limit)
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

    logger = setup_logger(PROJECT_ROOT / "logs" / os.environ.get("NG_LOG_SCOPE", "") / "14_ngraph_local_browser.log")
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
