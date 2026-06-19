#!/usr/bin/env python3
"""Optional Gemini adapter for the NGraph local RAG stack."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional


DEFAULT_MODEL = "gemini-3.1-flash-lite"
DEFAULT_MAX_OUTPUT_TOKENS = 512
DEFAULT_TEMPERATURE = 0.2
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


@dataclass
class GeminiConfig:
    api_key: str
    model: str = DEFAULT_MODEL
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    temperature: float = DEFAULT_TEMPERATURE
    timeout_s: int = 60


def get_api_key() -> Optional[str]:
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if key:
        key = key.strip()
    return key or None


def get_model() -> str:
    return os.environ.get("NG_GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def get_enabled_provider() -> str:
    return os.environ.get("NG_LLM_PROVIDER", "local").strip().lower() or "local"


def get_max_output_tokens() -> int:
    value = os.environ.get("NG_GEMINI_MAX_OUTPUT_TOKENS")
    try:
        return max(64, int(value)) if value is not None else DEFAULT_MAX_OUTPUT_TOKENS
    except Exception:
        return DEFAULT_MAX_OUTPUT_TOKENS


def get_temperature() -> float:
    value = os.environ.get("NG_GEMINI_TEMPERATURE")
    try:
        return float(value) if value is not None else DEFAULT_TEMPERATURE
    except Exception:
        return DEFAULT_TEMPERATURE


def build_config() -> Optional[GeminiConfig]:
    api_key = get_api_key()
    if not api_key:
        return None
    return GeminiConfig(
        api_key=api_key,
        model=get_model(),
        max_output_tokens=get_max_output_tokens(),
        temperature=get_temperature(),
    )


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_text(response_obj: Dict[str, Any]) -> str:
    candidates = response_obj.get("candidates") or []
    if not candidates:
        return ""
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            texts.append(str(part["text"]))
    return "\n".join(texts).strip()


def _parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    cleaned = _strip_code_fences(text)
    if not cleaned:
        return None
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def call_gemini(prompt: str, *, system_instruction: str = "", config: Optional[GeminiConfig] = None) -> Dict[str, Any]:
    cfg = config or build_config()
    if cfg is None:
        return {
            "provider": "gemini",
            "status": "missing_key",
            "model": get_model(),
            "text": "",
            "json": None,
        }

    payload: Dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": cfg.temperature,
            "maxOutputTokens": cfg.max_output_tokens,
            "responseMimeType": "application/json",
        },
    }
    if system_instruction.strip():
        payload["systemInstruction"] = {"parts": [{"text": system_instruction.strip()}]}

    body = json.dumps(payload).encode("utf-8")
    url = GEMINI_ENDPOINT.format(model=cfg.model)
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-goog-api-key": cfg.api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=cfg.timeout_s) as response:
            response_text = response.read().decode("utf-8")
        response_obj = json.loads(response_text)
        text = _extract_text(response_obj)
        parsed = _parse_json_text(text)
        return {
            "provider": "gemini",
            "status": "ok",
            "model": cfg.model,
            "text": text,
            "json": parsed,
            "raw_response": response_obj,
        }
    except urllib.error.HTTPError as exc:
        try:
            error_text = exc.read().decode("utf-8")
        except Exception:
            error_text = str(exc)
        return {
            "provider": "gemini",
            "status": f"http_error_{exc.code}",
            "model": cfg.model,
            "text": "",
            "json": None,
            "error": error_text,
        }
    except Exception as exc:  # pragma: no cover - runtime guard
        return {
            "provider": "gemini",
            "status": "error",
            "model": cfg.model,
            "text": "",
            "json": None,
            "error": str(exc),
        }
