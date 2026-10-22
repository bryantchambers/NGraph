"""Transient provider failures retry without changing evidence or hiding outages."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from ngraph_llm_adapter import GeminiConfig,call_gemini


class GeminiRetryTests(unittest.TestCase):
    def setUp(self):
        self.config=GeminiConfig(api_key='fixture',response_schema={'type':'OBJECT'})

    def test_transient_failure_recovers_with_same_request(self):
        responses=[dict(status='http_error_503'),dict(status='http_error_503'),dict(status='ok',json={'answer':'recorded evidence'})]
        with patch('ngraph_llm_adapter._call_gemini_once',side_effect=responses) as request,patch('ngraph_llm_adapter.time.sleep') as sleep:
            result=call_gemini('unchanged evidence',system_instruction='unchanged policy',config=self.config)
        self.assertEqual(result['status'],'ok');self.assertEqual(result['attempts'],3)
        self.assertEqual(result['retry_statuses'],['http_error_503','http_error_503'])
        self.assertEqual([c.args[0] for c in sleep.call_args_list],[1.,2.])
        for call in request.call_args_list:
            self.assertEqual(call.args[0],'unchanged evidence')
            self.assertEqual(call.kwargs['system_instruction'],'unchanged policy')
            self.assertEqual(call.kwargs['config'].model,self.config.model)
            self.assertEqual(call.kwargs['config'].response_schema,self.config.response_schema)
            self.assertLessEqual(call.kwargs['config'].timeout_s,self.config.timeout_s)

    def test_persistent_failure_is_bounded_and_preserved(self):
        with patch('ngraph_llm_adapter._call_gemini_once',return_value=dict(status='http_error_503')) as request,patch('ngraph_llm_adapter.time.sleep'):
            result=call_gemini('evidence',config=self.config)
        self.assertEqual(result['status'],'http_error_503');self.assertEqual(request.call_count,3)

    def test_nontransient_failure_is_not_retried(self):
        for status in ['http_error_400','http_error_401','http_error_403','http_error_429','invalid_json','output_truncated','generation_stopped']:
            with self.subTest(status=status),patch('ngraph_llm_adapter._call_gemini_once',return_value=dict(status=status)) as request,patch('ngraph_llm_adapter.time.sleep') as sleep:
                result=call_gemini('evidence',config=self.config)
                self.assertEqual(result['attempts'],1);request.assert_called_once();sleep.assert_not_called()

    def test_total_time_budget_prevents_another_attempt(self):
        with patch('ngraph_llm_adapter.time.monotonic',side_effect=[0,0,59.8]),patch('ngraph_llm_adapter.time.sleep') as sleep,patch('ngraph_llm_adapter._call_gemini_once',return_value=dict(status='http_error_503')) as request:
            result=call_gemini('evidence',config=self.config)
        self.assertEqual(result['attempts'],1);request.assert_called_once();sleep.assert_not_called()

    def test_missing_key_does_not_retry(self):
        with patch('ngraph_llm_adapter.build_config',return_value=None),patch('ngraph_llm_adapter._call_gemini_once',return_value=dict(status='missing_key')) as request:
            result=call_gemini('evidence')
        self.assertEqual(result['attempts'],0);request.assert_called_once()


if __name__=='__main__':unittest.main()
