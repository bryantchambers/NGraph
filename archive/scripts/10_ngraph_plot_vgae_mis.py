#!/usr/bin/env python3
"""Plot VGAE taxon embeddings colored by context-weighted MIS exposure."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import List

REQUIRED_MODULES = {
    "numpy": "numpy",
    "pandas": "pandas",
    "matplotlib": "matplotlib",
}


def check_environment() -> None:
    missing = [name for name, module in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "Missing required Python packages for MIS embedding plots: "
            + ", ".join(missing)
            + ". Update the ngraph Python environment; do not install from scripts."
        )


check_environment()

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import TwoSlopeNorm


SEED = 42
np.random.seed(SEED)
MIS_GLIACIAL_CUTOFF = 4.0


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def deep_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_modules"


def resolve_metadata_path() -> Path:
    candidates = [
        project_root() / "Source" / "ROCS" / "data" / "metadata_v5.tsv",
        project_root() / "data" / "metadata" / "metadata_v5.tsv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("Could not locate metadata_v5.tsv in Source/ROCS or data/metadata")


def log_line(log_path: Path, *parts: object) -> None:
    line = f"[{pd.Timestamp.now():%Y-%m-%d %H:%M:%S}] " + "".join(str(p) for p in parts)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")
    print(line)


def weighted_mis_summary(edge_df: pd.DataFrame, meta_df: pd.DataFrame) -> pd.DataFrame:
    mis_lookup = meta_df.loc[:, ["core", "mis"]].dropna(subset=["core", "mis"]).copy()
    mis_lookup["core"] = mis_lookup["core"].astype(str)

    merged = edge_df.merge(mis_lookup, on="core", how="left")
    merged["mean_tax_abund_tad"] = pd.to_numeric(merged["mean_tax_abund_tad"], errors="coerce")
    merged["mis"] = pd.to_numeric(merged["mis"], errors="coerce")
    merged = merged[np.isfinite(merged["mean_tax_abund_tad"]) & np.isfinite(merged["mis"])].copy()

    rows = []
    for taxon, group in merged.groupby("taxon", sort=False):
        weights = group["mean_tax_abund_tad"].to_numpy(dtype=float)
        values = group["mis"].to_numpy(dtype=float)
        weight_sum = float(weights.sum())
        core_count = int(group["core"].nunique())
        if weight_sum <= 0 or len(values) == 0:
            rows.append(
                {
                    "taxon": taxon,
                    "mis_context_mean": np.nan,
                    "mis_context_sd": np.nan,
                    "mis_context_min": np.nan,
                    "mis_context_max": np.nan,
                    "mis_context_weight_sum": weight_sum,
                    "mis_context_core_count": core_count,
                    "mis_context_glacial_fraction": np.nan,
                    "mis_context_class": np.nan,
                }
            )
            continue
        mu = float(np.average(values, weights=weights))
        var = float(np.average((values - mu) ** 2, weights=weights))
        rows.append(
            {
                "taxon": taxon,
                "mis_context_mean": mu,
                "mis_context_sd": float(np.sqrt(max(var, 0.0))),
                "mis_context_min": float(np.min(values)),
                "mis_context_max": float(np.max(values)),
                "mis_context_weight_sum": weight_sum,
                "mis_context_core_count": core_count,
                "mis_context_glacial_fraction": float(
                    np.average((values >= MIS_GLIACIAL_CUTOFF).astype(float), weights=weights)
                ),
                "mis_context_class": "glacial_like" if mu >= MIS_GLIACIAL_CUTOFF else "interglacial_like",
            }
        )

    return pd.DataFrame(rows)


def plot_embedding(module_df: pd.DataFrame, root_meta: pd.DataFrame, combo_dir: Path, threshold: str, method: str) -> pd.DataFrame:
    edges = pd.read_csv(combo_dir / "tables" / "hetero_taxon_site_edges.tsv", sep="\t")
    taxon_mis = weighted_mis_summary(edges, root_meta)

    plot_df = module_df.merge(taxon_mis, on="taxon", how="left")
    plot_df = plot_df[np.isfinite(plot_df["pca_1"]) & np.isfinite(plot_df["pca_2"])].copy()

    plot_out = combo_dir / "figures" / "vgae_taxon_embedding_mis_pca.png"

    valid = plot_df[np.isfinite(plot_df["mis_context_mean"])].copy()
    if valid.empty:
        raise SystemExit(f"No finite MIS summary values available for {threshold}/{method}")

    vmin = float(root_meta["mis"].min())
    vmax = float(root_meta["mis"].max())
    norm = TwoSlopeNorm(vmin=vmin, vcenter=MIS_GLIACIAL_CUTOFF, vmax=vmax)

    fig, ax = plt.subplots(figsize=(7.2, 5.5))
    sc = ax.scatter(
        valid["pca_1"],
        valid["pca_2"],
        c=valid["mis_context_mean"],
        cmap="coolwarm",
        norm=norm,
        s=28,
        alpha=0.9,
        linewidths=0,
    )
    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Taxon MIS exposure\n(context-weighted mean)")
    cbar.set_ticks([vmin, MIS_GLIACIAL_CUTOFF, vmax])
    cbar.set_ticklabels(
        [
            f"interglacial end\n{vmin:.2f}",
            f"MIS {MIS_GLIACIAL_CUTOFF:.1f}",
            f"glacial end\n{vmax:.2f}",
        ]
    )
    ax.set_title(f"VGAE taxon embeddings by MIS context: {threshold}/{method}")
    ax.set_xlabel("PCA 1")
    ax.set_ylabel("PCA 2")
    ax.grid(False)
    fig.tight_layout()
    fig.savefig(plot_out, dpi=180)
    plt.close(fig)

    plot_df.to_csv(combo_dir / "tables" / "vgae_taxon_mis_context.tsv", sep="\t", index=False)
    return plot_df


def discover_combos(root: Path, threshold: str | None, method: str | None) -> List[tuple[str, str, Path]]:
    combos: List[tuple[str, str, Path]] = []
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
    branch = os.environ.get("NG_BRANCH", "abundance_thresholding")
    threshold = os.environ.get("NG_THRESHOLD")
    method = os.environ.get("NG_METHOD")
    root = deep_root(branch)
    metadata_path = resolve_metadata_path()
    meta = pd.read_csv(metadata_path, sep="\t")
    meta["mis"] = pd.to_numeric(meta["mis"], errors="coerce")
    log_path = project_root() / "logs" / "10_ngraph_plot_vgae_mis.log"
    log_line(log_path, "Loaded metadata from ", metadata_path)

    rows: List[pd.DataFrame] = []
    for thr, meth, combo_dir in discover_combos(root, threshold, method):
        module_path = combo_dir / "tables" / "vgae_taxon_modules.tsv"
        if not module_path.exists():
            log_line(log_path, "Skipping ", thr, "/", meth, ": missing ", module_path)
            continue
        module_df = pd.read_csv(module_path, sep="\t")
        if not {"taxon", "pca_1", "pca_2"}.issubset(module_df.columns):
            log_line(log_path, "Skipping ", thr, "/", meth, ": missing PCA columns in ", module_path)
            continue
        plot_df = plot_embedding(module_df, meta, combo_dir, thr, meth)
        rows.append(
            pd.DataFrame(
                {
                    "threshold": [thr],
                    "method": [meth],
                    "taxa_plotted": [int(plot_df["taxon"].nunique())],
                    "mis_min": [float(meta["mis"].min())],
                    "mis_midpoint": [MIS_GLIACIAL_CUTOFF],
                    "mis_max": [float(meta["mis"].max())],
                    "plot_file": [str(combo_dir / "figures" / "vgae_taxon_embedding_mis_pca.png")],
                }
            )
        )
        log_line(log_path, "Method Validated: ", thr, "/", meth, " MIS plot written")

    if rows:
        summary = pd.concat(rows, ignore_index=True)
        summary.to_csv(root / "vgae_mis_plot_summary.tsv", sep="\t", index=False)
        log_line(log_path, "Wrote summary to ", root / "vgae_mis_plot_summary.tsv")
        return 0
    log_line(log_path, "No VGAE taxon embedding plots were generated")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
