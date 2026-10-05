#!/usr/bin/env bash
# Reproducible bounded prototype. A fresh branch name is mandatory on rerun.
set -euo pipefail
cd "$(dirname "$0")"
: "${NG_ENV_PREFIX:=/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph}"
export PYTHON="${NG_ENV_PREFIX}/bin/python" RSCRIPT="${NG_ENV_PREFIX}/bin/Rscript"
export NG_BRANCH="${NG_BRANCH:-mvp_$(date -u +%Y%m%dT%H%M%SZ)}"
export NG_LOG_SCOPE="$NG_BRANCH" NG_ABUNDANCE_MODE="${NG_ABUNDANCE_MODE:-hybrid_aggregated_tad_then_read}" NG_MIN_READS_GATE=100
export NG_PREVALENCE_THRESHOLDS=10 NG_PRIMARY_THRESHOLD=10 NG_SITE_GRAPH_METHODS=pearson
export NG_GRAPH_TOP_VARIABLE_TAXA=2000 NG_MODULE_K_MIN=6
if [[ "$NG_ABUNDANCE_MODE" == hybrid_aggregated_tad_then_read ]]; then
  export NG_TAD_SUPPORTED_ONLY="${NG_TAD_SUPPORTED_ONLY:-false}"
else
  export NG_TAD_SUPPORTED_ONLY="${NG_TAD_SUPPORTED_ONLY:-true}"
fi
export NG_TRAIN_EPOCHS="${NG_TRAIN_EPOCHS:-30}" OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
"$PYTHON" scripts/ngraph_import_kg_feedstock.py
export NG_RUNTIME_COMMAND="bash run_mvp.sh $*"
"$PYTHON" scripts/ngraph_run_manifest.py --branch "$NG_BRANCH" --status started
trap '"$PYTHON" scripts/ngraph_run_manifest.py --branch "$NG_BRANCH" --status failed' ERR
bash run_pipeline.sh "$@"
if [[ " $* " == *" --stop "* ]]; then
  "$PYTHON" scripts/ngraph_run_manifest.py --branch "$NG_BRANCH" --status partial_completed
else
  "$PYTHON" scripts/ngraph_validate_kg_substrate.py --branch "$NG_BRANCH"
  "$RSCRIPT" tests/test_proxy_matching.R
  "$PYTHON" scripts/ngraph_validate_mvp.py --branch "$NG_BRANCH"
  "$RSCRIPT" tests/verify_filtering.R
  "$PYTHON" scripts/ngraph_run_manifest.py --branch "$NG_BRANCH" --status completed
fi
