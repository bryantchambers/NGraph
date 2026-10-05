"""Bounded typed metapaths with relation-specific degree-weighted path counts.

DWPC uses damping 0.5 on each traversed endpoint's degree for that relation
and direction. Counts are descriptive connectivity scores, not significance.
Only paths with no repeated nodes are counted. Parallel duplicate triples are
collapsed, and incomplete enumeration is explicitly labelled truncated.
"""
from collections import defaultdict

CATALOG = {
    'site_taxon': [('site_has_sample', 1), ('sample_observed_taxon', 1)],
    'taxon_proxy': [('sample_observed_taxon', -1), ('sample_has_measurement', 1), ('measurement_of_variable', 1)],
    'site_module_bridge': [('site_has_sample', 1), ('sample_observed_taxon', 1), ('taxon_member_of_module', 1), ('taxon_member_of_module', -1), ('sample_observed_taxon', -1), ('site_has_sample', -1)],
    'shared_module': [('taxon_member_of_module', 1), ('taxon_member_of_module', -1)],
}

class ConnectivityIndex:
    def __init__(self, nodes, edges):
        self.nodes = {str(n['node_id']): n for n in nodes}
        self.adjacency = defaultdict(list)
        self.edge_lookup = {}
        seen = set()
        self.invalid_edges = []
        for e in edges:
            source, target, predicate = map(str, (e['source_id'], e['target_id'], e['edge_type']))
            if source not in self.nodes or target not in self.nodes:
                self.invalid_edges.append(str(e['edge_id']))
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

    def search(self, source, target, metapath, limit=20, max_paths=10000, max_expansions=100000):
        if metapath not in CATALOG:
            raise ValueError('Unknown metapath')
        if source not in self.nodes or target not in self.nodes:
            return {'status': 'missing', 'source': source, 'target': target, 'paths': []}
        steps = CATALOG[metapath]
        limit = max(1, min(int(limit), 100))
        max_paths = max(1, min(int(max_paths), 100000))
        count, total, expansions, truncated = 0, 0.0, 0, False
        evidence = []
        def visit(current, offset, node_ids, edge_ids, score):
            nonlocal count, total, expansions, truncated
            if truncated:
                return
            if offset == len(steps):
                if current == target:
                    count += 1
                    total += score
                    if len(evidence) < limit:
                        evidence.append({'nodes': node_ids, 'node_details': [{k:v for k,v in self.nodes[n].items() if k in {'node_id','node_type','label','variable','value','unit','unit_status','unit_evidence','match_method','bracket_width_cm','large_gap','source_observation_ids','observation_ids','source_table','source_file','evidence_status'}} for n in node_ids], 'edges': [self.edge_lookup[e] for e in edge_ids], 'weight': score})
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
                if offset == len(steps)-1 and neighbor != target:
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
                'paths': evidence, 'damping': 0.5,
                'interpretation': 'Descriptive connectivity; no null calibration or significance'}
