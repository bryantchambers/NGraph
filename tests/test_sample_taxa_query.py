"""Standalone core/age rankings must escape functional follow-up resolution."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_functional_query import FunctionalQuery,words
from test_functional_query_integration import App
from ngraph_rag_orchestrator import build_retrieval_bundle,validate_general_synthesis
spec=importlib.util.spec_from_file_location('sample_query_engine',Path(__file__).resolve().parents[1]/'scripts/13_ngraph_query_engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
QUESTION='If I was seeding a new environment similar to that found in core R1 at 150 kya, what are the top 100 taxa I would need?'

class SampleTaxaQueryTests(unittest.TestCase):
    def fixture(self):
        return dict(sample_qc=pd.DataFrame(dict(label=['a','b','outside','other'],core=['GeoB25202_R1']*3+['ST8'],age_kyr=[145.,150.,100.,150.])),sample_abundance=pd.DataFrame(dict(sample=['a','b','a','outside','other'],taxon=['S__one','S__one','S__two','S__outside','S__other'],abundance=[10.,10.,15.,1000.,2000.])),taxon_nodes=pd.DataFrame(dict(taxon=['S__one','S__two'])),cards=pd.DataFrame(columns=['card_id','card_type','entity_id']),embeddings=pd.DataFrame(),link_prediction=pd.DataFrame(),card_matrix=None,vectorizer=None)
    def result(self,q=QUESTION):
        with patch.object(engine,'semantic_context',return_value=pd.DataFrame()):return engine.build_seed_answer(q,self.fixture())
    def test_functional_context_does_not_capture_new_sample_request(self):
        backend=FunctionalQuery(App())
        context=backend.execute('functions in M3')['context']
        self.assertIsNone(backend.execute(QUESTION,context))
        self.assertNotIn('i',words(QUESTION))
        self.assertEqual(engine.choose_query_type(QUESTION),'seeding')
    def test_fixed_window_and_zero_inclusive_mean(self):
        r=self.result();self.assertEqual(r['selected_samples'],['a','b'])
        ranked=r['top_taxa'].set_index('taxon')
        self.assertEqual(ranked.loc['S__two','mean_abundance'],7.5)
        self.assertEqual(ranked.loc['S__one','mean_abundance'],10.)
        self.assertNotIn('S__outside',ranked.index)
        self.assertEqual(r['table_evidence']['returned_count'],2)
    def test_no_silent_substitution_for_empty_window_or_unknown_core(self):
        for q in ['top 100 taxa in core R1 at 900 kya','top 100 taxa in core R3 at 150 kya']:
            r=self.result(q);self.assertEqual(r['selected_samples'],[]);self.assertTrue(r['top_taxa'].empty)
    def test_zero_age_and_unit_aliases_are_preserved(self):
        for unit in ['kya','kyr','ka']:
            self.assertEqual(engine.parse_age_kya('core R1 at 0 '+unit),0.)
        self.assertEqual(self.result('top 100 taxa in core R1 at 0 kya')['age_target'],0.)
    def test_ranking_has_citable_evidence_including_selection(self):
        r=self.result();bundle=build_retrieval_bundle(QUESTION,r,self.fixture())
        cards=bundle['retrieved_cards'];self.assertEqual(cards.iloc[0].card_type,'sample_taxa_ranking')
        card=cards.iloc[0];self.assertIn('S__one',card.evidence)
        self.assertTrue(validate_general_synthesis(dict(answer='The historical ranking includes S__one.',evidence_ids=[card.card_id]),cards,{'module_system':'vgae'}))
        json.dumps(r['table_evidence'])
    def test_explicit_function_question_stays_functional(self):
        self.assertIsNotNone(FunctionalQuery(App()).execute('Which functions are associated with M3?'))
