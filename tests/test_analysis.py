"""Synthetic packages only; never copy supplied data into fixtures."""
import copy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

import numpy as np

from scripts.prepare_app_data import MANIFEST_CONTRACT, SCHEMA, dataset_version, fingerprint, slice_index, slice_record


ROOT = Path(__file__).resolve().parents[1]


def save_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def synthetic_signals():
    x = np.arange(200, dtype=float)
    values = np.column_stack([np.sin(x / (i + 2)) + x / 200 for i in range(20)])
    values[:, 0] = x
    values[:, 1] = 2 * x
    values[:, 2] = -x
    values[:50, 3] = 7
    values[:4, 4] = [1, 1, 2, 3]
    values[:4, 5] = [1, 2, 2, 3]
    return values


def make_package(path):
    path.mkdir()
    values = synthetic_signals()
    np.savez_compressed(path / "signals.npz", bold=values,
                        zscore=(values-values.mean(axis=0))/values.std(axis=0),
                        samples=np.arange(1, 201), region_ids=np.arange(1, 21))
    regions = [{"label_id": i, "hemisphere": "Left" if i <= 10 else "Right",
                "region_name": f"Synthetic_{(i-1)%10}", "name_ko": f"합성영역{(i-1)%10}",
                "color_rgb": [i, 2*i, 3*i], "thickness_mm": float(i),
                "volume_mm3": float(i*100), "contralateral_id": i+10 if i <= 10 else i-10}
               for i in range(1, 21)]
    save_json(path / "regions.json", regions)
    from scripts.prepare_app_data import display_signals
    save_json(path / "signals_display.json", display_signals(values, (values-values.mean(axis=0))/values.std(axis=0)))
    records = []
    for orientation, count in [("Axial", 16), ("Coronal", 17)]:
        for i in range(count):
            mask = np.zeros((6, 6), dtype=np.uint8)
            if i:
                mask[1:5, 1:6] = np.arange(1, 21).reshape(4, 5)
            record = slice_record(orientation, f"{orientation.lower()}_voxel_{i+1:03}.png", mask)
            for key in ("t1_path", "mask_path"):
                target = path / record[key]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"synthetic image; loader checks hashes, not pixels")
            records.append(record)
    save_json(path / "slice_index.json", slice_index(records))
    source = {"synthetic.csv": {"bytes": 1, "sha256": "0"*64}}
    script_hash = "1"*64
    manifest = {**copy.deepcopy(MANIFEST_CONTRACT), "schema_version": SCHEMA,
                "source_files": source, "generator": {"path": "scripts/prepare_app_data.py", "sha256": script_hash},
                "dataset_version": dataset_version(source, script_hash)}
    save_json(path / "manifest.json", manifest)
    refresh_hashes(path)


def refresh_hashes(path):
    manifest_path = path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = {p.relative_to(path).as_posix(): fingerprint(p)
                         for p in path.rglob("*") if p.is_file() and p != manifest_path}
    save_json(manifest_path, manifest)


class PackageCase(unittest.TestCase):
    def setUp(self):
        (ROOT / "tmp").mkdir(exist_ok=True)
        assert (ROOT / "tmp").resolve() == ROOT / "tmp"
        self.temp = tempfile.TemporaryDirectory(prefix="analysis-", dir=ROOT / "tmp")
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "package"
        make_package(self.package)

    def load(self):
        from backend.data import load_dataset
        return load_dataset(self.package)

    def change_json(self, name, edit):
        path = self.package / name
        value = json.loads(path.read_text(encoding="utf-8"))
        edit(value)
        save_json(path, value)
        if name != "manifest.json":
            refresh_hashes(self.package)


class LoaderTests(PackageCase):
    def test_load_valid_package(self):
        data = self.load()
        self.assertEqual(data.bold.shape, (200, 20))
        self.assertEqual(len(data.regions), 20)
        np.testing.assert_array_equal(data.samples, np.arange(1, 201))
        self.assertTrue(data.dataset_version)

    def test_reject_bad_hash(self):
        (self.package / "signals.npz").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            self.load()

    def test_reject_bad_shape_ids_and_normalization(self):
        path = self.package / "signals.npz"
        with np.load(path, allow_pickle=False) as values:
            original = {name: values[name] for name in values.files}
        for name, replacement in [("bold", original["bold"][None, :, :]),
                                  ("region_ids", np.arange(20)),
                                  ("samples", np.arange(200)),
                                  ("zscore", original["zscore"] + 1)]:
            with self.subTest(name=name):
                np.savez_compressed(path, **{**original, name: replacement})
                refresh_hashes(self.package)
                with self.assertRaises(ValueError):
                    self.load()

    def test_reject_bad_manifest_metadata_and_version(self):
        path = self.package / "manifest.json"
        original = path.read_bytes()
        for key, value in [("sample_interval_seconds", 2), ("dataset_version", "wrong"),
                           ("axes", ["region", "sample"]), ("schema_version", "wrong")]:
            with self.subTest(key=key):
                path.write_bytes(original)
                self.change_json("manifest.json", lambda m: m.update({key: value}))
                with self.assertRaises(ValueError):
                    self.load()

    def test_reject_duplicate_regions_and_invalid_slice_references(self):
        self.change_json("regions.json", lambda r: r[0].update(label_id=2))
        with self.assertRaises(ValueError):
            self.load()
        self.change_json("regions.json", lambda r: r[0].update(label_id=1))
        self.change_json("slice_index.json", lambda r: r["slices"][0].update(visible_region_ids=[99]))
        with self.assertRaises(ValueError):
            self.load()

    def test_reject_escaping_path(self):
        self.change_json("manifest.json", lambda m: m["files"].update({"../outside": {"bytes": 0, "sha256": "0"*64}}))
        with self.assertRaises(ValueError):
            self.load()

    def test_reject_junction_outside_package(self):
        target = Path(self.temp.name) / "outside"
        target.mkdir()
        (target / "file").write_text("synthetic", encoding="utf-8")
        alias = self.package / "escape"
        try:
            os.symlink(target, alias, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            import _winapi
            _winapi.CreateJunction(str(target), str(alias))
            self.addCleanup(alias.rmdir)
        else:
            self.addCleanup(alias.unlink)
        self.change_json("manifest.json", lambda m: m["files"].update({"escape/file": fingerprint(target / "file")}))
        with self.assertRaises(ValueError):
            self.load()

    def test_dataset_arrays_are_read_only(self):
        data = self.load()
        with self.assertRaises(ValueError):
            data.bold[0, 0] = 0
        with self.assertRaises(ValueError):
            data.zscore[0, 0] = 0


class BasicAnalysisTests(PackageCase):
    def setUp(self):
        super().setUp()
        self.data = self.load()

    def api(self):
        from backend import analysis
        return analysis

    def test_summary_region_and_structural_difference(self):
        api = self.api()
        self.assertEqual(api.get_dataset_summary(self.data)["region_count"], 20)
        self.assertEqual(api.get_region_info(self.data, 1)["region"]["contralateral_id"], 11)
        result = api.compare_regions(self.data, 1, 2)
        self.assertEqual(result["structure"]["thickness_mm"]["difference_b_minus_a"], 1)
        self.assertEqual(result["structure"]["volume_mm3"]["difference_b_minus_a"], 100)

    def test_query_boundaries_and_reject_invalid_inputs(self):
        api = self.api()
        result = api.get_timeseries(self.data, [2, 1])
        self.assertEqual(result["region_ids"], [2, 1])
        self.assertEqual(len(result["bold"]), 200)
        for start, end in [(1, 1), (200, 200), (3, 9)]:
            result = api.get_timeseries(self.data, [1], start, end)
            self.assertEqual(result["samples"], list(range(start, end+1)))
            self.assertEqual(result["bold"][0][0], start-1)
            self.assertEqual(result["zscore"][0][0], float(self.data.zscore[start-1, 0]))
        for ids in ([], [1, 1], [0], [21], [True], [1.0], ["1"], (1,)):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                api.get_timeseries(self.data, ids)
        for start, end in [(0, 2), (1, 201), (3, 2), (True, 10), (1.0, 10), (1, "3")]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                api.get_timeseries(self.data, [1], start, end)
        for a, b, start, end, method in [(1, 1, 1, 200, "pearson"), (1, 2, 1, 2, "pearson"),
                                       (1, 2, 1, 200, "unknown")]:
            with self.assertRaises(ValueError):
                api.compare_regions(self.data, a, b, start, end, method)

    def test_pearson_positive_negative_and_constant(self):
        api = self.api()
        self.assertAlmostEqual(api.compare_regions(self.data, 1, 2)["correlation"], 1)
        self.assertAlmostEqual(api.compare_regions(self.data, 1, 3)["correlation"], -1)
        result = api.compare_regions(self.data, 1, 4, 1, 50)
        self.assertEqual(result["status"], "unavailable")
        self.assertIsNone(result["correlation"])
        self.assertEqual(result["reason"], "constant_signal")

    def test_spearman_ties(self):
        self.assertAlmostEqual(self.api().compare_regions(self.data, 5, 6, 1, 4, "spearman")["correlation"], 5/6)

    def test_returns_do_not_mutate_dataset(self):
        api = self.api()
        result = api.get_region_info(self.data, 1)
        result["region"]["color_rgb"][0] = 255
        self.assertEqual(api.get_region_info(self.data, 1)["region"]["color_rgb"][0], 1)
        series = api.get_timeseries(self.data, [1])
        series["bold"][0][0] = 10000
        self.assertEqual(api.get_timeseries(self.data, [1])["bold"][0][0], 0)

    def test_json_has_no_numpy_or_nan(self):
        api = self.api()
        for result in [api.get_dataset_summary(self.data), api.get_region_info(self.data, 1),
                       api.get_timeseries(self.data, [1]), api.compare_regions(self.data, 1, 2),
                       api.compare_regions(self.data, 1, 4, 1, 4)]:
            json.dumps(result, allow_nan=False)
            for key in ("dataset_version", "analysis", "parameters", "status", "warnings"):
                self.assertIn(key, result)


class SearchAnalysisTests(PackageCase):
    def setUp(self):
        super().setUp()
        self.data = self.load()

    def test_pair_scope_order_and_ties(self):
        from backend.analysis import find_similar_pairs
        x = np.arange(200, dtype=float)
        bold = np.tile(x[:, None], (1, 20))
        bold[:, 2] = -x
        data = replace(self.data, bold=bold)
        all_pairs = find_similar_pairs(data, limit=190)
        self.assertEqual(all_pairs["candidate_pair_count"], 190)
        self.assertEqual(len(all_pairs["pairs"]), 190)
        identities = [(r["region_a"], r["region_b"]) for r in all_pairs["pairs"]]
        self.assertEqual(len(set(identities)), 190)
        self.assertEqual(identities[:2], [(1, 2), (1, 4)])
        low = find_similar_pairs(data, order="ascending", limit=1)["pairs"][0]
        self.assertEqual((low["region_a"], low["region_b"]), (1, 3))
        homologous = find_similar_pairs(data, scope="homologous", limit=10)
        self.assertEqual(homologous["candidate_pair_count"], 10)
        self.assertTrue(all(r["region_b"] == r["region_a"]+10 for r in homologous["pairs"]))
        json.dumps(homologous, allow_nan=False)
        for kwargs in ({"scope": "bad"}, {"order": "bad"}, {"limit": 0}, {"limit": True},
                       {"scope": "homologous", "limit": 11}, {"end": 2}, {"method": "bad"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                find_similar_pairs(data, **kwargs)

    def test_pair_search_skips_constants_without_fabricating_zero(self):
        from backend.analysis import find_similar_pairs
        result = find_similar_pairs(self.data, start=1, end=50, limit=190)
        self.assertEqual(len(result["unavailable_pairs"]), 19)
        self.assertEqual(len(result["pairs"]), 171)
        self.assertTrue(all(p["correlation"] is None for p in result["unavailable_pairs"]))

    def test_window_boundaries_and_unavailable_windows(self):
        from backend.analysis import analyze_pair_over_windows
        result = analyze_pair_over_windows(self.data, 1, 2)
        self.assertEqual(len(result["windows"]), 16)
        self.assertEqual((result["windows"][0]["start_sample"], result["windows"][0]["end_sample"]), (1, 50))
        self.assertEqual((result["windows"][-1]["start_sample"], result["windows"][-1]["end_sample"]), (151, 200))
        partial = analyze_pair_over_windows(self.data, 1, 2, 11, 171)
        self.assertEqual(len(partial["windows"]), 12)
        self.assertEqual(partial["windows"][-1]["end_sample"], 170)
        constant = analyze_pair_over_windows(self.data, 1, 4, 1, 50)
        self.assertEqual(constant["status"], "unavailable")
        self.assertIsNone(constant["min_correlation"])
        self.assertIsNone(constant["max_correlation"])
        self.assertIsNone(constant["windows"][0]["correlation"])
        json.dumps(constant, allow_nan=False)
        for kwargs in ({"window": 201}, {"window": 2}, {"window": True}, {"step": 0},
                       {"step": 201}, {"method": "bad"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze_pair_over_windows(self.data, 1, 2, **kwargs)

    def test_region_slices_and_missing_visibility(self):
        from backend.analysis import get_region_slices
        result = get_region_slices(self.data, 1)
        self.assertEqual(len(result["slices"]), 15)
        self.assertEqual(result["recommended_slice"]["slice_index"], 2)
        self.assertFalse(Path(result["slices"][0]["t1_path"]).is_absolute())
        result["slices"][0]["visible_region_ids"].clear()
        self.assertTrue(get_region_slices(self.data, 1)["slices"][0]["visible_region_ids"])
        index = copy.deepcopy(self.data.slice_index)
        for record in index["slices"]:
            record["visible_region_ids"] = [i for i in record["visible_region_ids"] if i != 1]
        index["best_region_slices"] = [r for r in index["best_region_slices"] if r["label_id"] != 1]
        empty = get_region_slices(replace(self.data, slice_index=index), 1)
        self.assertEqual(empty["slices"], [])
        self.assertIsNone(empty["recommended_slice"])
        for region, orientation in [(True, "Axial"), (1, "axial"), (21, "Coronal")]:
            with self.assertRaises(ValueError):
                get_region_slices(self.data, region, orientation)
        json.dumps(empty, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
