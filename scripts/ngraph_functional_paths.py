"""Read-only functional witnesses and versioned proof rules (seed-independent)."""
from collections import defaultdict
import hashlib
import json
import re

RULE_VERSION = 'functional-rules-1'
CAUTION = ('Recorded reference functional potential; not measured activity or causality. '
           'Module membership does not establish individual functional support. '
           'Missing projected evidence does not establish biological absence.')
SCOPE_FIELDS = ('branch', 'threshold', 'method', 'module_system', 'db_snapshot')


def text_value(value):
    return '' if value is None or str(value).lower() in {'nan', 'none'} else str(value)


def in_scope(record, scope):
    return all(not text_value(record.get(k)) or text_value(record[k]) == str(v)
               for k, v in scope.items() if v and k in SCOPE_FIELDS)


def witnesses(index, taxon, association, function):
    """Join three edges using the same annotation, association and target function."""
    owned = dict(index.adjacency.get((taxon, 'taxon_has_reference_annotation', 1), []))
    found = {}
    for annotation, support_edge in index.adjacency.get((association, 'association_supported_by_annotation', 1), []):
        if annotation not in owned:
            continue
        feature_edges = dict(index.adjacency.get((annotation, 'annotation_supports_function', 1), []))
        if function not in feature_edges:
            continue
        record = index.nodes[annotation]
        reference = text_value(record.get('genome_id')) or annotation
        proof = {'annotation_id': annotation, 'genome_id': reference,
                 'annotation': record, 'edge_ids': [owned[annotation], support_edge, feature_edges[function]]}
        found.setdefault(reference, proof)  # Reference aliases are one independent witness.
    return list(found.values())


def attach_proof(index, path):
    kinds = {index.nodes[n]['node_type']: n for n in path['nodes']}
    association = kinds.get('ModuleFunctionalAssociation')
    taxon, function = kinds.get('Taxon'), kinds.get('FunctionalFeature')
    if not (association and function):
        return
    support = witnesses(index, taxon, association, function) if taxon else []
    row = index.nodes[association]
    path.update(carrier_status='not_applicable' if not taxon else 'supported_in_catalog' if support else 'outside_projected_inventory',
                witnesses=support, membership_context=bool(taxon),
                claim_kind='module_functional_association' if not taxon else 'reference_supported_contributor' if support else 'member_of_function_associated_module',
                rule_version=RULE_VERSION, interpretation=CAUTION)
    edge_ids = [edge['edge_id'] for edge in path['edges']]
    payload = [RULE_VERSION, path['nodes'], edge_ids, [w['edge_ids'] for w in support]]
    path['proof_id'] = 'proof:functional:' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
    path['association_id'] = association
    path['statistics'] = {k: row.get(k) for k in ['permutation_z_score', 'q_value', 'p_value', 'odds_ratio',
          'prevalence_difference', 'null_carrier_count_mean', 'null_carrier_count_sd', 'annotation_coverage',
          'carrier_count', 'module_annotated_count', 'annotation_status', 'evidence_scope', 'functional_manifest']}


def recognize_query(query):
    """Resolve explicit IDs into an allowlisted query; ambiguous prose stays unresolved."""
    if not re.search(r'function|functional|kegg|biosynthesis|carrier|enrich|M\d{5}', query, re.I):
        return None
    taxon = re.search(r'(?:taxon:)?(S__[\w.\-]+)', query)
    module = re.search(r'(?<!\w)(M[1-9]\d?)(?!\d)', query, re.I)
    function = re.search(r'(?<!\w)(M\d{5})(?!\d)', query, re.I)
    if not (taxon or module or function):
        return {'needs_entities': True}
    return {'source': 'taxon:' + taxon[1] if taxon else module[1].upper() if module else function[1].upper(),
            'target': function[1].upper() if function and (taxon or module) else '',
            'metapath': 'taxon_module_function' if taxon else 'module_function' if module else 'function_module_taxon' if re.search(r'taxa|taxon|carrier|species|members', query, re.I) else 'function_module',
            'carriers_only': bool(re.search(r'only.*carrier|supporting carriers|which.*carriers', query, re.I))}


def render_query(result, query):
    paths = result.get('paths', [])
    lines = [CAUTION]
    cards = []
    for path in paths:
        nodes = path['node_details']
        association = next((n for n in nodes if n['node_type'] == 'ModuleFunctionalAssociation'), {})
        taxon = next((n for n in nodes if n['node_type'] == 'Taxon'), {})
        module = next((n for n in nodes if n['node_type'] == 'Module'), {})
        function = next((n for n in nodes if n['node_type'] == 'FunctionalFeature'), {})
        phrase = f"{taxon.get('label', 'Module')} belongs to {module.get('label', module.get('node_id', ''))}; " if taxon else ''
        phrase += f"{module.get('label', 'Module')} is associated with {function.get('function_id', '')} ({function.get('label', '')})"
        phrase += f"; q={association.get('q_value')}, Z={association.get('permutation_z_score')}."
        if taxon:
            phrase += f" Individual carrier evidence: {path.get('carrier_status')} (reference potential only)."
        proof_id = path.get('proof_id', association.get('node_id', ''))
        lines.append(phrase + f' [{proof_id}]')
        cards.append({'card_id': proof_id, 'card_type': 'functional_graph_proof', 'title': phrase,
                      'summary': CAUTION, 'entity_id': association.get('node_id'), 'proof': path})
    if not paths:
        lines.append('No qualified path in the selected scope; this is not evidence of biological absence.')
    if result.get('evidence_truncated'):
        lines.append(f"Showing {len(paths)} evidence paths of {result.get('path_count')} counted paths ({result.get('count_status')}).")
    return {'query': query, 'query_type': 'functional_kg', 'answer_lines': lines,
            'markdown': '\n\n'.join(lines), 'retrieved_cards': cards, 'graph_evidence': result,
            'llm_provider': 'deterministic_kg', 'llm_status': 'rule_based', 'rule_version': RULE_VERSION}
