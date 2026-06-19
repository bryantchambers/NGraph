#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-8000}"
BRANCH="${NG_BRANCH:-abundance_thresholding}"
HOST="${NG_HOST:-0.0.0.0}"

pick_python() {
  if [[ -n "${NG_PYTHON:-}" ]]; then
    printf '%s\n' "${NG_PYTHON}"
    return 0
  fi

  local candidates=(
    python3.14
    python3.13
    python3.12
    python3.11
    python3.10
    python3
  )

  local py
  for py in "${candidates[@]}"; do
    if command -v "${py}" >/dev/null 2>&1; then
      if "${py}" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
      then
        printf '%s\n' "${py}"
        return 0
      fi
    fi
  done

  return 1
}

if [[ "${PORT}" == "-h" || "${PORT}" == "--help" ]]; then
  cat <<'EOF'
Usage: ./start_server.sh [port]

Starts the NGraph local browser on 0.0.0.0.

Environment variables:
  NG_BRANCH  Branch to browse (default: abundance_thresholding)
  NG_HOST    Bind host (default: 0.0.0.0)
  NG_PYTHON  Python interpreter to use if auto-detection is not enough
  NG_LLM_PROVIDER  Set to gemini to enable the Google API adapter
  GEMINI_API_KEY   Gemini API key if you want the Google adapter active
  GOOGLE_API_KEY   Alternate Gemini API key env var supported by the adapter
  NG_GEMINI_MODEL  Gemini model override (default: gemini-3.1-flash-lite)
EOF
  exit 0
fi

PYTHON_BIN="$(pick_python)" || {
  echo "No Python 3.10+ interpreter found. Set NG_PYTHON to a suitable interpreter and retry." >&2
  exit 1
}

exec "${PYTHON_BIN}" "${SCRIPT_DIR}/scripts/14_ngraph_local_browser.py" --host "${HOST}" --port "${PORT}" --branch "${BRANCH}"
