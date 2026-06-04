#!/usr/bin/env bash
# run_pipeline.sh -- NGraph graph-of-graphs workflow.
#
# Usage:
#   bash run_pipeline.sh
#   bash run_pipeline.sh --start 03

set -euo pipefail

RSCRIPT="${RSCRIPT:-Rscript}"
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
S="${PROJ}/scripts"

START="01"
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
  "01|CLR matrix isolation|01_ngraph_clr_matrices.R"
  "02|Input QC ordination and PC correlations|02_ngraph_input_qc.R"
  "03|Site-specific taxon graphs|03_ngraph_site_graphs.R"
  "04|Graph-of-graphs similarity network|04_ngraph_graph_of_graphs.R"
  "05|NGraph summary|05_ngraph_summary.R"
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

cd "${PROJ}"

for i in "${!PIPELINE[@]}"; do
  (( i < start_index )) && continue
  IFS="|" read -r step_id step_name script_name <<< "${PIPELINE[$i]}"
  script_path="${S}/${script_name}"
  [[ -f "${script_path}" ]] || { echo "Pipeline script not found: ${script_path}" >&2; exit 1; }
  log "=== ${step_id}. ${step_name} ==="
  "${RSCRIPT}" "${script_path}"
done

log "=== NGraph pipeline complete ==="
