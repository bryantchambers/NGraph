"""Reject incompatible definitions, scope and independent carrier witnesses."""
import hashlib
from pathlib import Path
import sys
import unittest
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ngraph_validate_functional_graph import validate_functional_graph
from test_functional_paths import SCOPE


def graph():
    nodes = [dict(node_id=n, node_type=t, **SCOPE) for n, t in
             [('M', 'Module'), ('A', 'ModuleFunctionalAssociation'), ('F', 'FunctionalFeature'),
              ('RUN', 'AnalysisRun'), ('C', 'FunctionalConcept')]]
    nodes[1]['evidence_scope'] = 'recorded_annotation_catalog'
    nodes[2].update(definition_expression='K00001', definition_sha256=hashlib.sha256(b'K00001').hexdigest())
    edges = []
    def edge(a, p, b):
        edges.append(dict(source_id=a, edge_type=p, target_id=b))
    edge('M', 'module_has_functional_association', 'A')
    edge('A', 'association_with_function', 'F')
    edge('A', 'association_derived_from_analysis', 'RUN')
    edge('F', 'functional_feature_has_concept', 'C')
    for i in range(5):
        nodes += [dict(node_id=f'T{i}', node_type='Taxon'),
                  dict(node_id=f'R{i}', node_type='ReferenceFunctionalAnnotation', genome_id=f'G{i}',
                       source_file='evidence.tsv', gene_ids=f'gene{i}', ko_ids='K00001', **SCOPE),
                  dict(node_id=f'G{i}', node_type='ReferenceGenome', genome_id=f'G{i}', **SCOPE)]
        edge(f'T{i}', 'taxon_member_of_module', 'M')
        edge(f'T{i}', 'taxon_has_reference_annotation', f'R{i}')
        edge('A', 'association_supported_by_annotation', f'R{i}')
        edge(f'R{i}', 'annotation_supports_function', 'F')
        edge(f'R{i}', 'annotation_from_reference', f'G{i}')
    return nodes, edges


class FunctionalSemanticsTests(unittest.TestCase):
    def validate(self, nodes, edges):
        return validate_functional_graph(pd.DataFrame(nodes), pd.DataFrame(edges))

    def test_valid_assertion(self):
        self.assertEqual(self.validate(*graph())['status'], 'passed')

    def test_incompatible_definition_or_analysis(self):
        for node, attribute, value in [('F', 'definition_expression', 'K00002'),
                                       ('RUN', 'db_snapshot', 'other'), ('M', 'method', 'spearman')]:
            nodes, edges = graph()
            next(n for n in nodes if n['node_id'] == node)[attribute] = value
            with self.subTest(node=node), self.assertRaises(ValueError):
                self.validate(nodes, edges)

    def test_witness_scope_ownership_and_reference(self):
        for mutation in ['scope', 'ownership', 'reference']:
            nodes, edges = graph()
            if mutation == 'scope':
                next(n for n in nodes if n['node_id'] == 'R0')['threshold'] = 'prev_5'
            else:
                edges = [e for e in edges if not (e['source_id'] == ('T0' if mutation == 'ownership' else 'R0')
                         and e['edge_type'] == ('taxon_member_of_module' if mutation == 'ownership' else 'annotation_from_reference'))]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.validate(nodes, edges)

    def test_aliases_cannot_supply_independent_reference_count(self):
        nodes, edges = graph()
        for n in nodes:
            if n.get('genome_id') == 'G4':
                n['genome_id'] = 'G0'
        with self.assertRaisesRegex(ValueError, 'five independent'):
            self.validate(nodes, edges)


if __name__ == '__main__':
    unittest.main()
