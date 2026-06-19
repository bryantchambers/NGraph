#!/usr/bin/env python3
"""Train a batched per-site DiffPool baseline on exported NGraph site graphs."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple


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
    missing = [name for name, module in REQUIRED_MODULES.items() if __import__("importlib.util").util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "Missing required Python packages for DiffPool training: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from matplotlib import pyplot as plt
from torch import nn
from torch_geometric.nn import dense_diff_pool
import seaborn as sns


SEED = 42
torch.manual_seed(SEED)
np.random.seed(SEED)


class DenseGraphBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.lin = nn.Linear(in_channels, out_channels)

    def forward(self, x: torch.Tensor, adj: torch.Tensor, mask: torch.Tensor | None) -> torch.Tensor:
        deg = adj.sum(dim=-1, keepdim=True).clamp(min=1.0)
        h = torch.bmm(adj, x) / deg
        h = self.lin(h)
        if mask is not None:
            h = h * mask.unsqueeze(-1)
        return F.relu(h)


class DiffPoolNet(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int, assign_dim: int, assign_dim_2: int):
        super().__init__()
        self.embed1 = DenseGraphBlock(in_channels, hidden_channels)
        self.assign1 = DenseGraphBlock(in_channels, assign_dim)
        self.embed2 = DenseGraphBlock(hidden_channels, hidden_channels)
        self.assign2 = DenseGraphBlock(hidden_channels, assign_dim_2)

    def forward(self, x: torch.Tensor, adj: torch.Tensor, mask: torch.Tensor) -> Dict[str, torch.Tensor]:
        z0 = self.embed1(x, adj, mask)
        s1 = torch.softmax(self.assign1(x, adj, mask), dim=-1)
        x1, adj1, link1, ent1 = dense_diff_pool(z0, adj, s1, mask)
        mask1 = torch.ones(x1.size(0), x1.size(1), device=x.device)
        z1 = self.embed2(x1, adj1, mask1)
        s2 = torch.softmax(self.assign2(x1, adj1, mask1), dim=-1)
        x2, adj2, link2, ent2 = dense_diff_pool(z1, adj1, s2, mask1)
        return {
            "z0": z0,
            "s1": s1,
            "x1": x1,
            "adj1": adj1,
            "link1": link1,
            "ent1": ent1,
            "x2": x2,
            "adj2": adj2,
            "link2": link2,
            "ent2": ent2,
        }


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


def build_site_graphs(
    taxon_nodes: pd.DataFrame,
    site_nodes: pd.DataFrame,
    taxon_taxon: pd.DataFrame,
    site_site: pd.DataFrame,
    taxon_site: pd.DataFrame,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, List[str], List[str], Dict[Tuple[str, str], float]]:
    taxon_features, taxon_cols = numeric_feature_frame(taxon_nodes, exclude=["threshold", "taxon_index"])
    site_features, site_cols = numeric_feature_frame(site_nodes, exclude=["threshold", "method"])
    taxon_order = taxon_nodes["taxon"].astype(str).tolist()
    site_order = site_nodes["core"].astype(str).tolist()
    taxon_index = {name: i for i, name in enumerate(taxon_order)}

    edge_weight_lookup: Dict[Tuple[str, str], float] = {}
    for row in site_site.itertuples(index=False):
        a, b = str(row.site_from), str(row.site_to)
        edge_weight_lookup[tuple(sorted((a, b)))] = float(row.weight)

    feature_cols = [c for c in taxon_site.columns if c not in {"threshold", "method", "core", "taxon", "edge_type"} and pd.api.types.is_numeric_dtype(taxon_site[c])]
    if not feature_cols:
        raise SystemExit("No numeric taxon-site feature columns were found.")
    taxon_site = taxon_site.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    n_taxa = len(taxon_order)
    n_sites = len(site_order)
    n_feat = len(feature_cols)
    taxon_features_by_site = torch.zeros((n_sites, n_taxa, n_feat), dtype=torch.float32)
    adjacency = torch.zeros((n_sites, n_taxa, n_taxa), dtype=torch.float32)
    mask = torch.zeros((n_sites, n_taxa), dtype=torch.float32)

    for site_pos, site_name in enumerate(site_order):
        site_rows = taxon_site[taxon_site["core"].astype(str) == site_name]
        if site_rows.empty:
            continue
        mask[site_pos, :] = 0.0
        for row in site_rows.itertuples(index=False):
            taxon = str(row.taxon)
            if taxon not in taxon_index:
                continue
            tax_pos = taxon_index[taxon]
            mask[site_pos, tax_pos] = 1.0
            vals = np.asarray([getattr(row, col) for col in feature_cols], dtype=np.float32)
            taxon_features_by_site[site_pos, tax_pos, :] = torch.from_numpy(vals)

        edges = taxon_taxon[taxon_taxon["source_core"].astype(str) == site_name]
        if edges.empty:
            continue
        max_weight = float(edges["abs_weight"].max()) if float(edges["abs_weight"].max()) > 0 else 1.0
        for row in edges.itertuples(index=False):
            i = taxon_index.get(str(row.taxon_from))
            j = taxon_index.get(str(row.taxon_to))
            if i is None or j is None:
                continue
            w = float(row.abs_weight) / max_weight
            adjacency[site_pos, i, j] = max(adjacency[site_pos, i, j], w)
            adjacency[site_pos, j, i] = max(adjacency[site_pos, j, i], w)

    # Normalize node features globally per combo after filling.
    x = taxon_features_by_site
    base_feature = torch.from_numpy(taxon_features.to_numpy()).unsqueeze(0).repeat(n_sites, 1, 1)
    x = torch.cat([base_feature, x], dim=-1)
    x = x * mask.unsqueeze(-1)

    # Normalize each adjacency matrix to [0, 1].
    for i in range(n_sites):
        max_val = float(adjacency[i].max())
        if max_val > 0:
            adjacency[i] = adjacency[i] / max_val

    return x, adjacency, mask, site_features, taxon_order, site_order, edge_weight_lookup


def consistency_loss(assignments: torch.Tensor, mask: torch.Tensor, site_weights: Dict[Tuple[str, str], float], site_order: List[str]) -> torch.Tensor:
    if assignments.size(0) < 2:
        return torch.tensor(0.0, device=assignments.device)
    total = torch.tensor(0.0, device=assignments.device)
    denom = 0.0
    for i in range(assignments.size(0)):
        for j in range(i + 1, assignments.size(0)):
            pair = tuple(sorted((site_order[i], site_order[j])))
            weight = float(site_weights.get(pair, 0.0))
            if weight <= 0:
                continue
            shared = (mask[i] > 0) & (mask[j] > 0)
            if shared.sum().item() == 0:
                continue
            diff = assignments[i, shared, :] - assignments[j, shared, :]
            total = total + weight * diff.pow(2).mean()
            denom += weight
    if denom == 0:
        return torch.tensor(0.0, device=assignments.device)
    return total / denom


def train_combo(branch: str, threshold: str, method: str, epochs: int = 160) -> pd.DataFrame:
    combo_dir = combo_dirs(branch, threshold, method)
    if not combo_dir.exists():
        raise SystemExit(f"Missing deep-module export directory: {combo_dir}")

    taxon_nodes, site_nodes, taxon_taxon, site_site, taxon_site, manifest = load_combo_tables(combo_dir)
    x, adj, mask, site_features, taxon_order, site_order, site_weights = build_site_graphs(
        taxon_nodes, site_nodes, taxon_taxon, site_site, taxon_site
    )

    n_sites, n_taxa, n_feat = x.shape
    assign_dim_1 = max(4, min(32, int(round(math.sqrt(n_taxa)))))
    assign_dim_2 = max(2, assign_dim_1 // 2)
    hidden = max(32, min(64, n_feat * 4))

    model = DiffPoolNet(in_channels=n_feat, hidden_channels=hidden, assign_dim=assign_dim_1, assign_dim_2=assign_dim_2)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=1e-4)

    history = []
    best_state = None
    best_loss = math.inf

    mask_pair = mask.unsqueeze(2) * mask.unsqueeze(1)
    site_order_list = site_order

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad()
        out = model(x, adj, mask)
        recon_logits = torch.matmul(out["z0"], out["z0"].transpose(1, 2))
        recon = F.mse_loss(torch.sigmoid(recon_logits) * mask_pair, adj * mask_pair)
        c_loss = consistency_loss(out["s1"], mask, site_weights, site_order_list)
        loss = recon + out["link1"] + out["ent1"] + out["link2"] + out["ent2"] + 0.25 * c_loss
        loss.backward()
        optimizer.step()

        history.append(
            {
                "epoch": epoch,
                "total_loss": float(loss.item()),
                "recon_loss": float(recon.item()),
                "link_loss_1": float(out["link1"].item()),
                "entropy_loss_1": float(out["ent1"].item()),
                "link_loss_2": float(out["link2"].item()),
                "entropy_loss_2": float(out["ent2"].item()),
                "consistency_loss": float(c_loss.item()),
            }
        )
        if loss.item() < best_loss:
            best_loss = float(loss.item())
            best_state = {"epoch": epoch, "state_dict": model.state_dict()}

    if best_state is not None:
        model.load_state_dict(best_state["state_dict"])

    model.eval()
    with torch.no_grad():
        out = model(x, adj, mask)

    s1 = out["s1"].cpu().numpy()
    assignment_entropy = -(s1 * np.log(s1 + 1e-12)).sum(axis=-1)
    consensus = s1.mean(axis=0)
    consensus_module = consensus.argmax(axis=-1)
    mask_np = mask.cpu().numpy()

    module_rows = []
    for site_idx, site_name in enumerate(site_order):
        for tax_idx, taxon in enumerate(taxon_order):
            if mask[site_idx, tax_idx].item() <= 0:
                continue
            row = {
                "threshold": threshold,
                "method": method,
                "site": site_name,
                "taxon": taxon,
                "sites_present": int(mask[:, tax_idx].sum().item()),
                "assignment_entropy": float(assignment_entropy[site_idx, tax_idx]),
                "consensus_module": f"M{int(consensus_module[tax_idx]) + 1}",
            }
            for k in range(s1.shape[-1]):
                row[f"module_prob_{k + 1}"] = float(s1[site_idx, tax_idx, k])
            module_rows.append(row)

    module_df = pd.DataFrame(module_rows)
    consensus_df = pd.DataFrame(
        {
            "threshold": threshold,
            "method": method,
            "taxon": taxon_order,
            "consensus_module": [f"M{int(v) + 1}" for v in consensus_module],
            "mean_assignment_entropy": assignment_entropy.mean(axis=0),
            "sites_present": mask.cpu().numpy().sum(axis=0).astype(int),
        }
    )

    site_summary = []
    for site_idx, site_name in enumerate(site_order):
        site_summary.append(
            {
                "threshold": threshold,
                "method": method,
                "site": site_name,
                "present_taxa": int(mask[site_idx].sum().item()),
                "mean_assignment_entropy": float(assignment_entropy[site_idx, mask_np[site_idx] > 0].mean()) if mask[site_idx].sum().item() > 0 else np.nan,
                "mean_site_similarity": float(np.mean([site_weights.get(tuple(sorted((site_name, other))), 0.0) for other in site_order if other != site_name])),
            }
        )
    site_summary_df = pd.DataFrame(site_summary)

    history_df = pd.DataFrame(history)
    history_df.to_csv(combo_dir / "tables" / "diffpool_training_history.tsv", sep="\t", index=False)
    module_df.to_csv(combo_dir / "tables" / "diffpool_site_taxon_assignments.tsv", sep="\t", index=False)
    consensus_df.to_csv(combo_dir / "tables" / "diffpool_consensus_modules.tsv", sep="\t", index=False)
    site_summary_df.to_csv(combo_dir / "tables" / "diffpool_site_summary.tsv", sep="\t", index=False)

    torch.save(
        {
            "state_dict": model.state_dict(),
            "threshold": threshold,
            "method": method,
            "assign_dim_1": assign_dim_1,
            "assign_dim_2": assign_dim_2,
            "feature_dim": n_feat,
            "taxon_order": taxon_order,
            "site_order": site_order,
        },
        combo_dir / "models" / "diffpool_model.pt",
    )

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    sns.barplot(data=consensus_df.sort_values("consensus_module"), x="consensus_module", y="sites_present", ax=axes[0], color="#4477aa")
    axes[0].set_title(f"Consensus module support: {threshold}/{method}")
    axes[0].set_xlabel("Consensus module")
    axes[0].set_ylabel("Sites present")

    sns.histplot(
        data=module_df,
        x="assignment_entropy",
        hue="site",
        multiple="layer",
        bins=20,
        ax=axes[1],
        element="step",
    )
    axes[1].set_title("Site-wise soft assignment entropy")
    axes[1].set_xlabel("Entropy")
    axes[1].set_ylabel("Taxon count")
    fig.tight_layout()
    fig.savefig(combo_dir / "figures" / "diffpool_assignment_diagnostics.png", dpi=180)
    plt.close(fig)

    run_summary = pd.DataFrame(
        [
            {
                "threshold": threshold,
                "method": method,
                "best_epoch": best_state["epoch"] if best_state is not None else np.nan,
                "best_loss": best_loss,
                "assign_dim_1": assign_dim_1,
                "assign_dim_2": assign_dim_2,
                "n_taxa": n_taxa,
                "n_sites": n_sites,
            }
        ]
    )
    run_summary.to_csv(combo_dir / "tables" / "diffpool_run_summary.tsv", sep="\t", index=False)
    return run_summary


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
    parser.add_argument("--epochs", type=int, default=160)
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
        print(f"Training DiffPool on {threshold}/{method}")
        summaries.append(train_combo(args.branch, threshold, method, epochs=args.epochs))

    if summaries:
        summary_df = pd.concat(summaries, ignore_index=True)
        summary_df.to_csv(root / "diffpool_run_summary.tsv", sep="\t", index=False)
        print(f"Validated DiffPool runs written to {root / 'diffpool_run_summary.tsv'}")
    else:
        raise SystemExit("No DiffPool runs completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
