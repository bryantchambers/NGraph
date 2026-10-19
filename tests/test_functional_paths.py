"""Membership does not entail function; witnesses and scope remain explicit."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ngraph_kg_connectivity import ConnectivityIndex, preset_catalog
from ngraph_functional_paths import recognize_query, render_query

SCOPE = dict(branch='demo', threshold='prev_10', method='pearson', module_system='vgae', db_snapshot='catalog')


def fixture():
    nodes = [dict(node_id=k, node_type=t, label=k, **SCOPE) for k,t in
             [('T1','Taxon'),('T2','Taxon'),('M','Module'),('A','ModuleFunctionalAssociation'),
              ('F','FunctionalFeature'),('R','ReferenceFunctionalAnnotation')]]
    nodes[3].update(q_value=.01, permutation_z_score=4.2, function_id='M00091')
    nodes[4]['function_id']='M00091';nodes[5]['genome_id']='G1'
    edges = [dict(edge_id=str(i),source_id=a,target_id=b,edge_type=p,**SCOPE) for i,(a,p,b) in enumerate([
        ('T1','taxon_member_of_module','M'),('T2','taxon_member_of_module','M'),
        ('M','module_has_functional_association','A'),('A','association_with_function','F'),
        ('T1','taxon_has_reference_annotation','R'),('A','association_supported_by_annotation','R'),
        ('R','annotation_supports_function','F')])]
    return nodes, edges


class FunctionalPathTests(unittest.TestCase):
    def test_membership_and_carrier_are_distinct(self):
        n,e=fixture(); index=ConnectivityIndex(n,e,SCOPE)
        carrier=index.search('T1','F','taxon_module_function')
        other=index.search('T2','F','taxon_module_function')
        self.assertEqual(carrier['path_count'],other['path_count'])
        self.assertEqual(carrier['paths'][0]['carrier_status'],'supported_in_catalog')
        self.assertEqual(other['paths'][0]['claim_kind'],'member_of_function_associated_module')
        self.assertFalse(other['paths'][0]['witnesses'])
        self.assertEqual(index.search('T2','F','taxon_module_function',carriers_only=True)['path_count'],0)
        self.assertIn('not measured activity',other['paths'][0]['interpretation'])
        self.assertEqual(carrier['paths'][0]['statistics']['permutation_z_score'],4.2)

    def test_reverse_and_bounded_counts(self):
        n,e=fixture();index=ConnectivityIndex(n,e,SCOPE)
        all_members=index.search('F','','function_module_taxon',limit=1)
        self.assertEqual(all_members['path_count'],2)
        self.assertTrue(all_members['evidence_truncated'])
        self.assertEqual(index.search('F','','function_module_taxon',carriers_only=True)['path_count'],1)
        self.assertEqual(index.search('F','','function_module')['path_count'],1)
        self.assertEqual(index.search('F','','function_module_taxon',max_paths=1)['count_status'],'lower_bound')
        with self.assertRaises(ValueError):index.search('M','F','taxon_module_function')

    def test_other_analysis_cannot_supply_witness(self):
        n,e=fixture();e[5]['db_snapshot']='another'
        result=ConnectivityIndex(n,e,SCOPE).search('T1','F','taxon_module_function',carriers_only=True)
        self.assertEqual(result['path_count'],0)
        self.assertEqual(ConnectivityIndex(n,e,dict(SCOPE,module_system='diffpool')).search('T1','F','taxon_module_function')['path_count'],0)

    def test_independent_witnesses_and_degree_scope(self):
        n,e=fixture();n.append(dict(n[5],node_id='Ralias'))
        e += [dict(e[4],edge_id='a1',target_id='Ralias'),dict(e[5],edge_id='a2',target_id='Ralias'),dict(e[6],edge_id='a3',source_id='Ralias')]
        result=ConnectivityIndex(n,e,SCOPE).search('T1','F','taxon_module_function')
        self.assertEqual(len(result['paths'][0]['witnesses']),1)
        self.assertAlmostEqual(result['dwpc'],2**-.5)
        # An incompatible membership must not change the relation-specific degrees.
        e.append(dict(e[1],edge_id='other',source_id='T1',db_snapshot='other'))
        self.assertAlmostEqual(ConnectivityIndex(n,e,SCOPE).search('T1','F','taxon_module_function')['dwpc'],2**-.5)

    def test_query_templates_and_proofs(self):
        q='Which functions are associated with S__3300004630_4 and M00091?'
        parsed=recognize_query(q);self.assertEqual(parsed['metapath'],'taxon_module_function')
        self.assertEqual(recognize_query('Which modules are enriched for M00091?')['metapath'],'function_module')
        self.assertEqual(recognize_query('Which supporting carriers have function M00091?')['metapath'],'function_module_taxon')
        self.assertTrue(recognize_query('What are the functional roles?')['needs_entities'])
        n,e=fixture();result=ConnectivityIndex(n,e,SCOPE).search('T2','F','taxon_module_function')
        answer=render_query(result,q)
        self.assertIn('reference',answer['markdown'])
        self.assertTrue(answer['retrieved_cards'][0]['card_id'].startswith('proof:functional:'))
        self.assertIn('taxon_module_function',preset_catalog())

if __name__=='__main__':unittest.main()
