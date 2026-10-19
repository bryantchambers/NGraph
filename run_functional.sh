#!/usr/bin/env bash
# Offline functional analysis; no package installation or database downloads.
set -euo pipefail
PROJ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/python}"
RSCRIPT="${RSCRIPT:-/maps/projects/caeg/people/gfx654/miniforge3/envs/ngraph/bin/Rscript}"
: "${NG_BRANCH:?Set NG_BRANCH to a completed repaired discovery run}"
: "${NG_FUNCTIONAL_REFERENCE_SNAPSHOT:?Set the reference snapshot identifier}"
: "${NG_FUNCTIONAL_SNAPSHOT:?Set a new immutable analysis snapshot identifier}"
export NG_BRANCH
mkdir -p "${PROJ}/logs/${NG_BRANCH}"
"${RSCRIPT}" "${PROJ}/scripts/16_ngraph_functional_inputs.R"
"${PYTHON}" "${PROJ}/scripts/18_ngraph_catalog_enrichment.py" \
  --branch "${NG_BRANCH}" --reference-snapshot "${NG_FUNCTIONAL_REFERENCE_SNAPSHOT}" \
  --snapshot "${NG_FUNCTIONAL_SNAPSHOT}" --threshold "${NG_PRIMARY_THRESHOLD:-prev_10}" \
  --method "${NG_FUNCTIONAL_METHOD:-pearson}" --bootstraps "${NG_FUNCTIONAL_BOOTSTRAPS:-200}"
"${PYTHON}" "${PROJ}/scripts/ngraph_functional_kg.py" --no-activate \
  --branch "${NG_BRANCH}" --snapshot "${NG_FUNCTIONAL_SNAPSHOT}" \
  --threshold "${NG_PRIMARY_THRESHOLD:-prev_10}" --method "${NG_FUNCTIONAL_METHOD:-pearson}" > "${PROJ}/logs/${NG_BRANCH}/functional_projection_candidate.json"
CANDIDATE_SNAPSHOT=$("${PYTHON}" -c 'import json,sys; print(json.load(open(sys.argv[1]))["kg_snapshot_id"])' "${PROJ}/logs/${NG_BRANCH}/functional_projection_candidate.json")
"${PYTHON}" "${PROJ}/scripts/ngraph_validate_kg_substrate.py" --branch "${NG_BRANCH}" --snapshot "${CANDIDATE_SNAPSHOT}"
"${PYTHON}" "${PROJ}/scripts/ngraph_kg_snapshots.py" --branch "${NG_BRANCH}" --activate "${CANDIDATE_SNAPSHOT}"
