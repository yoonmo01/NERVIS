"""Synthetic data, fake credentials and MockTransport only. Never calls BAZE."""
import json
import os
from unittest.mock import patch

import httpx

from test_analysis import PackageCase
from backend.schemas import RequestModel
from backend.ai import AIError, AnalysisAI, Gateway, Settings, TOOL_MODELS


def call(name="compare_regions", arguments=None, call_id="call_1"):
    return {"type": "function_call", "name": name, "call_id": call_id,
            "arguments": json.dumps(arguments or {"region_a": 1, "region_b": 11})}


def response(output, **extra):
    return {"status": "completed", "output": output, "usage": {"input_tokens": 10, "output_tokens": 5}, **extra}


class AITests(PackageCase):
    def make_ai(self, packets, budget=2):
        self.requests = []

        def handler(request):
            self.requests.append(request)
            packet = packets.pop(0)
            if isinstance(packet, Exception):
                raise packet
            return httpx.Response(200, json=packet)

        client = self.enterContext(httpx.Client(transport=httpx.MockTransport(handler)))
        gateway = Gateway(Settings("fake-test-key", "synthetic-model", budget), client=client)
        return AnalysisAI(gateway)

    def test_tool_loop_sends_only_approved_summary_and_validates_grounded_answer(self):
        ai = self.make_ai([response([call()]), response([{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps({"answer": "두 신호가 같은 방향으로 변했습니다.", "used_fact_ids": ["call_1.comparison"]})}]}])])
        result = ai.run(self.load(), "전전두피질의 좌우를 비교해줘", {})
        self.assertEqual(result["results"][0]["data"]["analysis"], "compare_regions")
        from backend.analysis import compare_regions
        self.assertEqual(result["results"][0]["data"], compare_regions(self.load(), 1, 11))
        self.assertEqual(result["gateway_requests"], 2)
        self.assertEqual(result["model_acknowledgement"], "두 신호가 같은 방향으로 변했습니다.")
        second = json.loads(self.requests[1].content)
        feedback = next(x for x in second["input"] if x.get("type") == "function_call_output")
        summary = json.loads(feedback["output"])
        self.assertIn('call_1.comparison', summary['facts'])
        self.assertEqual(summary['facts']['call_1.comparison']['correlation'], result['results'][0]['data']['correlation'])
        outbound = b"".join(r.content for r in self.requests).decode()
        for forbidden in ('"bold": [', '"zscore": [', '"samples": [', '"t1_path"', '"mask_path"'):
            self.assertNotIn(forbidden, outbound)
        self.assertFalse(second["store"])
        self.assertEqual(second["tool_choice"], "none")

    def test_invalid_fact_references_or_unstructured_explanation_preserve_local_result(self):
        for text in ('완료', json.dumps({'answer': '설명', 'used_fact_ids': ['made-up']})):
            ai = self.make_ai([response([call()]), response([{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}])])
            result = ai.run(self.load(), '비교', {})
            self.assertEqual(result['status'], 'partial')
            self.assertEqual(result['warning'], 'invalid_grounded_explanation')
            self.assertIsNone(result['model_acknowledgement'])
            self.assertEqual(len(result['results']), 1)

    def test_unlimited_app_mode_and_disabled_mode_do_not_repurpose_legacy_zero(self):
        enabled = Settings('fake', 'synthetic', None, enabled=True)
        self.assertIsNone(enabled.max_requests)
        gateway = Gateway(enabled, client=self.enterContext(httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response([]))))))
        for _ in range(12):
            gateway.send('responses/', {})
        self.assertEqual(gateway.used, 12)
        disabled = Gateway(Settings('fake', 'synthetic', None, enabled=False))
        with self.assertRaises(AIError):
            disabled.send('responses/', {})

    def test_activation_flag_migration_and_test_override_are_explicit(self):
        file = self.package.parent / 'fake-settings.env'
        file.write_text('BAZE_API_KEY=fake\nNERVIS_LLM_MODEL=synthetic\nNERVIS_AI_MAX_REQUESTS=0\n', encoding='utf-8')
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(Settings.load(file).active)
            file.write_text(file.read_text()+'NERVIS_AI_ENABLED=true\n', encoding='utf-8')
            self.assertTrue(Settings.load(file).active)
            self.assertIsNone(Settings.load(file).max_requests)
            self.assertEqual(Settings.load(file, max_requests=2).max_requests, 2)
            self.assertEqual(Settings.load(file, max_requests=2).active, True)
            file.write_text(file.read_text().replace('ENABLED=true', 'ENABLED=false'), encoding='utf-8')
            self.assertFalse(Settings.load(file).active)
            file.write_text(file.read_text().replace('ENABLED=false', 'ENABLED=invalid'), encoding='utf-8')
            with self.assertRaises(ValueError):
                Settings.load(file)

    def test_detailed_summary_does_not_transmit_series_or_image_metadata(self):
        ai = self.make_ai([response([call('analyze_regions_detailed')]), response([])])
        result = ai.run(self.load(), '전전두피질 자세히', {})
        feedback = json.loads(json.loads(self.requests[1].content)['input'][-1]['output'])
        self.assertIn('call_1.pca', feedback['facts'])
        text = json.dumps(feedback)
        for field in ('"comparison":', '"bold": [', '"samples":', '"t1_path"', '"color_rgb"'):
            self.assertNotIn(field, text)
        self.assertEqual(result['results'][0]['tool'], 'analyze_regions_detailed')

    def test_registry_uses_strict_models(self):
        self.assertTrue(issubclass(TOOL_MODELS["compare_regions"], RequestModel))

    def test_receipts_keep_only_numeric_usage_and_billing(self):
        ai = self.make_ai([response([], billing={"deducted_credit": 0.01, "unexpected": "do-not-store"},
                                    usage={"input_tokens": 10, "unexpected": "do-not-store"})])
        ai.run(self.load(), "설명해줘", {})
        self.assertEqual(ai.gateway.receipts[0]["usage"], {"input_tokens": 10})
        self.assertEqual(ai.gateway.receipts[0]["billing"], {"deducted_credit": 0.01})
        self.assertNotIn("do-not-store", json.dumps(ai.gateway.receipts))

    def test_untrusted_calls_rejected_before_any_execution(self):
        invalid = [call("exec"), call(arguments={"region_a": True, "region_b": 11}),
                   call(arguments={"region_a": 1, "region_b": 11, "path": ".env"}),
                   call(arguments={"region_a": 21, "region_b": 11})]
        for item in invalid:
            with self.subTest(item=item), patch("backend.ai.analysis.compare_regions") as execute:
                ai = self.make_ai([response([call(), item])])
                with self.assertRaises(AIError):
                    ai.run(self.load(), "비교해줘", {})
                execute.assert_not_called()
                self.assertEqual(len(self.requests), 1)

    def test_duplicate_ids_and_excess_calls_stop(self):
        for calls in ([call(), call()], [call(call_id=str(i)) for i in range(7)]):
            ai = self.make_ai([response(calls)])
            with self.assertRaises(AIError):
                ai.run(self.load(), "비교해줘", {})
            self.assertEqual(len(self.requests), 1)

    def test_budget_disabled_exhaustion_and_failed_attempts_are_counted(self):
        ai = self.make_ai([], budget=0)
        with self.assertRaises(AIError):
            ai.run(self.load(), "비교해줘", {})
        self.assertEqual(self.requests, [])
        ai = self.make_ai([httpx.ReadTimeout("private-provider-body")], budget=1)
        for _ in range(2):
            with self.assertRaises(AIError) as error:
                ai.run(self.load(), "비교해줘", {})
            self.assertNotIn("private-provider-body", str(error.exception))
        self.assertEqual(len(self.requests), 1)

    def test_second_response_cannot_start_another_tool_round(self):
        ai = self.make_ai([response([call()]), response([call(call_id="call_2")])])
        result = ai.run(self.load(), "비교해줘", {})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["warning"], "unexpected_additional_tool_round")
        self.assertEqual(len(self.requests), 2)

    def test_failed_acknowledgement_keeps_completed_results_local(self):
        ai = self.make_ai([response([call()]), httpx.ReadTimeout("not-logged")])
        result = ai.run(self.load(), "비교해줘", {})
        self.assertEqual(result["status"], "partial")
        self.assertEqual(len(result["results"]), 1)
        self.assertIsNone(result["model_acknowledgement"])
        self.assertEqual(result["gateway_requests"], 2)

    def test_bad_provider_status_and_json_are_not_executed(self):
        for packet in (response([call()], status="incomplete"), {"output": "bad"}):
            ai = self.make_ai([packet])
            with self.assertRaises(AIError):
                ai.run(self.load(), "비교해줘", {})

    def test_malformed_message_rejected_before_tools_execute(self):
        ai = self.make_ai([response([call(), {"type": "message", "content": "invalid"}])])
        with patch("backend.ai.analysis.compare_regions") as execute:
            with self.assertRaises(AIError):
                ai.run(self.load(), "비교해줘", {})
            execute.assert_not_called()

    def test_gateway_rejects_different_destination_and_too_large_budget(self):
        for url in ("https://example.com", "http://factchat-cloud.mindlogic.ai/v1/gateway",
                    "https://factchat-cloud.mindlogic.ai.evil/v1/gateway"):
            with self.assertRaises(ValueError):
                Settings("fake", "synthetic", 2, base_url=url)
        with self.assertRaises(ValueError):
            Settings("fake", "synthetic", 1000)
