"""Gemini explains missing analyses without inventing results or unbounded citations."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_llm_adapter import GeminiConfig
from ngraph_rag_orchestrator import augment_result,augment_functional_result,validate_interpretation

class SynthesisRoutesTests(unittest.TestCase):
    def test_general_schema_bounds_citations_and_lists(self):
        with patch('ngraph_llm_adapter.build_config',return_value=GeminiConfig(api_key='fixture')),patch('ngraph_rag_orchestrator.call_gemini',return_value={'status':'output_truncated'}) as call:
            augment_result('Evidence?',{'answer_lines':['local']},{},llm_provider='gemini')
        props=call.call_args.kwargs['config'].response_schema['properties']
        self.assertEqual(props['evidence_ids']['maxItems'],4)
        self.assertEqual(set(props),{'answer','evidence_ids'})

    def test_climate_limitations_reach_synthesis_and_preserve_unavailable_status(self):
        result={'query':'Glacial transitions?','query_type':'climate_context','resolution_status':'analysis_unavailable','answer_lines':['No analysis computed.'],'retrieved_cards':[{'card_id':'source:mis','card_type':'metadata_semantics','evidence':{'status':'verified'}}]}
        with patch('ngraph_rag_orchestrator.augment_result',return_value=dict(result,llm_status='evidence_checked',llm_answer='No analysis computed.')) as call:
            out=augment_functional_result(result,llm_provider='gemini')
        call.assert_called_once()
        self.assertEqual(out['resolution_status'],'analysis_unavailable')
        self.assertEqual(out['retrieved_cards'],result['retrieved_cards'])
        self.assertTrue(out['llm_answer'])

    def test_local_climate_route_does_not_call_provider(self):
        result={'query_type':'climate_context','resolution_status':'analysis_unavailable','llm_status':'analysis_unavailable','retrieved_cards':[{'card_id':'source:mis'}]}
        with patch('ngraph_rag_orchestrator.call_gemini') as call:
            out=augment_functional_result(result,llm_provider='local')
        call.assert_not_called()
        self.assertEqual(out['llm_status'],'analysis_unavailable')

    def test_no_data_limitation_is_allowed_but_positive_premise_is_rejected(self):
        validate_interpretation('The supplied evidence contains no data regarding taxa cooperating during glacial transitions.')
        with self.assertRaises(ValueError):
            validate_interpretation('Taxa cooperate during glacial transitions, with no data for other periods.')

    def test_because_is_not_a_causal_biological_claim(self):
        validate_interpretation('Because only one sample was analyzed, temporal replication is unavailable.')
        with self.assertRaises(ValueError):
            validate_interpretation('Taxa cause climate changes, with no evidence for other periods.')
