"""Provenance checks for the legacy `mis` field, without inferring climate states."""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / 'data/metadata/metadata_v5.tsv'
STACK = ROOT / 'Source/ROCS/old/Lisiecki2005_copy.txt'


def climate_question(question):
    return bool(re.search(r'\bMIS\b|glacial|climat|transition|\bd18o\b|δ.?18|delta.?18|ice.volume', question, re.I))


def audit_mis(metadata=METADATA, stack=STACK):
    """Compare every finite, in-range source row; never extrapolate or relabel it."""
    meta = pd.read_csv(metadata, sep='\t')
    reference = pd.read_csv(stack, sep='\t', on_bad_lines='skip')
    x = pd.to_numeric(reference['Time_ka'], errors='coerce')
    y = pd.to_numeric(reference['Benthic_d18O'], errors='coerce')
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite].to_numpy(), y[finite].to_numpy()
    order = np.argsort(x); x, y = x[order], y[order]
    if not len(x) or len(np.unique(x)) != len(x):
        raise ValueError('Invalid LR04 age grid')
    ages = pd.to_numeric(meta.y_bp, errors='coerce') / 1000
    values = pd.to_numeric(meta.mis, errors='coerce')
    usable = np.isfinite(ages) & np.isfinite(values) & ages.between(x.min(), x.max())
    expected = np.interp(ages[usable], x, y)
    errors = np.abs(expected - values[usable])
    matches = errors <= 1e-8
    verified = bool(len(errors) and matches.all())
    examples = meta.loc[usable, ['label', 'core', 'y_bp', 'mis']].head(8).copy()
    examples['lr04_expected'] = expected[:len(examples)]
    result = dict(schema='metadata-semantics-1', field='mis', status='verified_lr04_interpolation' if verified else 'unresolved',
                  semantic_label='Age-interpolated LR04 benthic delta18O' if verified else 'Unresolved metadata field',
                  is_stage_number=False if verified else None, is_local_measurement=False if verified else None,
                  source_rows=len(meta), compared_rows=int(usable.sum()), matching_rows=int(matches.sum()),
                  unassessed_rows=int((~usable).sum()), max_absolute_error=float(errors.max()) if len(errors) else None,
                  interpolation='linear at y_bp / 1000, within measured stack range; no extrapolation',
                  tolerance=1e-8, units='per mil (LR04 reference scale)' if verified else None,
                  reference_parsing='Skip malformed CSV records and exclude nonfinite age/isotope values; source hashes retain exact input identity.',
                  unit_reference='https://doi.org/10.1594/PANGAEA.701576',
                  invalid_reference_rows=int((~finite).sum()),
                  source_hashes={str(Path(p).relative_to(ROOT)) if Path(p).is_relative_to(ROOT) else str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [metadata,stack]},
                  historical_usage=['Source/ROCS/scripts/10_climate_sensitivity.R:47', 'Source/ROCS/scripts/06_figures.R:45'],
                  reference_url='https://doi.org/10.1594/PANGAEA.701576',
                  examples=json.loads(examples.to_json(orient='records')),
                  limitations=['Age-derived global stack context, not a site-specific isotope measurement.',
                               'No MIS-stage boundaries, climate classes or transition windows are assigned.',
                               'No module/function climate-association analysis has been computed.'])
    return result


def climate_result(question, scope=None, entities=None):
    """Return an inspectable limitation rather than a fabricated transition analysis."""
    try:
        audit = audit_mis()
    except (OSError, ValueError, KeyError):
        audit = dict(status='unresolved', field='mis', limitations=['Climate source validation is unavailable.'])
    entities = entities or dict(modules=[], functions=[], taxa=[])
    verified = audit['status'] == 'verified_lr04_interpolation'
    lines = [
        (f"The metadata field `mis` is an age-interpolated LR04 benthic delta18O proxy, not a Marine Isotope Stage number. {audit['matching_rows']} of {audit['compared_rows']} comparable metadata rows match the local stack."
         if verified else 'The meaning of the metadata field `mis` could not be verified against its source.'),
        'Glacial/interglacial transition and MIS–function association results have not been computed. A median split of this field is not a climate transition analysis.',
        'Existing module enrichment q-values and permutation Z-scores measure reference-function overrepresentation among module members, not association with climate.',
        'Predicted network links do not establish ecological cooperation, climate adaptation or causal roles.',
    ]
    card_id = 'metadata:mis:' + hashlib.sha256(json.dumps(audit,sort_keys=True).encode()).hexdigest()[:20]
    lines.append('Inspect the metadata provenance and interpolation examples in the evidence panel. ['+card_id+']')
    scope = dict(scope or {})
    return dict(query=question, query_type='climate_context', resolution_status='analysis_unavailable',
                llm_status='analysis_unavailable', llm_provider='local', llm_answer='', scope=scope,
                entities=entities, answer_lines=lines, markdown='\n\n'.join(lines),
                retrieved_cards=[dict(card_id=card_id,card_type='metadata_semantics',title=audit.get('semantic_label','MIS metadata semantics'),
                                      summary=('Source-verified field interpretation; no climate-association test.' if verified else 'Source verification unresolved; no climate-association test.'),evidence=audit)],
                table_evidence=dict(intent='metadata semantics',rows=audit.get('examples',[]),total_count=audit.get('compared_rows',0),
                                    returned_count=len(audit.get('examples',[])),truncated=audit.get('compared_rows',0)>8,
                                    source_file='data/metadata/metadata_v5.tsv',scope=scope,entities=entities),
                context=dict(schema='functional-query-1',scope=scope,entities=entities,core='',intent='climate_context'),
                metadata_semantics=audit, synthesis_validation='deterministic_source_check')


if __name__ == '__main__':
    import argparse, logging, platform
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/reference/metadata_semantics_20261019.json')
    args=parser.parse_args()
    (ROOT/'logs').mkdir(exist_ok=True)
    logging.basicConfig(filename=ROOT/'logs/ngraph_climate_context.log',level=logging.INFO,format='%(asctime)s %(message)s')
    logging.info('Audit seed=42 Python=%s pandas=%s numpy=%s',platform.python_version(),pd.__version__,np.__version__)
    audit=audit_mis()
    audit['audit_seed']=42
    audit['source_code_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(audit,indent=2)+'\n')
    logging.info('Audit status=%s compared=%s matched=%s output=%s',audit['status'],audit['compared_rows'],audit['matching_rows'],args.output)
    print(json.dumps({k:audit[k] for k in ['status','compared_rows','matching_rows','unassessed_rows','max_absolute_error']}))
