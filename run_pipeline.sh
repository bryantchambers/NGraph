#!/usr/bin/env bash
# run_pipeline.sh -- NGraph graph-of-graphs workflow.
#
# Usage:
#   bash run_pipeline.sh
#   bash run_pipeline.sh --start 03
#   NG_BRANCH=abundance_thresholding bash run_pipeline.sh

set -euo pipefail

RSCRIPT="${RSCRIPT:-Rscript}"
PYTHON="${PYTHON:-python3}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="${PROJ}/scripts"

START="00"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

log() { echo "[$(date '+%H:%M:%S')] $*"; }

normalize_step() {
  local step="$1"
  if [[ "${step}" =~ ^0*([0-9]+)([[:alpha:]]*)$ ]]; then
    printf "%02d%s" "$((10#${BASH_REMATCH[1]}))" "${BASH_REMATCH[2]}"
  else
    printf "%s" "${step}"
  fi
}

START="$(normalize_step "${START}")"

PIPELINE=(
  "00|Import feedstock into /src/data|00_ngraph_import_feedstock.R"
  "01|CLR matrix isolation|01_ngraph_clr_matrices.R"
  "02|Input QC ordination and PC correlations|02_ngraph_input_qc.R"
  "03|Site-specific taxon graphs|03_ngraph_site_graphs.R"
  "04|Graph-of-graphs similarity network|04_ngraph_graph_of_graphs.R"
  "05|NGraph summary|05_ngraph_summary.R"
  "06|Heterograph export for deep modules|06_ngraph_build_heterograph.R"
  "07|Heterograph VGAE/GAE training|07_ngraph_train_vgae.py"
  "08|Per-site DiffPool training|08_ngraph_train_diffpool.py"
  "09|Deep module summary|09_ngraph_deep_module_summary.R"
  "10|Learned link prediction|10_ngraph_link_prediction.py"
  "11|Evidence card generation|11_ngraph_build_evidence_cards.py"
  "12|Local retrieval index|12_ngraph_build_retrieval_index.py"
  "13|Natural-language query engine|13_ngraph_query_engine.py"
)

start_index=-1
for i in "${!PIPELINE[@]}"; do
  IFS="|" read -r step_id _ _ <<< "${PIPELINE[$i]}"
  if [[ "${step_id}" == "${START}" ]]; then
    start_index="${i}"
    break
  fi
done

if [[ "${start_index}" -lt 0 ]]; then
  echo "Unknown --start step: ${START}" >&2
  echo "Known steps:" >&2
  for entry in "${PIPELINE[@]}"; do
    IFS="|" read -r step_id step_name _ <<< "${entry}"
    echo "  ${step_id}  ${step_name}" >&2
  done
  exit 1
fi

if [[ "${RSCRIPT}" == */* ]]; then
  [[ -x "${RSCRIPT}" ]] || { echo "Rscript is not executable: ${RSCRIPT}" >&2; exit 1; }
else
  command -v "${RSCRIPT}" >/dev/null 2>&1 || { echo "Rscript not found on PATH: ${RSCRIPT}" >&2; exit 1; }
fi

if [[ "${PYTHON}" == */* ]]; then
  [[ -x "${PYTHON}" ]] || { echo "Python is not executable: ${PYTHON}" >&2; exit 1; }
else
  command -v "${PYTHON}" >/dev/null 2>&1 || { echo "Python not found on PATH: ${PYTHON}" >&2; exit 1; }
fi

cd "${PROJ}"

for i in "${!PIPELINE[@]}"; do
  (( i < start_index )) && continue
  IFS="|" read -r step_id step_name script_name <<< "${PIPELINE[$i]}"
  script_path="${S}/${script_name}"
  [[ -f "${script_path}" ]] || { echo "Pipeline script not found: ${script_path}" >&2; exit 1; }
  log "=== ${step_id}. ${step_name} ==="
  case "${script_path}" in
    *.R) "${RSCRIPT}" "${script_path}" ;;
    *.py) "${PYTHON}" "${script_path}" ;;
    *) echo "Unsupported pipeline script type: ${script_path}" >&2; exit 1 ;;
  esac
done

log "=== NGraph pipeline complete ==="
