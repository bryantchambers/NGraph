"""Branch-scoped, read-only content for the Constellations interface."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if pd.notna(number) else None
    except (TypeError, ValueError):
        return None


def build_overview(app: Any, threshold: str, method: str) -> dict[str, Any]:
    """Derive visible totals from the active branch, never from a hard-coded run."""
    root = app.global_dir / app.branch
    manifest = app.run_manifest
    sample_frame = app.sample_abundance
    if {"sample", "core", "age_kyr"}.issubset(sample_frame.columns):
        samples = sample_frame[["sample", "core", "age_kyr"]].drop_duplicates("sample")
    else:
        samples = pd.DataFrame(columns=["sample", "core", "age_kyr"])
    ages = pd.to_numeric(samples["age_kyr"], errors="coerce").dropna()
    core_counts = samples.groupby("core")["sample"].nunique().sort_index().to_dict() if not samples.empty else {}
    active_cores = set(str(core) for core in core_counts)
    locations = []
    registered_locations = []
    for row in app.kg_sites.to_dict("records"):
        aliases = [name.strip() for name in str(row.get("core_aliases") or "").split(",")]
        matched = [name for name in aliases if name in active_cores]
        site = {
            "site": str(row.get("site_label") or row.get("site_id") or ""),
            "cores": matched or aliases,
            "latitude": _number(row.get("latitude")),
            "longitude": _number(row.get("longitude")),
            "samples": sum(int(core_counts[name]) for name in matched),
            "active": bool(matched),
        }
        registered_locations.append(site)
        if matched:
            locations.append(site)
    try:
        context = app.combo_context(threshold, method)
        assignments = context["vgae_modules"]
    except FileNotFoundError:
        assignments = pd.DataFrame()
    module_sizes = (
        {str(key): int(value) for key, value in assignments["module_kmeans"].value_counts().sort_index().items()}
        if "module_kmeans" in assignments.columns else {}
    )
    node_counts = (
        {str(key): int(value) for key, value in app.kg_nodes["node_type"].value_counts().items()}
        if "node_type" in app.kg_nodes.columns else {}
    )
    edge_counts = (
        {str(key): int(value) for key, value in app.kg_edges["edge_type"].value_counts().items()}
        if "edge_type" in app.kg_edges.columns else {}
    )
    card_counts = (
        {str(key): int(value) for key, value in app.cards["card_type"].value_counts().items()}
        if "card_type" in app.cards.columns else {}
    )
    sources = []
    for row in app.kg_datasets.to_dict("records"):
        sources.append({"name": str(row.get("label") or row.get("dataset_id") or ""), "source_file": str(row.get("source_file") or "")})
    namespaces = (
        sorted(app.kg_ontology_terms["ontology_prefix"].dropna().astype(str).unique().tolist())
        if "ontology_prefix" in app.kg_ontology_terms.columns else []
    )
    workstreams = sorted(p.name for p in app.global_dir.iterdir() if p.is_dir() and (p / "run_manifest.json").exists()) if app.global_dir.exists() else []
    kg_validation = app.kg_substrate_validation
    return {
        "service": "Constellations",
        "branch": app.branch,
        "run_status": manifest.get("status", "unknown"),
        "analysis_label": app.analysis_label(),
        "threshold": threshold,
        "method": method,
        "counts": {
            "physical_sites": len(locations), "cores": len(active_cores), "samples": int(len(samples)),
            "taxa_in_modules": int(len(assignments)), "modules": len(module_sizes),
            "kg_nodes": int(len(app.kg_nodes)), "kg_edges": int(len(app.kg_edges)),
            "kg_measurements": int(len(app.kg_measurements)),
            "ontology_terms": int(len(app.kg_ontology_terms)),
            "embeddings": int(len(app.vgae_embeddings)), "link_hypotheses": int(len(app.link_predictions)),
            "evidence_cards": int(len(app.cards)), "data_sources": len(sources),
        },
        "age_range_years_bp": [round(float(ages.min() * 1000), 1), round(float(ages.max() * 1000), 1)] if len(ages) else None,
        "core_samples": {str(key): int(value) for key, value in core_counts.items()},
        "locations": locations,
        "registered_locations": registered_locations,
        "module_sizes": module_sizes,
        "node_types": node_counts,
        "edge_types": edge_counts,
        "card_types": card_counts,
        "ontology_namespaces": namespaces,
        "sources": sources,
        "workstreams": workstreams,
        "validation": {"kg": kg_validation.get("status", "unverified"), "run": manifest.get("status", "unknown")},
        "updated_from": [str(root / "run_manifest.json"), str(app.kg_dir / "tables" / "kg_nodes.tsv")],
    }


def build_catalog(app: Any, project_root: Path) -> list[dict[str, Any]]:
    """List curated source and output files; IDs double as a download allowlist."""
    branch_root = (app.global_dir / app.branch).resolve()
    candidates: list[tuple[str, Path]] = []
    for directory, category, pattern in [
        (app.discovery_dir / "reports", "Reports", "*.md"),
        (app.deep_modules_dir / "reports", "Reports", "*.md"),
        (app.kg_dir / "reports", "Reports", "*.md"),
        (app.kg_dir / "tables", "Knowledge graph", "*.json"),
        (app.kg_dir / "tables", "Knowledge graph", "*.tsv"),
        (app.deep_modules_dir, "Figures", "*.png"),
        (app.threshold_dir / "figures", "Figures", "*.png"),
    ]:
        if directory.exists():
            candidates.extend((category, path) for path in directory.rglob(pattern) if path.is_file())
    for path in [
        branch_root / "run_manifest.json",
        app.discovery_dir / "link_prediction_top_candidates.tsv",
        app.deep_modules_dir / threshold_dir(app) / "tables" / "vgae_taxon_modules.tsv",
        project_root / "data" / "metadata" / "metadata_v5.tsv",
    ]:
        if path.is_file():
            candidates.append(("Analysis" if branch_root in path.resolve().parents else "Source data", path))
    for row in app.kg_datasets.to_dict("records"):
        source = str(row.get("source_file") or "")
        path = Path(source)
        if not path.is_absolute():
            path = project_root / path
        if path.is_file() and project_root.resolve() in path.resolve().parents:
            candidates.append(("Source data", path))
    results = []
    seen = set()
    for category, path in candidates:
        resolved = path.resolve()
        relative = resolved.relative_to(project_root.resolve()).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        results.append({"id": relative, "name": path.name, "category": category, "size": path.stat().st_size, "format": path.suffix.lstrip(".").upper() or "FILE"})
    return sorted(results, key=lambda row: (row["category"], row["name"], row["id"]))


def threshold_dir(app: Any) -> Path:
    """Resolve the currently selected default module output without scanning unrelated runs."""
    return Path(app.primary_combo["threshold"]) / app.primary_combo["method"]
