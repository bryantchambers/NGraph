#!/usr/bin/env python3
"""Shared helpers for the deep knowledge discovery phase."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

import pandas as pd


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def deep_modules_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_modules"


def knowledge_root(branch: str) -> Path:
    return project_root() / "results" / "ngraph" / branch / "deep_knowledge_discovery"


def combo_root(branch: str, threshold: str, method: str, kind: str = "knowledge") -> Path:
    base = knowledge_root(branch) if kind == "knowledge" else deep_modules_root(branch)
    return base / threshold / method


def combo_tables(branch: str, threshold: str, method: str, kind: str = "knowledge") -> Path:
    return combo_root(branch, threshold, method, kind=kind) / "tables"


def combo_indexes(branch: str, threshold: str, method: str) -> Path:
    return combo_root(branch, threshold, method, kind="knowledge") / "indexes"


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def read_table(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    return pd.read_csv(path, sep="\t")


def read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def list_combo_dirs(branch: str, kind: str = "deep_modules") -> List[Tuple[str, str, Path]]:
    base = deep_modules_root(branch) if kind == "deep_modules" else knowledge_root(branch)
    combos: List[Tuple[str, str, Path]] = []
    if not base.exists():
        return combos
    for thr_dir in sorted(base.glob("prev_*")):
        if not thr_dir.is_dir():
            continue
        for method_dir in sorted(thr_dir.iterdir()):
            if method_dir.is_dir():
                combos.append((thr_dir.name, method_dir.name, method_dir))
    return combos


def normalize_threshold_label(label: str | int) -> str:
    if isinstance(label, int):
        return f"prev_{label}"
    if isinstance(label, str) and label.startswith("prev_"):
        return label
    try:
        return f"prev_{int(label)}"
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError(f"Cannot normalize threshold label: {label!r}") from exc


def safe_slug(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", text.strip()).strip("_")
    return slug or "item"

