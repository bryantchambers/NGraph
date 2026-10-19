"""Provider HTTP success must not turn partial JSON into a displayed answer."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ngraph_llm_adapter import GeminiConfig, call_gemini
from ngraph_rag_orchestrator import augment_result


class GeminiResponseIntegrityTests(unittest.TestCase):
    def response(self, text, finish="STOP", candidates=True):
        raw = {"candidates": [{"finishReason": finish, "content": {"parts": [{"text": text}]}}]} if candidates else {}
        transport = MagicMock()
        transport.__enter__.return_value.read.return_value = json.dumps(raw).encode()
        with patch("ngraph_llm_adapter.urllib.request.urlopen", return_value=transport):
            return call_gemini("Question", config=GeminiConfig(api_key="fixture"))

    def test_truncated_json_is_not_success(self):
        result = self.response('{"answer":"unfinished', "MAX_TOKENS")
        self.assertEqual(result["status"], "output_truncated")
        self.assertEqual(result["finish_reason"], "MAX_TOKENS")

    def test_token_limit_even_with_parseable_json_is_incomplete(self):
        self.assertEqual(self.response('{"answer":"partial"}', "MAX_TOKENS")["status"], "output_truncated")

    def test_malformed_output_is_not_success(self):
        self.assertEqual(self.response('{"answer":')["status"], "invalid_json")

    def test_empty_output_is_not_success(self):
        self.assertEqual(self.response("", candidates=False)["status"], "empty_response")

    def test_blocked_generation_is_not_success(self):
        self.assertEqual(self.response("", "SAFETY")["status"], "generation_stopped")

    def test_complete_response_is_parsed(self):
        result = self.response('{"answer":"supported answer"}')
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["json"]["answer"], "supported answer")

    def test_response_schema_is_sent_to_provider(self):
        schema=dict(type='OBJECT',properties=dict(evidence_ids=dict(type='ARRAY',items=dict(type='STRING',enum=['card:exact']))))
        transport=MagicMock()
        transport.__enter__.return_value.read.return_value=b'{"candidates":[]}'
        with patch('ngraph_llm_adapter.urllib.request.urlopen',return_value=transport) as request:
            call_gemini('Question',config=GeminiConfig(api_key='fixture',response_schema=schema))
        sent=json.loads(request.call_args.args[0].data)
        self.assertEqual(sent['generationConfig']['responseSchema'],schema)

    def test_general_synthesis_keeps_local_answer_on_truncation(self):
        response = dict(status="output_truncated", text='{"answer":"unfinished', json=None, finish_reason="MAX_TOKENS")
        with patch("ngraph_rag_orchestrator.call_gemini", return_value=response):
            result = augment_result("Question", {"answer_lines": ["local evidence"]}, {}, llm_provider="gemini")
        self.assertEqual(result["llm_answer"], "")
        self.assertEqual(result["answer_lines"], ["local evidence"])
        self.assertEqual(result["llm_status"], "output_truncated")

    def test_general_synthesis_requires_answer_contract(self):
        with patch("ngraph_rag_orchestrator.call_gemini", return_value=dict(status="ok", text="[]", json=[])):
            result = augment_result("Question", {}, {}, llm_provider="gemini")
        self.assertEqual(result["llm_status"], "invalid_response")
        self.assertEqual(result["llm_answer"], "")


if __name__ == "__main__":
    unittest.main()
