"""Bounded typed metapaths with relation-specific degree-weighted path counts.

DWPC uses damping 0.5 on each traversed endpoint's degree for that relation
and direction. Counts are descriptive connectivity scores, not significance.
Only paths with no repeated nodes are counted. Parallel duplicate triples are
collapsed, and incomplete enumeration is explicitly labelled truncated.
"""
from collections import defaultdict
from ngraph_functional_paths import attach_proof, in_scope, CAUTION

CATALOG = {
    'site_taxon': [('site_has_sample', 1), ('sample_observed_taxon', 1)],
    'taxon_proxy': [('sample_observed_taxon', -1), ('sample_has_measurement', 1), ('measurement_of_variable', 1)],
    'site_module_bridge': [('site_has_sample', 1), ('sample_observed_taxon', 1), ('taxon_member_of_module', 1), ('taxon_member_of_module', -1), ('sample_observed_taxon', -1), ('site_has_sample', -1)],
    'shared_module': [('taxon_member_of_module', 1), ('taxon_member_of_module', -1)],
    'taxon_module_function': [('taxon_member_of_module', 1), ('module_has_functional_association', 1), ('association_with_function', 1)],
    'function_module': [('association_with_function', -1), ('module_has_functional_association', -1)],
    'function_module_taxon': [('association_with_function', -1), ('module_has_functional_association', -1), ('taxon_member_of_module', -1)],
    'module_function': [('module_has_functional_association', 1), ('association_with_function', 1)],
    'module_function_ko': [('module_has_functional_association',1),('association_with_function',1),('functional_definition_mentions_ko',1)],
    'taxon_function': [('taxon_has_reference_annotation', 1), ('annotation_supports_function', 1)],
}

class ConnectivityIndex:
    def __init__(self, nodes, edges, scope=None):
        self.scope = {k: v for k, v in (scope or {}).items() if v}
        self.nodes = {str(n['node_id']): n for n in nodes}
        self.adjacency = defaultdict(list)
        self.edge_lookup = {}
        seen = set()
        self.invalid_edges = []
        for e in edges:
            source, target, predicate = map(str, (e['source_id'], e['target_id'], e['edge_type']))
            if source not in self.nodes or (target and target not in self.nodes):
                self.invalid_edges.append(str(e['edge_id']))
                continue
            if not in_scope(e, self.scope):
                continue
            if not all(in_scope(self.nodes[n], self.scope) for n in (source, target)):
                continue
            triple = source, predicate, target
            if triple in seen:
                continue
            seen.add(triple)
            eid = str(e['edge_id'])
            self.edge_lookup[eid] = e
            self.adjacency[source, predicate, 1].append((target, eid))
            self.adjacency[target, predicate, -1].append((source, eid))
        for key in self.adjacency:
            self.adjacency[key].sort()

    def search(self, source, target, metapath, limit=20, max_paths=10000, max_expansions=100000, carriers_only=False):
        if metapath not in CATALOG:
            raise ValueError('Unknown metapath')
        if source not in self.nodes or (target and target not in self.nodes):
            return {'status': 'missing', 'source': source, 'target': target, 'paths': []}
        steps = CATALOG[metapath]
        type_rules = {'taxon_module_function': ('Taxon','FunctionalFeature'),
                      'function_module_taxon': ('FunctionalFeature','Taxon'),
                      'function_module': ('FunctionalFeature','Module'),
                      'module_function': ('Module','FunctionalFeature'),
                      'module_function_ko': ('Module','FunctionalConcept'),
                      'taxon_function': ('Taxon','FunctionalFeature')}
        if metapath in type_rules:
            source_type, target_type = type_rules[metapath]
            if self.nodes[source]['node_type'] != source_type or (target and self.nodes[target]['node_type'] != target_type):
                raise ValueError('Source/target types do not match the functional metapath')
        if carriers_only and metapath not in {'taxon_module_function', 'function_module_taxon'}:
            raise ValueError('Carrier-only filtering requires the combined functional path')
        limit = max(1, min(int(limit), 100))
        max_paths = max(1, min(int(max_paths), 100000))
        count, total, expansions, truncated = 0, 0.0, 0, False
        evidence = []
        def visit(current, offset, node_ids, edge_ids, score):
            nonlocal count, total, expansions, truncated
            if truncated:
                return
            if offset == len(steps):
                if not target or current == target:
                    path = {'nodes': node_ids, 'edges': [self.edge_lookup[e] for e in edge_ids], 'weight': score}
                    attach_proof(self, path)
                    if carriers_only and not path.get('witnesses'):
                        return
                    count += 1
                    total += score
                    if len(evidence) < limit:
                        path.update({'nodes': node_ids, 'node_details': [{k:v for k,v in self.nodes[n].items() if k in {'node_id','node_type','label','variable','value','unit','unit_status','unit_evidence','match_method','bracket_width_cm','large_gap','source_observation_ids','observation_ids','source_table','source_file','evidence_status','function_id','function_namespace','function_name','q_value','p_value','statistic','prevalence_difference','test_method','annotation_coverage','annotation_status','db_snapshot','genome_id','gene_ids','ko_ids','completeness','source_path','source_row','source_kind','functional_manifest','permutation_z_score','null_carrier_count_mean','null_carrier_count_sd','evidence_scope','branch','threshold','method','module_system','carrier_count','module_annotated_count','odds_ratio','biological_review_status','definition_sha256','definition_expression'}} for n in node_ids], 'edges': [self.edge_lookup[e] for e in edge_ids], 'weight': score})
                        evidence.append(path)
                    if count >= max_paths:
                        truncated = True
                return
            predicate, direction = steps[offset]
            adjacent = self.adjacency.get((current, predicate, direction), [])
            for neighbor, eid in adjacent:
                expansions += 1
                if expansions > max_expansions:
                    truncated = True
                    return
                if neighbor in node_ids:
                    continue
                if offset == len(steps)-1 and target and neighbor != target:
                    continue
                reverse_degree = len(self.adjacency.get((neighbor, predicate, -direction), []))
                degree_weight = (len(adjacent) * reverse_degree) ** -0.5
                visit(neighbor, offset+1, node_ids+[neighbor], edge_ids+[eid], score*degree_weight)
                if truncated:
                    return
        visit(source, 0, [source], [], 1.0)
        return {'status': 'ok', 'source': source, 'target': target, 'metapath': metapath,
                'steps': [{'predicate': p, 'direction': d} for p,d in steps],
                'path_count': count, 'dwpc': total, 'truncated': truncated,
                'count_status': 'lower_bound' if truncated else 'exact',
                'evidence_truncated': count > len(evidence), 'expansions': expansions,
                'paths': evidence, 'damping': 0.5, 'scope': self.scope, 'carriers_only': carriers_only,
                'interpretation': 'Descriptive connectivity; no null calibration or significance'}


PRESET_INFO = {
 'site_taxon': ('Core → sample → taxon', 'Site', 'Taxon', 'Observed sample connections.'),
 'taxon_proxy': ('Taxon → sample → measurement → proxy', 'Taxon', 'ProxyVariable', 'Sample-associated proxy evidence.'),
 'site_module_bridge': ('Core → taxa → module → taxa → core', 'Site', 'Site', 'Exploratory cross-core community context.'),
 'shared_module': ('Taxon → module ← taxon', 'Taxon', 'Taxon', 'Shared community membership.'),
 'module_function': ('Module → association → function', 'Module', 'FunctionalFeature', CAUTION),
 'module_function_ko': ('Module → association → function → definition KO', 'Module','FunctionalConcept','Definition components retain AND/OR/optional logic. No separate KO enrichment test.'),
 'taxon_function': ('Taxon → reference annotation → function', 'Taxon', 'FunctionalFeature', CAUTION),
 'taxon_module_function': ('Taxon → community module → association → function', 'Taxon', 'FunctionalFeature', CAUTION),
 'function_module': ('Function ← association ← community module', 'FunctionalFeature', 'Module', CAUTION),
 'function_module_taxon': ('Function ← association ← community module ← taxon', 'FunctionalFeature', 'Taxon', CAUTION),
}

def preset_catalog():
    return {k: dict(zip(('label', 'source', 'target', 'help'), PRESET_INFO[k]),
                    steps=[{'predicate': p, 'direction': d} for p, d in v]) for k, v in CATALOG.items()}
