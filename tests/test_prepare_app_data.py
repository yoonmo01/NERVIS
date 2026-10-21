"""Offline tests use synthetic files under tmp; supplied originals are never edited."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_app_data.py"
REGION_NAMES = ["Prefrontal", "Motor_Premotor", "Somatosensory", "Posterior_Parietal",
                "Superior_Temporal", "Middle_Inferior_Temporal", "Medial_Temporal",
                "Occipital_Visual", "Cingulate", "Insula"]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def record_synthetic_baseline(root):
    raw = root / "뇌영상 시계열 예시 데이터"
    rows = [{"path": str(p.relative_to(raw)), "bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(raw.rglob("*")) if p.is_file()]
    write_csv(root / "reports/data_analysis/source_manifest.csv", ["path", "bytes", "sha256"], rows)


def make_synthetic_project(root):
    raw = root / "뇌영상 시계열 예시 데이터"
    palette = [{"label_id": i, "hemisphere": "Left" if i <= 10 else "Right",
                "R": i, "G": 0, "B": 1} for i in range(1, 21)]
    for orientation, indices in [("Axial", range(41, 192, 10)), ("Coronal", range(51, 212, 10))]:
        folder = raw / f"{orientation}_PNG"
        write_csv(folder / "region_colors_used.csv", ["label_id", "hemisphere", "R", "G", "B"], palette)
        for kind in ("T1", "Overlay", "Labels"):
            (folder / kind).mkdir()
        for position, index in enumerate(indices):
            name = f"{orientation.lower()}_voxel_{index:03d}.png"
            labels = np.zeros((1024, 1024, 3), dtype=np.uint8)
            if position:
                for i in range(1, 21):
                    labels[i, i+1] = [i, 0, 1]
            t1 = np.full_like(labels, 80)
            overlay = t1.copy()
            overlay[np.any(labels, axis=2)] = labels[np.any(labels, axis=2)]
            for kind, pixels in (("T1", t1), ("Overlay", overlay), ("Labels", labels)):
                Image.fromarray(pixels).save(folder / kind / name)
    for filename, column in [("cortical_thickness_20regions.csv", "thickness_mm"),
                             ("gray_matter_volume_20regions.csv", "volume_mm3")]:
        rows = [{"label_id": i, "hemisphere": "Left" if i <= 10 else "Right",
                 "region_name": REGION_NAMES[(i-1) % 10],
                 column: 1+i/10 if column == "thickness_mm" else 100*i}
                for i in range(1, 21)]
        write_csv(raw / filename, ["label_id", "hemisphere", "region_name", column], rows)
    x = np.arange(200, dtype=float)[:, None] - 99.5
    np.savetxt(raw / "timeseries_FILT_bp_mean_200x20_demean.csv", x*np.arange(1,21), delimiter=",")
    (raw / "synthetic_guide.pdf").write_bytes(b"Synthetic fixture, not a supplied PDF")
    record_synthetic_baseline(root)


class PreparePackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (ROOT / "tmp").mkdir(exist_ok=True)
        assert (ROOT / "tmp").resolve() == ROOT / "tmp"
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix="package-fixture-", dir=ROOT / "tmp")
        cls.fixture = Path(cls.fixture_dir.name)
        assert cls.fixture.resolve().is_relative_to(ROOT / "tmp")
        make_synthetic_project(cls.fixture)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    def setUp(self):
        self.case_dir = tempfile.TemporaryDirectory(prefix="package-case-", dir=ROOT / "tmp")
        assert Path(self.case_dir.name).resolve().is_relative_to(ROOT / "tmp")
        self.addCleanup(self.case_dir.cleanup)
        self.root = Path(self.case_dir.name) / "project"
        shutil.copytree(self.fixture, self.root)
        self.raw = self.root / "뇌영상 시계열 예시 데이터"
        self.output = self.root / "data/processed/nervis_v1"

    def preparer(self):
        if not SCRIPT.exists():
            self.fail("Offline preparation script has not been implemented")
        spec = importlib.util.spec_from_file_location("prepare_app_data", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_round_trip_preserves_signal_ids_pixels_and_blank_masks(self):
        module = self.preparer()
        baseline = (self.root / "reports/data_analysis/source_manifest.csv").read_bytes()
        report = module.prepare_package(self.root)
        self.assertEqual(report["region_count"], 20)
        self.assertEqual(report["slice_count"], 33)
        self.assertEqual(report["empty_mask_count"], 2)
        with np.load(self.output / "signals.npz", allow_pickle=False) as signals:
            self.assertEqual(signals["bold"].shape, (200, 20))
            self.assertEqual(float(signals["bold"][0, 0]), -99.5)
            self.assertEqual(float(signals["bold"][-1, -1]), 1990.0)
            np.testing.assert_allclose(signals["zscore"].mean(axis=0), 0, atol=1e-12)
            np.testing.assert_allclose(signals["zscore"].std(axis=0), 1, atol=1e-12)
        regions = json.loads((self.output / "regions.json").read_text(encoding="utf-8"))
        self.assertEqual(regions[0]["label_id"], 1)
        self.assertEqual(regions[0]["thickness_mm"], 1.1)
        self.assertEqual(regions[-1]["volume_mm3"], 2000)
        with Image.open(self.output / "masks/Axial/axial_voxel_051.png") as image:
            self.assertEqual(image.mode, "L")
            self.assertEqual(image.getpixel((2, 1)), 1)
            self.assertEqual(image.getpixel((21, 20)), 20)
            self.assertEqual(image.getpixel((0, 0)), 0)
        index = json.loads((self.output / "slice_index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["best_region_slices"][0]["slice_index"], 51)
        self.assertEqual(module.verify_package(self.root, self.output)["slice_count"], 33)
        self.assertEqual((self.root / "reports/data_analysis/source_manifest.csv").read_bytes(), baseline)

    def test_output_inside_original_is_rejected_without_creating_files(self):
        module = self.preparer()
        with self.assertRaises(ValueError):
            module.prepare_package(self.root, self.raw / "output")
        self.assertFalse((self.raw / "output").exists())

    def test_output_outside_processed_directory_is_rejected(self):
        module = self.preparer()
        with self.assertRaises(ValueError):
            module.prepare_package(self.root, self.root / "elsewhere")
        self.assertFalse((self.root / "elsewhere").exists())

    def test_existing_output_is_not_overwritten(self):
        module = self.preparer()
        self.output.mkdir(parents=True)
        marker = self.output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            module.prepare_package(self.root)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_changed_source_aborts_without_replacing_baseline(self):
        module = self.preparer()
        baseline_path = self.root / "reports/data_analysis/source_manifest.csv"
        baseline = baseline_path.read_bytes()
        (self.raw / "synthetic_guide.pdf").write_bytes(b"Changed synthetic input")
        with self.assertRaises(ValueError):
            module.prepare_package(self.root)
        self.assertFalse(self.output.exists())
        self.assertEqual(baseline_path.read_bytes(), baseline)

    def test_unknown_rgb_aborts_without_publishing(self):
        module = self.preparer()
        path = self.raw / "Axial_PNG/Labels/axial_voxel_051.png"
        with Image.open(path) as image:
            pixels = np.array(image)
        pixels[0, 0] = [255, 255, 255]
        Image.fromarray(pixels).save(path)
        record_synthetic_baseline(self.root)
        with self.assertRaises(ValueError):
            module.prepare_package(self.root)
        self.assertFalse(self.output.exists())

    def test_semantic_signal_corruption_rejected_even_with_matching_file_hash(self):
        module = self.preparer()
        module.prepare_package(self.root)
        path = self.output / "signals.npz"
        with np.load(path, allow_pickle=False) as arrays:
            values = {name: arrays[name] for name in arrays.files}
        values["bold"][0, 0] = 12345.0
        np.savez_compressed(path, **values)
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["signals.npz"] = {"bytes": path.stat().st_size,
                                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.verify_package(self.root, self.output)

    def test_manifest_timing_tampering_is_rejected(self):
        module = self.preparer()
        module.prepare_package(self.root)
        path = self.output / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["sample_interval_seconds"] = 2.0
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.verify_package(self.root, self.output)

    def test_manifest_version_tampering_is_rejected(self):
        module = self.preparer()
        module.prepare_package(self.root)
        path = self.output / "manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["dataset_version"] = "incorrect"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.verify_package(self.root, self.output)

    def test_zscore_shape_tampering_is_rejected(self):
        module = self.preparer()
        module.prepare_package(self.root)
        path = self.output / "signals.npz"
        with np.load(path, allow_pickle=False) as arrays:
            values = {name: arrays[name] for name in arrays.files}
        values["zscore"] = values["zscore"][None, :, :]
        np.savez_compressed(path, **values)
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["signals.npz"] = {"bytes": path.stat().st_size,
                                                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            module.verify_package(self.root, self.output)

    def test_symlink_to_original_is_not_an_output_escape(self):
        module = self.preparer()
        parent = self.root / "data/processed"
        parent.mkdir(parents=True)
        alias = parent / "source-alias"
        try:
            os.symlink(self.raw, alias, target_is_directory=True)
        except OSError:
            if os.name != "nt":
                raise
            # Directory junctions exercise the same resolved-path guard without symlink privileges.
            import _winapi
            _winapi.CreateJunction(str(self.raw), str(alias))
            self.addCleanup(alias.rmdir)
        else:
            self.addCleanup(alias.unlink)
        with self.assertRaises(ValueError):
            module.prepare_package(self.root, alias / "output")
        self.assertFalse((self.raw / "output").exists())


if __name__ == "__main__":
    unittest.main()
