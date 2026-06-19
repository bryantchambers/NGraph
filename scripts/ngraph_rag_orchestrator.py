#!/usr/bin/env python3
"""Local RAG orchestration helpers for the NGraph discovery phase."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from ngraph_llm_adapter import call_gemini, get_enabled_provider


def dataframe_records(df: pd.DataFrame, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []
    frame = df.copy()
    if limit is not None:
        frame = frame.head(limit)
    records = []
    for row in frame.to_dict(orient="records"):
        cleaned = {}
        for key, value in row.items():
            if pd.isna(value):
                cleaned[key] = None
            elif hasattr(value, "item"):
                try:
                    cleaned[key] = value.item()
                except Exception:  # pragma: no cover - defensive
                    cleaned[key] = value
            else:
                cleaned[key] = value
        records.append(cleaned)
    return records


def _as_frame(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, list):
        return pd.DataFrame(value)
    return pd.DataFrame()


def _unique(values: Iterable[Any]) -> List[Any]:
    seen = set()
    out: List[Any] = []
    for value in values:
        if value is None:
            continue
        key = str(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _card_matches(cards: pd.DataFrame, card_type: Optional[str] = None, entity_ids: Optional[Sequence[str]] = None) -> pd.DataFrame:
    frame = cards.copy()
    if card_type and "card_type" in frame.columns:
        frame = frame[frame["card_type"].astype(str) == str(card_type)]
    if entity_ids and "entity_id" in frame.columns:
        targets = {str(item) for item in entity_ids if item is not None and str(item)}
        frame = frame[frame["entity_id"].astype(str).isin(targets)]
    return frame


def _card_ids_from_semantic_hits(semantic_hits: pd.DataFrame) -> List[str]:
    if semantic_hits is None or semantic_hits.empty:
        return []
    if "card_id" in semantic_hits.columns:
        return semantic_hits["card_id"].dropna().astype(str).tolist()
    return []


def _taxa_from_result(result: Dict[str, Any]) -> List[str]:
    taxa: List[str] = []
    if result.get("context_taxa"):
        taxa.extend([str(item) for item in result["context_taxa"] if item is not None and str(item)])
    top_taxa = _as_frame(result.get("top_taxa"))
    if not top_taxa.empty:
        taxon_col = "taxon" if "taxon" in top_taxa.columns else "entity_id" if "entity_id" in top_taxa.columns else None
        if taxon_col:
            taxa.extend(top_taxa[taxon_col].dropna().astype(str).tolist())
    semantic_hits = _as_frame(result.get("semantic_hits"))
    if not semantic_hits.empty and "entity_id" in semantic_hits.columns and "card_type" in semantic_hits.columns:
        taxa.extend(
            semantic_hits.loc[semantic_hits["card_type"].astype(str) == "taxon", "entity_id"].dropna().astype(str).tolist()
        )
    return _unique(taxa)


def _module_ids_for_taxa(taxon_nodes: pd.DataFrame, taxa: Sequence[str]) -> List[str]:
    if taxon_nodes is None or taxon_nodes.empty or not taxa:
        return []
    frame = taxon_nodes.copy()
    if "taxon" not in frame.columns:
        return []
    frame = frame[frame["taxon"].astype(str).isin({str(item) for item in taxa})]
    module_ids: List[str] = []
    for col, prefix in [("vgae_module", "vgae"), ("diffpool_module", "diffpool")]:
        if col not in frame.columns:
            continue
        values = frame[col].dropna().astype(str).tolist()
        module_ids.extend([f"{prefix}:{value}" for value in values if value and value.lower() != "nan"])
    return _unique(module_ids)


def _site_ids_for_result(result: Dict[str, Any]) -> List[str]:
    sites: List[str] = []
    if result.get("core"):
        sites.append(str(result["core"]))
    if result.get("selected_samples"):
        # Query output stores sample IDs; site cards are keyed by core so only keep core-like IDs.
        pass
    semantic_hits = _as_frame(result.get("semantic_hits"))
    if not semantic_hits.empty and "entity_id" in semantic_hits.columns and "card_type" in semantic_hits.columns:
        sites.extend(
            semantic_hits.loc[semantic_hits["card_type"].astype(str) == "site", "entity_id"].dropna().astype(str).tolist()
        )
    return _unique(sites)


def _link_entity_ids(result: Dict[str, Any]) -> List[str]:
    link_hits = _as_frame(result.get("link_hits"))
    if link_hits.empty:
        return []
    if not {"relation_type", "threshold", "method"}.issubset(link_hits.columns):
        return []
    id_cols = None
    if {"taxon_from", "taxon_to"}.issubset(link_hits.columns):
        id_cols = ("taxon_from", "taxon_to")
    elif {"source_taxon", "target_node"}.issubset(link_hits.columns):
        id_cols = ("source_taxon", "target_node")
    if id_cols is None:
        return []
    entity_ids = []
    for _, row in link_hits.iterrows():
        relation_type = str(row.get("relation_type", "")).strip()
        threshold = str(row.get("threshold", "")).strip()
        method = str(row.get("method", "")).strip()
        source = str(row.get(id_cols[0], "")).strip()
        target = str(row.get(id_cols[1], "")).strip()
        if not relation_type or not source or not target:
            continue
        entity_ids.append("::".join([relation_type, threshold, method, source, target]))
    return _unique(entity_ids)


def build_retrieval_bundle(query: str, result: Dict[str, Any], data: Dict[str, Any], top_k: int = 12) -> Dict[str, Any]:
    cards = _as_frame(data.get("cards"))
    semantic_hits = _as_frame(result.get("semantic_hits"))
    top_taxa = _as_frame(result.get("top_taxa"))
    link_hits = _as_frame(result.get("link_hits"))
    capability_tables = result.get("capability_tables") or {}
    taxon_nodes = _as_frame(data.get("taxon_nodes"))
    site_nodes = _as_frame(data.get("site_nodes"))

    semantic_card_ids = _card_ids_from_semantic_hits(semantic_hits)
    taxa = _taxa_from_result(result)
    module_ids = _module_ids_for_taxa(taxon_nodes, taxa)
    site_ids = _site_ids_for_result(result)
    link_entity_ids = _link_entity_ids(result)

    cards_by_priority = []
    if semantic_card_ids:
        cards_by_priority.append(_card_matches(cards, entity_ids=semantic_card_ids))
    if taxa:
        cards_by_priority.append(_card_matches(cards, card_type="taxon", entity_ids=taxa))
    if module_ids:
        cards_by_priority.append(_card_matches(cards, card_type="module", entity_ids=module_ids))
    if site_ids:
        cards_by_priority.append(_card_matches(cards, card_type="site", entity_ids=site_ids))
    if link_entity_ids:
        cards_by_priority.append(_card_matches(cards, card_type="predicted_link", entity_ids=link_entity_ids))

    if cards_by_priority:
        retrieved_cards = pd.concat(cards_by_priority, ignore_index=True)
        if "card_id" in retrieved_cards.columns:
            retrieved_cards = retrieved_cards.drop_duplicates(subset=["card_id"], keep="first")
    else:
        retrieved_cards = cards.head(0).copy()

    if "score" in retrieved_cards.columns:
        retrieved_cards["retrieval_rank"] = pd.to_numeric(retrieved_cards["score"], errors="coerce")
    else:
        retrieved_cards["retrieval_rank"] = pd.Series([None] * len(retrieved_cards), index=retrieved_cards.index, dtype="object")

    if not retrieved_cards.empty:
        priority_map = {"predicted_link": 0, "module": 1, "taxon": 2, "site": 3, "sample": 4}
        retrieved_cards["retrieval_priority"] = retrieved_cards["card_type"].map(priority_map).fillna(9)
        if "score" in retrieved_cards.columns:
            retrieved_cards = retrieved_cards.sort_values(["retrieval_priority", "score"], ascending=[True, False])
        else:
            retrieved_cards = retrieved_cards.sort_values(["retrieval_priority", "entity_id"], ascending=[True, True])

    retrieval_summary = {
        "query": query,
        "query_type": result.get("query_type", "general"),
        "semantic_hit_count": int(len(semantic_hits)),
        "retrieved_card_count": int(len(retrieved_cards)),
        "taxon_context_count": int(len(taxa)),
        "module_context_count": int(len(module_ids)),
        "site_context_count": int(len(site_ids)),
        "predicted_link_count": int(len(link_hits)),
        "card_types": _unique(retrieved_cards["card_type"].dropna().astype(str).tolist()) if not retrieved_cards.empty and "card_type" in retrieved_cards.columns else [],
    }

    prompt = build_prompt(query, result, retrieved_cards, taxon_nodes, site_nodes, capability_tables)
    bundle = {
        "query": query,
        "query_type": result.get("query_type", "general"),
        "retrieval_summary": retrieval_summary,
        "retrieved_cards": retrieved_cards,
        "retrieved_links": link_hits,
        "retrieved_taxa": taxa,
        "retrieved_modules": module_ids,
        "retrieved_sites": site_ids,
        "prompt": prompt,
        "prompt_preview": prompt,
        "llm_provider": "local",
        "llm_status": "fallback_only",
    }
    return bundle


def build_prompt(
    query: str,
    result: Dict[str, Any],
    retrieved_cards: pd.DataFrame,
    taxon_nodes: pd.DataFrame,
    site_nodes: pd.DataFrame,
    capability_tables: Dict[str, Any],
) -> str:
    lines = [
        "You are answering a scientific question using NGraph retrieval evidence.",
        "Use only the supplied evidence cards and graph context.",
        "Cite card_id values inline when making factual claims.",
        "If evidence is weak or missing, say so explicitly.",
        "Return JSON with keys: answer, evidence_ids, observations, predictions, uncertainty, followups.",
        "",
        f"Question: {query}",
        f"Query type: {result.get('query_type', 'general')}",
    ]
    if result.get("answer_lines"):
        lines.extend(["", "Deterministic local answer draft:"])
        for line in result["answer_lines"]:
            lines.append(f"- {line}")
    lines.extend(["", "Top retrieved evidence cards:"])
    if retrieved_cards is None or retrieved_cards.empty:
        lines.append("- No evidence cards retrieved.")
    else:
        for _, row in retrieved_cards.head(12).iterrows():
            card_id = str(row.get("card_id", ""))
            title = str(row.get("title", ""))
            summary = str(row.get("summary", ""))
            status = str(row.get("observed_status", ""))
            lines.append(f"- [{card_id}] {title} :: {summary} (status={status})")

    if result.get("top_taxa") is not None and not _as_frame(result.get("top_taxa")).empty:
        lines.extend(["", "Top taxa table available in the retrieval bundle."])
    if result.get("link_hits") is not None and not _as_frame(result.get("link_hits")).empty:
        lines.extend(["", "Top predicted links table available in the retrieval bundle."])
    if capability_tables:
        lines.extend(["", "Functional capability tables available for the context taxa."])
    if not taxon_nodes.empty:
        lines.append(f"Taxon node context available for {len(taxon_nodes)} taxa.")
    if not site_nodes.empty:
        lines.append(f"Site node context available for {len(site_nodes)} sites.")
    lines.extend([
        "",
        "Response rule:",
        "Return a concise synthesis, list the strongest evidence IDs, and separate observations from predictions.",
    ])
    return "\n".join(lines)


def build_system_instruction() -> str:
    return "\n".join(
        [
            "You are a careful scientific synthesis engine for NGraph.",
            "Answer only from the retrieved evidence cards and graph context.",
            "Do not invent taxa, modules, ages, or functions.",
            "Prefer concise answers with explicit uncertainty.",
            "Return valid JSON with keys: answer, evidence_ids, observations, predictions, uncertainty, followups.",
            "Keep evidence_ids as an array of card_id strings.",
            "Separate observed facts from inferred hypotheses.",
        ]
    )


def augment_result(query: str, result: Dict[str, Any], data: Dict[str, Any], top_k: int = 12) -> Dict[str, Any]:
    bundle = build_retrieval_bundle(query, result, data, top_k=top_k)
    enriched = dict(result)
    llm_provider = get_enabled_provider()
    llm_result: Dict[str, Any] = {
        "provider": "local",
        "status": "disabled",
        "model": None,
        "text": "",
        "json": None,
    }
    if llm_provider in {"gemini", "google"}:
        llm_result = call_gemini(bundle["prompt"], system_instruction=build_system_instruction())
    llm_status = llm_result.get("status", "disabled")
    llm_text = llm_result.get("text", "") or ""
    llm_json = llm_result.get("json")
    llm_answer = ""
    llm_evidence_ids: List[str] = []
    llm_observations: List[str] = []
    llm_predictions: List[str] = []
    llm_uncertainty = ""
    llm_followups: List[str] = []
    if isinstance(llm_json, dict):
        llm_answer = str(llm_json.get("answer", "")).strip()
        llm_evidence_ids = [str(item) for item in llm_json.get("evidence_ids", []) if item is not None and str(item)]
        llm_observations = [str(item) for item in llm_json.get("observations", []) if item is not None and str(item)]
        llm_predictions = [str(item) for item in llm_json.get("predictions", []) if item is not None and str(item)]
        llm_uncertainty = str(llm_json.get("uncertainty", "")).strip()
        llm_followups = [str(item) for item in llm_json.get("followups", []) if item is not None and str(item)]
    elif llm_text:
        llm_answer = llm_text.strip()
    enriched["retrieval_bundle"] = {
        "query": bundle["query"],
        "query_type": bundle["query_type"],
        "retrieval_summary": bundle["retrieval_summary"],
        "prompt_preview": bundle["prompt_preview"],
        "retrieved_taxa": bundle["retrieved_taxa"],
        "retrieved_modules": bundle["retrieved_modules"],
        "retrieved_sites": bundle["retrieved_sites"],
        "llm_provider": llm_result.get("provider", bundle["llm_provider"]) if llm_provider in {"gemini", "google"} else bundle["llm_provider"],
        "llm_status": llm_status if llm_provider in {"gemini", "google"} else bundle["llm_status"],
        "llm_model": llm_result.get("model"),
    }
    enriched["retrieved_cards"] = bundle["retrieved_cards"]
    enriched["retrieved_links"] = bundle["retrieved_links"]
    enriched["retrieval_prompt"] = bundle["prompt"]
    enriched["retrieval_summary"] = bundle["retrieval_summary"]
    enriched["llm_provider"] = llm_result.get("provider", bundle["llm_provider"]) if llm_provider in {"gemini", "google"} else bundle["llm_provider"]
    enriched["llm_status"] = llm_status if llm_provider in {"gemini", "google"} else bundle["llm_status"]
    enriched["llm_model"] = llm_result.get("model")
    enriched["llm_answer"] = llm_answer
    enriched["llm_evidence_ids"] = llm_evidence_ids
    enriched["llm_observations"] = llm_observations
    enriched["llm_predictions"] = llm_predictions
    enriched["llm_uncertainty"] = llm_uncertainty
    enriched["llm_followups"] = llm_followups
    if llm_text:
        enriched["llm_raw_text"] = llm_text
    if isinstance(llm_json, dict):
        enriched["llm_response_json"] = llm_json
    return enriched
