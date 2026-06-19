#!/usr/bin/env python3
"""Train a relation-aware VGAE baseline on exported NGraph heterographs."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import importlib.util


REQUIRED_MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "torch": "torch",
    "torch_geometric": "torch_geometric",
    "sklearn": "sklearn",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
}


def check_environment() -> None:
    missing = [name for name, module in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "Missing required Python packages for VGAE training: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from matplotlib import pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from torch import nn
from torch_geometric.data import HeteroData
from torch_geometric.nn import VGAE
from torch_geometric.utils import negative_sampling
import seaborn as sns


SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)


class RelationAwareVGAEEncoder(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int, latent_channels: int, num_relations: int):
        super().__init__()
        self.hidden_channels = hidden_channels
        self.latent_channels = latent_channels
        self.num_relations = num_relations
        self.lin_in = nn.Linear(in_channels, hidden_channels)
        self.lin_mu = nn.Linear(hidden_channels, latent_channels)
        self.lin_logstd = nn.Linear(hidden_channels, latent_channels)
        self.rel_msg = nn.ModuleList([nn.Linear(in_channels, hidden_channels, bias=False) for _ in range(num_relations)])
        self.rel_mu = nn.ModuleList([nn.Linear(hidden_channels, latent_channels, bias=False) for _ in range(num_relations)])
        self.rel_logstd = nn.ModuleList([nn.Linear(hidden_channels, latent_channels, bias=False) for _ in range(num_relations)])
        self.norm = nn.LayerNorm(hidden_channels)

    def aggregate(self, x: torch.Tensor, edge_index: torch.Tensor, edge_type: torch.Tensor, rel_layers: nn.ModuleList, out_dim: int) -> torch.Tensor:
        out = x.new_zeros((x.size(0), out_dim))
        deg = x.new_zeros((x.size(0), 1))
        for rel_id, layer in enumerate(rel_layers):
            mask = edge_type == rel_id
            if mask.sum().item() == 0:
                continue
            src = edge_index[0, mask]
            dst = edge_index[1, mask]
            msg = layer(x[src])
            part = x.new_zeros((x.size(0), out_dim))
            part.index_add_(0, dst, msg)
            out = out + part
            deg.index_add_(0, dst, torch.ones((dst.numel(), 1), dtype=x.dtype, device=x.device))
        return out / deg.clamp(min=1.0)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor, edge_type: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h = F.relu(self.lin_in(x) + self.aggregate(x, edge_index, edge_type, self.rel_msg, self.hidden_channels))
        h = self.norm(h)
        mu = self.lin_mu(h) + self.aggregate(h, edge_index, edge_type, self.rel_mu, self.latent_channels)
        logstd = self.lin_logstd(h) + self.aggregate(h, edge_index, edge_type, self.rel_logstd, self.latent_channels)
        return mu, logstd


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def deep_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_modules"


def combo_dirs(branch: str, threshold: str, method: str) -> Path:
    return deep_root(branch) / threshold / method


def load_combo_tables(combo_dir: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    tables = combo_dir / "tables"
    with open(tables / "heterograph_manifest.json", "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    taxon_nodes = pd.read_csv(tables / "hetero_taxon_nodes.tsv", sep="\t")
    site_nodes = pd.read_csv(tables / "hetero_site_nodes.tsv", sep="\t")
    taxon_taxon = pd.read_csv(tables / "hetero_taxon_taxon_edges.tsv", sep="\t")
    site_site = pd.read_csv(tables / "hetero_site_site_edges.tsv", sep="\t")
    taxon_site = pd.read_csv(tables / "hetero_taxon_site_edges.tsv", sep="\t")
    return taxon_nodes, site_nodes, taxon_taxon, site_site, taxon_site, manifest


def numeric_feature_frame(df: pd.DataFrame, exclude: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
    if not cols:
        raise SystemExit("No numeric feature columns available after excluding: " + ", ".join(exclude))
    features = df[cols].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype(np.float32)
    return features, cols


def build_hetero_graph(
    taxon_nodes: pd.DataFrame,
    site_nodes: pd.DataFrame,
    taxon_taxon: pd.DataFrame,
    site_site: pd.DataFrame,
    taxon_site: pd.DataFrame,
) -> Tuple[HeteroData, Dict[str, int], Dict[str, int], List[str], List[str]]:
    taxon_features, taxon_cols = numeric_feature_frame(
        taxon_nodes,
        exclude=["threshold", "taxon_index"],
    )
    site_features, site_cols = numeric_feature_frame(
        site_nodes,
        exclude=["threshold", "method"],
    )
    feature_dim = max(taxon_features.shape[1], site_features.shape[1])
    if taxon_features.shape[1] < feature_dim:
        pad = feature_dim - taxon_features.shape[1]
        taxon_features = pd.concat(
            [taxon_features, pd.DataFrame(0.0, index=taxon_features.index, columns=[f"taxon_pad_{i+1}" for i in range(pad)])],
            axis=1,
        )
        taxon_cols = taxon_cols + [f"taxon_pad_{i+1}" for i in range(pad)]
    if site_features.shape[1] < feature_dim:
        pad = feature_dim - site_features.shape[1]
        site_features = pd.concat(
            [site_features, pd.DataFrame(0.0, index=site_features.index, columns=[f"site_pad_{i+1}" for i in range(pad)])],
            axis=1,
        )
        site_cols = site_cols + [f"site_pad_{i+1}" for i in range(pad)]

    taxon_index = {taxon: i for i, taxon in enumerate(taxon_nodes["taxon"].astype(str))}
    site_index = {site: i for i, site in enumerate(site_nodes["core"].astype(str))}

    hetero = HeteroData()
    hetero["taxon"].x = torch.from_numpy(taxon_features.to_numpy()).float()
    hetero["site"].x = torch.from_numpy(site_features.to_numpy()).float()
    hetero["taxon"].taxon_id = taxon_nodes["taxon"].astype(str).tolist()
    hetero["site"].site_id = site_nodes["core"].astype(str).tolist()

    # Taxon-taxon relation types are source-core and sign specific.
    for relation_name, group in taxon_taxon.groupby("edge_type", sort=False):
        src = torch.tensor(group["taxon_from"].map(taxon_index).to_numpy(), dtype=torch.long)
        dst = torch.tensor(group["taxon_to"].map(taxon_index).to_numpy(), dtype=torch.long)
        edge_index = torch.stack([torch.cat([src, dst]), torch.cat([dst, src])], dim=0)
        hetero["taxon", relation_name, "taxon"].edge_index = edge_index
        hetero["taxon", relation_name, "taxon"].edge_weight = torch.tensor(
            np.concatenate([group["abs_weight"].to_numpy(), group["abs_weight"].to_numpy()]),
            dtype=torch.float32,
        )

    # Site-site relation is shared within the combo.
    if len(site_site) > 0:
        src = torch.tensor(site_site["site_from"].map(site_index).to_numpy(), dtype=torch.long)
        dst = torch.tensor(site_site["site_to"].map(site_index).to_numpy(), dtype=torch.long)
        edge_index = torch.stack([torch.cat([src, dst]), torch.cat([dst, src])], dim=0)
        hetero["site", "site_similarity", "site"].edge_index = edge_index
        hetero["site", "site_similarity", "site"].edge_weight = torch.tensor(
            np.concatenate([site_site["weight"].to_numpy(), site_site["weight"].to_numpy()]),
            dtype=torch.float32,
        )

    # Taxon-site context is source-core specific.
    for core_id, group in taxon_site.groupby("core", sort=False):
        src = torch.tensor(group["taxon"].map(taxon_index).to_numpy(), dtype=torch.long)
        dst = torch.tensor(group["core"].map(site_index).to_numpy(), dtype=torch.long)
        forward = torch.stack([src, dst], dim=0)
        reverse = torch.stack([dst, src], dim=0)
        rel = f"taxon_site_context__{core_id}"
        rev = f"site_taxon_context__{core_id}"
        hetero["taxon", rel, "site"].edge_index = forward
        hetero["taxon", rel, "site"].edge_weight = torch.tensor(group["mean_clr"].to_numpy(), dtype=torch.float32)
        hetero["site", rev, "taxon"].edge_index = reverse
        hetero["site", rev, "taxon"].edge_weight = torch.tensor(group["mean_clr"].to_numpy(), dtype=torch.float32)

    hetero.validate(raise_on_error=True)
    return hetero, taxon_index, site_index, taxon_cols, site_cols


def hetero_to_homogeneous(
    hetero: HeteroData,
    taxon_index: Dict[str, int],
    site_index: Dict[str, int],
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, List[str], List[str]]:
    taxon_x = hetero["taxon"].x
    site_x = hetero["site"].x
    x = torch.cat([taxon_x, site_x], dim=0).float()
    node_type = torch.cat(
        [
            torch.zeros(taxon_x.size(0), dtype=torch.long),
            torch.ones(site_x.size(0), dtype=torch.long),
        ]
    )
    node_names = list(hetero["taxon"].taxon_id) + list(hetero["site"].site_id)

    edge_chunks: List[torch.Tensor] = []
    edge_type_chunks: List[torch.Tensor] = []
    edge_type_names: List[str] = []

    for rel_id, edge_type in enumerate(hetero.edge_types):
        src_type, rel_name, dst_type = edge_type
        store = hetero[edge_type]
        edge_index = store.edge_index.clone()
        if src_type == "site":
            edge_index[0] += len(taxon_index)
        if dst_type == "site":
            edge_index[1] += len(taxon_index)
        edge_chunks.append(edge_index)
        edge_type_chunks.append(torch.full((edge_index.size(1),), rel_id, dtype=torch.long))
        edge_type_names.append("__".join(edge_type))

    edge_index = torch.cat(edge_chunks, dim=1)
    edge_type = torch.cat(edge_type_chunks, dim=0)
    return x, edge_index, edge_type, node_type, node_names, edge_type_names


def train_combo(branch: str, threshold: str, method: str, epochs: int = 120) -> pd.DataFrame:
    combo_dir = combo_dirs(branch, threshold, method)
    if not combo_dir.exists():
        raise SystemExit(f"Missing deep-module export directory: {combo_dir}")

    taxon_nodes, site_nodes, taxon_taxon, site_site, taxon_site, manifest = load_combo_tables(combo_dir)
    hetero, taxon_index, site_index, taxon_cols, site_cols = build_hetero_graph(
        taxon_nodes, site_nodes, taxon_taxon, site_site, taxon_site
    )
    x, edge_index, edge_type, node_type, node_names, edge_type_names = hetero_to_homogeneous(
        hetero, taxon_index, site_index
    )

    taxon_count = len(taxon_index)
    validation_core = os.environ.get("NG_DEEP_VALIDATION_CORE", "GeoB25202_R2")

    # Reconstruct a row-wise frame to split by relation/core.
    row_frames = []
    for edge_type_name, store in hetero.edge_items():
        src_type, rel_name, dst_type = edge_type_name
        src = store.edge_index[0].cpu().numpy()
        dst = store.edge_index[1].cpu().numpy()
        weight = store.edge_weight.cpu().numpy() if hasattr(store, "edge_weight") else np.ones(len(src))
        for s, t, w in zip(src, dst, weight):
            row_frames.append(
                {
                    "edge_type_name": "__".join(edge_type_name),
                    "src_type": src_type,
                    "dst_type": dst_type,
                    "src": int(s),
                    "dst": int(t),
                    "weight": float(w),
                }
            )
    edge_frame = pd.DataFrame(row_frames)
    edge_frame["src_global"] = edge_frame["src"]
    edge_frame["dst_global"] = edge_frame["dst"]
    site_offset = taxon_count
    edge_frame.loc[edge_frame["src_type"] == "site", "src_global"] += site_offset
    edge_frame.loc[edge_frame["dst_type"] == "site", "dst_global"] += site_offset
    edge_frame["src_global"] = edge_frame["src_global"].astype(int)
    edge_frame["dst_global"] = edge_frame["dst_global"].astype(int)

    # Split on the edge type naming convention from the exporter.
    is_validation = edge_frame["edge_type_name"].str.contains(f"taxon_taxon__{validation_core}__")
    train_frame = edge_frame[~is_validation].copy()
    test_frame = edge_frame[is_validation & (edge_frame["src"] < edge_frame["dst"])].copy()

    train_x = x
    train_edge_index = torch.tensor(train_frame[["src_global", "dst_global"]].astype(int).to_numpy().T, dtype=torch.long)
    train_edge_type_map = {name: i for i, name in enumerate(sorted(train_frame["edge_type_name"].unique()))}
    train_edge_type = torch.tensor(train_frame["edge_type_name"].map(train_edge_type_map).to_numpy(), dtype=torch.long)

    model = VGAE(
        RelationAwareVGAEEncoder(
            in_channels=train_x.size(1),
            hidden_channels=64,
            latent_channels=32,
            num_relations=max(len(train_edge_type_map), 1),
        )
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)

    history = []
    best_state = None
    best_auc = -math.inf
    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        z = model.encode(train_x, train_edge_index, train_edge_type)
        loss = model.recon_loss(z, train_edge_index) + 0.001 * model.kl_loss()
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            z_eval = model.encode(train_x, train_edge_index, train_edge_type)
            taxon_z = z_eval[:taxon_count]
            test_pos = torch.tensor(test_frame[["src", "dst"]].to_numpy().T, dtype=torch.long)
            if len(test_frame) > 0:
                neg = negative_sampling(
                    test_pos,
                    num_nodes=taxon_count,
                    num_neg_samples=test_pos.size(1),
                    method="sparse",
                )
                auc, ap = model.test(taxon_z, test_pos, neg)
            else:
                auc, ap = float("nan"), float("nan")

        history.append(
            {
                "epoch": epoch,
                "train_loss": float(loss.item()),
                "heldout_auc": float(auc),
                "heldout_ap": float(ap),
            }
        )
        if np.isfinite(auc) and auc > best_auc:
            best_auc = auc
            best_state = {
                "epoch": epoch,
                "state_dict": model.state_dict(),
            }

    if best_state is not None:
        model.load_state_dict(best_state["state_dict"])

    model.eval()
    with torch.no_grad():
        z = model.encode(train_x, train_edge_index, train_edge_type)
    taxon_z = z[:taxon_count].cpu().numpy()
    site_z = z[taxon_count:].cpu().numpy()

    # Cluster taxon embeddings.
    k_max = max(2, min(8, taxon_z.shape[0] - 1))
    if taxon_z.shape[0] < 3:
        clusters = np.zeros(taxon_z.shape[0], dtype=int)
        chosen_k = 1
        sil = float("nan")
    else:
        best_k = 2
        best_sil = -math.inf
        for k in range(2, k_max + 1):
            labels = KMeans(n_clusters=k, random_state=SEED, n_init="auto").fit_predict(taxon_z)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(taxon_z, labels)
            if score > best_sil:
                best_sil = score
                best_k = k
        clusters = KMeans(n_clusters=best_k, random_state=SEED, n_init="auto").fit_predict(taxon_z)
        chosen_k = best_k
        sil = float(best_sil)

    pca = PCA(n_components=2, random_state=SEED)
    coords = pca.fit_transform(taxon_z)
    module_df = pd.DataFrame(
        {
            "taxon": taxon_nodes["taxon"].astype(str),
            "threshold": threshold,
            "method": method,
            "module_kmeans": [f"M{m + 1}" for m in clusters],
            "embedding_1": taxon_z[:, 0],
            "embedding_2": taxon_z[:, 1] if taxon_z.shape[1] > 1 else np.zeros(taxon_z.shape[0]),
            "pca_1": coords[:, 0],
            "pca_2": coords[:, 1],
        }
    )
    module_df["module_entropy_proxy"] = 0.0
    module_df["module_count"] = chosen_k
    module_df["silhouette"] = sil

    emb_cols = [f"z_{i+1}" for i in range(taxon_z.shape[1])]
    embeddings = pd.DataFrame(taxon_z, columns=emb_cols)
    embeddings.insert(0, "node_type", "taxon")
    embeddings.insert(0, "node_id", taxon_nodes["taxon"].astype(str))

    site_emb = pd.DataFrame(site_z, columns=[f"z_{i+1}" for i in range(site_z.shape[1])])
    site_emb.insert(0, "node_type", "site")
    site_emb.insert(0, "node_id", site_nodes["core"].astype(str))
    embeddings = pd.concat([embeddings, site_emb], ignore_index=True)

    history_df = pd.DataFrame(history)
    history_df.to_csv(combo_dir / "tables" / "vgae_training_history.tsv", sep="\t", index=False)
    embeddings.to_csv(combo_dir / "tables" / "vgae_embeddings.tsv", sep="\t", index=False)
    module_df.to_csv(combo_dir / "tables" / "vgae_taxon_modules.tsv", sep="\t", index=False)

    test_scores = pd.DataFrame(
        {
            "threshold": threshold,
            "method": method,
            "validation_core": validation_core,
            "best_epoch": best_state["epoch"] if best_state is not None else np.nan,
            "best_heldout_auc": best_auc if np.isfinite(best_auc) else np.nan,
            "module_k": chosen_k,
            "module_silhouette": sil,
        },
        index=[0],
    )
    test_scores.to_csv(combo_dir / "tables" / "vgae_run_summary.tsv", sep="\t", index=False)

    torch.save(
        {
            "state_dict": model.state_dict(),
            "threshold": threshold,
            "method": method,
            "validation_core": validation_core,
            "taxon_feature_columns": taxon_cols,
            "site_feature_columns": site_cols,
            "edge_type_map": train_edge_type_map,
        },
        combo_dir / "models" / "vgae_model.pt",
    )

    # Diagnostic plot.
    fig, ax = plt.subplots(figsize=(7.2, 5.5))
    palette = sns.color_palette("husl", n_colors=max(chosen_k, 2))
    sns.scatterplot(
        data=module_df,
        x="pca_1",
        y="pca_2",
        hue="module_kmeans",
        palette=palette,
        s=28,
        edgecolor="none",
        ax=ax,
    )
    ax.set_title(f"VGAE taxon embeddings: {threshold}/{method}")
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.legend(loc="best", frameon=False, title="Module")
    fig.tight_layout()
    fig.savefig(combo_dir / "figures" / "vgae_taxon_embedding_pca.png", dpi=180)
    plt.close(fig)

    return test_scores


def discover_combos(root: Path, threshold: str | None, method: str | None) -> List[Tuple[str, str, Path]]:
    combos = []
    for thr_dir in sorted(root.glob("prev_*")):
        if threshold is not None and thr_dir.name != threshold:
            continue
        for method_dir in sorted(thr_dir.iterdir()):
            if not method_dir.is_dir():
                continue
            if method in {None, method_dir.name}:
                combos.append((thr_dir.name, method_dir.name, method_dir))
    return combos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default=os.environ.get("NG_BRANCH", "abundance_thresholding"))
    parser.add_argument("--threshold", default=None, help="Limit to one prevalence directory, e.g. prev_5")
    parser.add_argument("--method", default=None, help="Limit to one graph method")
    parser.add_argument("--epochs", type=int, default=120)
    args = parser.parse_args()

    root = deep_root(args.branch)
    if not root.exists():
        raise SystemExit(f"Missing deep-module root: {root}")

    combos = discover_combos(root, args.threshold, args.method)
    if not combos:
        raise SystemExit("No deep-module export directories were found.")

    summaries = []
    for threshold, method, combo_dir in combos:
        tables = combo_dir / "tables"
        required = [
            tables / "hetero_taxon_nodes.tsv",
            tables / "hetero_site_nodes.tsv",
            tables / "hetero_taxon_taxon_edges.tsv",
            tables / "hetero_site_site_edges.tsv",
            tables / "hetero_taxon_site_edges.tsv",
        ]
        if not all(path.exists() for path in required):
            print(f"Skipping {threshold}/{method}: missing export tables", file=sys.stderr)
            continue
        print(f"Training VGAE on {threshold}/{method}")
        summaries.append(train_combo(args.branch, threshold, method, epochs=args.epochs))

    if summaries:
        summary_df = pd.concat(summaries, ignore_index=True)
        summary_df.to_csv(root / "vgae_run_summary.tsv", sep="\t", index=False)
        print(f"Validated VGAE runs written to {root / 'vgae_run_summary.tsv'}")
    else:
        raise SystemExit("No VGAE runs completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
