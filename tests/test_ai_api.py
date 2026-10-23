"""HTTP command boundary tests, fake model only; no .env or network requests."""
import httpx
from fastapi.testclient import TestClient

from test_ai import call, response
from test_analysis import PackageCase
from backend.ai import AnalysisAI, Gateway, Settings
from backend.app import create_app


class AIAPITests(PackageCase):
    def test_status_is_local_only_and_reports_budget_and_busy_without_secrets(self):
        def no_network(request):
            self.fail("Reading local status must never contact Gateway")
        transport = self.enterContext(httpx.Client(transport=httpx.MockTransport(no_network)))
        service = AnalysisAI(Gateway(Settings("never-return-this-key", "synthetic", 2), client=transport))
        client = self.enterContext(TestClient(create_app(self.package, ai_service=service), base_url="http://127.0.0.1"))
        self.assertEqual(client.get("/api/ai/status").json(), {
            "enabled": True, "model": "synthetic", "remaining_process_requests": 2, "busy": False})
        self.assertEqual(service.gateway.used, 0)
        service.gateway.used = 2
        service.busy.acquire()
        try:
            result = client.get("/api/ai/status")
            self.assertEqual(result.json(), {"enabled": False, "model": "synthetic", "remaining_process_requests": 0, "busy": True})
            self.assertNotIn("never-return-this-key", result.text)
        finally:
            service.busy.release()

    def test_command_route_runs_fake_model_and_existing_analysis(self):
        packets = [response([call()]), response([{"type": "message", "content": [
            {"type": "output_text", "text": '{"answer":"두 영역의 신호 관계와 구조를 비교했습니다.","used_fact_ids":["call_1.comparison"]}'}]}])]
        gateway_client = self.enterContext(httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=packets.pop(0)))))
        service = AnalysisAI(Gateway(Settings("fake", "synthetic", 2), client=gateway_client))
        client = self.enterContext(TestClient(create_app(self.package, ai_service=service), base_url="http://127.0.0.1"))
        result = client.post("/api/ai/chat", json={"command": "좌우 비교해줘"})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["results"][0]["data"]["analysis"], "compare_regions")
        self.assertFalse(result.json()["screen_applied"])
        self.assertEqual(result.json()['status'], 'ok')
        self.assertEqual(client.post("/api/ai/chat", json={"command": "다시 비교"}).status_code, 503)

    def test_disabled_invalid_cross_origin_and_busy_never_send(self):
        def no_network(request):
            self.fail("Gateway must not be contacted")
        gateway_client = self.enterContext(httpx.Client(transport=httpx.MockTransport(no_network)))
        service = AnalysisAI(Gateway(Settings("", "", 0), client=gateway_client))
        client = self.enterContext(TestClient(create_app(self.package, ai_service=service), base_url="http://127.0.0.1"))
        self.assertEqual(client.post("/api/ai/chat", json={"command": "비교"}).status_code, 503)
        for body in ({"command": ""}, {"command": "x" * 601}, {"command": "비교", "key": "do-not-echo"},
                     {"command": "비교", "context": {"selected_region_ids": [True]}}):
            result = client.post("/api/ai/chat", json=body)
            self.assertEqual(result.status_code, 422)
            self.assertNotIn("do-not-echo", result.text)
        self.assertEqual(client.post("/api/ai/chat", json={"command": "비교"}, headers={"Origin": "https://evil.example"}).status_code, 403)
        service.busy.acquire()
        try:
            self.assertEqual(client.post("/api/ai/chat", json={"command": "비교"}).status_code, 409)
        finally:
            service.busy.release()
