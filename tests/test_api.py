"""HTTP boundary tests use synthetic packages, never supplied data or keys."""
import json
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from test_analysis import PackageCase


class ApiTests(PackageCase):
    def setUp(self):
        super().setUp()
        from backend.app import create_app
        self.app = create_app(self.package)
        self.client = self.enterContext(TestClient(self.app, base_url="http://127.0.0.1"))

    def test_health_summary_regions_and_openapi(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        summary = self.client.get("/api/dataset").json()
        self.assertEqual(summary["region_count"], 20)
        self.assertEqual(summary["sample_count"], 200)
        regions = self.client.get("/api/regions").json()["regions"]
        self.assertEqual([r["label_id"] for r in regions], list(range(1, 21)))
        region = self.client.get("/api/regions/1").json()["region"]
        self.assertEqual(region["contralateral_id"], 11)
        self.assertIn("/api/analysis/compare", self.client.get("/openapi.json").json()["paths"])

    def test_all_analysis_routes_match_local_functions(self):
        from backend import analysis
        data = self.app.state.dataset
        cases = [("timeseries", {"region_ids": [2, 1], "start": 11, "end": 20}, analysis.get_timeseries),
                 ("compare", {"region_a": 1, "region_b": 2, "method": "spearman"}, analysis.compare_regions),
                 ("pairs", {"scope": "homologous", "limit": 3}, analysis.find_similar_pairs),
                 ("windows", {"region_a": 1, "region_b": 2, "window": 40}, analysis.analyze_pair_over_windows),
                 ("detailed", {"region_a": 1, "region_b": 11, "start": 51, "end": 150, "window": 40, "step": 5}, analysis.analyze_regions_detailed)]
        for route, body, function in cases:
            with self.subTest(route=route):
                response = self.client.post(f"/api/analysis/{route}", json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json(), function(data, **body))

    def test_constant_interval_is_successful_unavailable_result(self):
        response = self.client.post("/api/analysis/compare", json={"region_a": 1, "region_b": 4, "start": 1, "end": 50})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "unavailable")
        self.assertIsNone(response.json()["correlation"])
        json.dumps(response.json(), allow_nan=False)

    def test_integer_types_and_unknown_fields_are_not_coerced(self):
        for value in (True, 1.0, "1", 0, 21):
            with self.subTest(value=value):
                response = self.client.post("/api/analysis/compare", json={"region_a": value, "region_b": 2})
                self.assertEqual(response.status_code, 422)
        response = self.client.post("/api/analysis/compare", json={"region_a": 1, "region_b": 2, "secret": "do-not-echo-this"})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn("do-not-echo-this", response.text)

    def test_invalid_ranges_pairs_windows_and_methods(self):
        cases = [("timeseries", {"region_ids": []}), ("timeseries", {"region_ids": [1, 1]}),
                 ("timeseries", {"region_ids": [1], "start": 20, "end": 10}),
                 ("timeseries", {"region_ids": [1], "end": 201}),
                 ("compare", {"region_a": 1, "region_b": 1}),
                 ("compare", {"region_a": 1, "region_b": 2, "end": 2}),
                 ("compare", {"region_a": 1, "region_b": 2, "method": "bad"}),
                 ("pairs", {"scope": "homologous", "limit": 11}),
                 ("pairs", {"limit": True}), ("pairs", {"end": 2}),
                 ("windows", {"region_a": 1, "region_b": 2, "end": 40}),
                 ("windows", {"region_a": 1, "region_b": 2, "step": 0}),
                 ("detailed", {"region_a": 1, "region_b": 2, "end": 3, "step": 10}),
                 ("detailed", {"region_a": 1, "region_b": 2, "window": 201})]
        for route, body in cases:
            with self.subTest(route=route, body=body):
                self.assertEqual(self.client.post(f"/api/analysis/{route}", json=body).status_code, 422)
        for region_id in ("1.0", "true", "21", "0"):
            self.assertEqual(self.client.get(f"/api/regions/{region_id}").status_code, 422)
        self.assertEqual(self.client.get("/api/regions/1/slices?orientation=bad").status_code, 422)

    def test_slice_lookup_and_registered_images(self):
        result = self.client.get("/api/regions/1/slices").json()
        self.assertEqual(len(result["slices"]), 15)
        for kind in ("t1", "mask"):
            response = self.client.get(f"/api/slices/Axial/2/{kind}")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"], "image/png")
            key = "t1_path" if kind == "t1" else "mask_path"
            self.assertEqual(response.content, (self.package / result["slices"][0][key]).read_bytes())

    def test_unknown_files_are_not_served_and_changed_image_is_rejected(self):
        for route in ("/api/slices/Axial/999/t1", "/.env", "/manifest.json", "/data/processed/nervis_v1/manifest.json"):
            self.assertEqual(self.client.get(route).status_code, 404)
        self.assertEqual(self.client.get("/api/slices/Axial/2/manifest").status_code, 422)
        path = self.package / "slices/Axial/axial_voxel_002.png"
        path.write_bytes(b"changed synthetic image")
        self.assertEqual(self.client.get("/api/slices/Axial/2/t1").status_code, 409)

    def test_cors_and_host_boundaries(self):
        allowed = self.client.get("/api/dataset", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(allowed.headers["access-control-allow-origin"], "http://localhost:5173")
        rejected = self.client.get("/api/dataset", headers={"Origin": "https://example.com"})
        self.assertNotIn("access-control-allow-origin", rejected.headers)
        self.assertEqual(self.client.get("/api/health", headers={"Host": "example.com"}).status_code, 400)


class ApiLifecycleTests(PackageCase):
    def test_startup_loads_once_and_corrupt_package_fails(self):
        from backend.app import create_app
        from backend.data import load_dataset
        app = create_app(self.package)
        with patch("backend.app.load_dataset", wraps=load_dataset) as loader:
            self.assertEqual(loader.call_count, 0)
            with TestClient(app, base_url="http://127.0.0.1") as client:
                for _ in range(3):
                    self.assertEqual(client.get("/api/dataset").status_code, 200)
                self.assertEqual(loader.call_count, 1)
        self.assertFalse(hasattr(app.state, "dataset"))
        (self.package / "signals.npz").write_bytes(b"corrupt synthetic input")
        with self.assertRaises(RuntimeError):
            with TestClient(create_app(self.package), base_url="http://127.0.0.1"):
                pass
