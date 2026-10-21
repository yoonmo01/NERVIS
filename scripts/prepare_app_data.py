"""Build and verify a local app package; no network or credential access."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = "뇌영상 시계열 예시 데이터"
SCHEMA = "nervis.app-data.v1"
MANIFEST_CONTRACT = {
    "axes": ["sample", "region"], "shape": [200, 20],
    "units": {"thickness": "mm", "volume": "mm3", "bold": None, "time": "sample index"},
    "sample_interval_seconds": None,
    "spatial_reference": "rendered 2D pixels; no physical affine/spacing",
    "normalization": {"axis": "region", "samples": [1, 200], "ddof": 0},
}
NAMES_KO = dict(zip(
    ["Prefrontal", "Motor_Premotor", "Somatosensory", "Posterior_Parietal",
     "Superior_Temporal", "Middle_Inferior_Temporal", "Medial_Temporal",
     "Occipital_Visual", "Cingulate", "Insula"],
    ["전전두피질", "운동·운동전피질", "체성감각피질", "후두정피질", "상측두피질",
     "중·하측두피질", "내측측두피질", "후두·시각피질", "대상피질", "섬엽피질"],
))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fingerprint(path):
    return {"bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def source_snapshot(root):
    raw = (root / SOURCE_DIR).resolve()
    baseline_path = root / "reports/data_analysis/source_manifest.csv"
    require(baseline_path.is_file(), "Saved source manifest is required; no new baseline will be created")
    with baseline_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected = {row["path"].replace("\\", "/"): {"bytes": int(row["bytes"]), "sha256": row["sha256"]}
                for row in rows}
    paths = [p for p in raw.rglob("*") if p.is_file()]
    require(len(rows) == len(expected) == len(paths) == 105, "Unexpected source file count")
    for path in paths:
        require(path.resolve().is_relative_to(raw), "Source file resolves outside supplied directory")
    actual = {p.relative_to(raw).as_posix(): fingerprint(p) for p in paths}
    require(actual == expected, "Supplied source differs from saved baseline; preparation stopped")
    return actual


def checked_output(root, output):
    requested = Path(output) if output is not None else root / "data/processed/nervis_v1"
    if not requested.is_absolute():
        requested = root / requested
    resolved = requested.resolve()
    allowed = root / "data/processed"
    raw = (root / SOURCE_DIR).resolve()
    require(resolved != allowed and resolved.is_relative_to(allowed)
            and not resolved.is_relative_to(raw),
            "Output must resolve to a child of this project's data/processed directory")
    return resolved


def read_table(path, fields):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames is not None and set(reader.fieldnames) == set(fields),
                f"Unexpected CSV header: {path.name}")
        rows = list(reader)
    require(len(rows) == 20, f"Expected 20 rows: {path.name}")
    indexed = {int(row["label_id"]): row for row in rows}
    require(len(indexed) == 20 and set(indexed) == set(range(1, 21)),
            f"Duplicate or missing label IDs: {path.name}")
    return indexed


def load_inputs(root):
    raw = root / SOURCE_DIR
    color_fields = ["label_id", "hemisphere", "R", "G", "B"]
    palette = read_table(raw / "Axial_PNG/region_colors_used.csv", color_fields)
    require(palette == read_table(raw / "Coronal_PNG/region_colors_used.csv", color_fields),
            "Orientation palettes differ")
    thickness = read_table(raw / "cortical_thickness_20regions.csv",
                           ["label_id", "hemisphere", "region_name", "thickness_mm"])
    volume = read_table(raw / "gray_matter_volume_20regions.csv",
                        ["label_id", "hemisphere", "region_name", "volume_mm3"])
    regions = []
    for label_id in range(1, 21):
        p, t, v = palette[label_id], thickness[label_id], volume[label_id]
        hemisphere = "Left" if label_id <= 10 else "Right"
        require(p["hemisphere"] == t["hemisphere"] == v["hemisphere"] == hemisphere,
                "Hemisphere mismatch")
        require(t["region_name"] == v["region_name"] and t["region_name"] in NAMES_KO,
                "Unknown or inconsistent region name")
        rgb = [int(p[c]) for c in ("R", "G", "B")]
        require(all(0 <= c <= 255 for c in rgb) and any(rgb), "Invalid palette RGB")
        thick, vol = float(t["thickness_mm"]), float(v["volume_mm3"])
        require(np.isfinite([thick, vol]).all() and thick > 0 and vol > 0,
                "Invalid structural values")
        regions.append({"label_id": label_id, "hemisphere": hemisphere,
                        "region_name": t["region_name"], "name_ko": NAMES_KO[t["region_name"]],
                        "color_rgb": rgb, "thickness_mm": thick, "volume_mm3": vol,
                        "contralateral_id": label_id + 10 if label_id <= 10 else label_id - 10})
    require(len({tuple(r["color_rgb"]) for r in regions}) == 20, "Duplicate palette colors")
    bold = np.loadtxt(raw / "timeseries_FILT_bp_mean_200x20_demean.csv", delimiter=",")
    require(bold.shape == (200, 20) and np.isfinite(bold).all(), "Invalid BOLD shape or values")
    std = bold.std(axis=0, ddof=0)
    require((std > 0).all(), "Constant BOLD column")
    zscore = (bold - bold.mean(axis=0)) / std
    return regions, bold, zscore


def read_rgb(path):
    with Image.open(path) as image:
        require(image.mode == "RGB" and image.size == (1024, 1024),
                f"Expected 1024x1024 RGB PNG: {path.name}")
        return np.array(image)


def source_slices(root, regions):
    colors = {0: 0}
    for region in regions:
        r, g, b = region["color_rgb"]
        colors[(r << 16) | (g << 8) | b] = region["label_id"]
    raw = root / SOURCE_DIR
    for orientation, indices in (("Axial", range(41, 192, 10)), ("Coronal", range(51, 212, 10))):
        folder = raw / f"{orientation}_PNG"
        names = [f"{orientation.lower()}_voxel_{i:03d}.png" for i in indices]
        for kind in ("T1", "Labels", "Overlay"):
            require(sorted(p.name for p in (folder / kind).glob("*.png")) == names,
                    f"Unexpected {orientation} {kind} slice set")
        for name in names:
            labels = read_rgb(folder / "Labels" / name).astype(np.uint32)
            packed = labels[:, :, 0]*65536 + labels[:, :, 1]*256 + labels[:, :, 2]
            unique, inverse = np.unique(packed, return_inverse=True)
            require(all(int(code) in colors for code in unique), "Unknown label RGB")
            mask = np.array([colors[int(code)] for code in unique], dtype=np.uint8)[inverse].reshape(1024, 1024)
            t1 = read_rgb(folder / "T1" / name)
            overlay = read_rgb(folder / "Overlay" / name)
            require(np.array_equal(t1[mask == 0], overlay[mask == 0]), "Overlay background mismatch")
            yield orientation, name, folder / "T1" / name, mask


def slice_record(orientation, name, mask):
    counts = np.bincount(mask.ravel(), minlength=21)
    visible = np.flatnonzero(counts[1:]) + 1
    ys, xs = np.nonzero(mask)
    labels = mask[ys, xs]
    bounds = {}
    for label_id in visible:
        chosen = labels == label_id
        bounds[str(label_id)] = [int(xs[chosen].min()), int(ys[chosen].min()),
                                 int(xs[chosen].max()), int(ys[chosen].max())]
    return {"orientation": orientation, "filename": name,
            "slice_index": int(Path(name).stem.split("_")[-1]),
            "t1_path": f"slices/{orientation}/{name}", "mask_path": f"masks/{orientation}/{name}",
            "visible_region_ids": visible.tolist(),
            "pixel_counts": {str(i): int(counts[i]) for i in range(1, 21)},
            "bounds_xyxy_inclusive": bounds}


def slice_index(records):
    best_regions, best_pairs = [], []
    for orientation in ("Axial", "Coronal"):
        slices = [r for r in records if r["orientation"] == orientation]
        for label_id in range(1, 21):
            best = max(slices, key=lambda r: r["pixel_counts"][str(label_id)])
            pixels = best["pixel_counts"][str(label_id)]
            require(pixels > 0, f"Region {label_id} absent from {orientation}")
            best_regions.append({"orientation": orientation, "label_id": label_id,
                                 "slice_index": best["slice_index"], "filename": best["filename"],
                                 "pixels": pixels})
        for label_id in range(1, 11):
            best = max(slices, key=lambda r: min(r["pixel_counts"][str(label_id)],
                                                r["pixel_counts"][str(label_id+10)]))
            left, right = best["pixel_counts"][str(label_id)], best["pixel_counts"][str(label_id+10)]
            best_pairs.append({"orientation": orientation, "left_id": label_id, "right_id": label_id+10,
                               "slice_index": best["slice_index"], "filename": best["filename"],
                               "left_pixels": left, "right_pixels": right, "minimum_pixels": min(left, right)})
    return {"coordinate_system": "image pixels; origin top-left; no physical spacing",
            "slices": records, "best_region_slices": best_regions, "best_bilateral_slices": best_pairs}


def display_signals(bold, zscore):
    return {"axes": ["sample", "region"], "samples": list(range(1, 201)),
            "region_ids": list(range(1, 21)), "bold": bold.tolist(), "zscore": zscore.tolist(),
            "bold_units": None, "sample_interval_seconds": None,
            "normalization": "per-region full 200-sample z-score; ddof=0; no filtering or interpolation",
            "suggested_z_color_range": [-3, 3]}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def package_files(output):
    paths = [p for p in output.rglob("*") if p.is_file() and p.name != "manifest.json"]
    require(all(p.resolve().is_relative_to(output) for p in paths), "Package file resolves outside output")
    return {p.relative_to(output).as_posix(): fingerprint(p) for p in sorted(paths)}


def dataset_version(source, script_hash):
    version_input = json.dumps({"source_files": source, "schema": SCHEMA, "script_sha256": script_hash},
                               sort_keys=True).encode("utf-8")
    return hashlib.sha256(version_input).hexdigest()[:20]


def verify_package(root, output):
    root = Path(root).resolve()
    output = checked_output(root, output)
    source = source_snapshot(root)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    require(manifest["schema_version"] == SCHEMA and manifest["source_files"] == source,
            "Manifest source/schema mismatch")
    require(all(manifest.get(key) == value for key, value in MANIFEST_CONTRACT.items()),
            "Manifest axes, shape, units, timing, spatial reference or normalization differ")
    generator = manifest.get("generator")
    require(isinstance(generator, dict) and generator.get("path") == "scripts/prepare_app_data.py",
            "Invalid generator metadata")
    script_hash = generator.get("sha256")
    require(isinstance(script_hash, str) and len(script_hash) == 64
            and all(char in "0123456789abcdef" for char in script_hash), "Invalid generator fingerprint")
    require(manifest.get("dataset_version") == dataset_version(source, script_hash),
            "Dataset version does not match its recorded source and generator")
    require(manifest["files"] == package_files(output), "Package file hashes differ")
    regions, bold, zscore = load_inputs(root)
    require(json.loads((output / "regions.json").read_text(encoding="utf-8")) == regions,
            "Packaged regions differ from source")
    with np.load(output / "signals.npz", allow_pickle=False) as values:
        require(set(values.files) == {"bold", "zscore", "samples", "region_ids"}, "Unexpected signal arrays")
        require(all(values[name].shape == shape for name, shape in
                    {"bold": (200,20), "zscore": (200,20), "samples": (200,), "region_ids": (20,)}.items()),
                "Signal arrays have incorrect dimensions")
        require(np.array_equal(values["bold"], bold), "Packaged BOLD differs from source")
        require(np.allclose(values["zscore"], zscore, rtol=0, atol=1e-12), "Packaged z-score differs")
        require(np.array_equal(values["samples"], np.arange(1,201))
                and np.array_equal(values["region_ids"], np.arange(1,21)), "Signal order mismatch")
    require(json.loads((output / "signals_display.json").read_text(encoding="utf-8")) == display_signals(bold,zscore),
            "Display signals differ from source")
    records = []
    expected_files = {"regions.json", "signals.npz", "signals_display.json", "slice_index.json"}
    for orientation, name, t1, expected_mask in source_slices(root, regions):
        record = slice_record(orientation, name, expected_mask)
        with Image.open(output / record["mask_path"]) as image:
            require(image.mode == "L" and np.array_equal(np.array(image), expected_mask),
                    "ROI mask differs from source RGB labels")
        require(fingerprint(output / record["t1_path"]) == fingerprint(t1), "T1 copy differs from source")
        expected_files.update([record["mask_path"], record["t1_path"]])
        records.append(record)
    require(set(manifest["files"]) == expected_files, "Unexpected package contents")
    index = slice_index(records)
    require(json.loads((output / "slice_index.json").read_text(encoding="utf-8")) == index,
            "Slice index differs from source masks")
    # Existing analysis tables are independent evidence, not inputs to overwrite.
    checked_tables = []
    for filename, key, fields in [
        ("best_region_slices.csv", "best_region_slices", ["orientation","label_id","filename","pixels"]),
        ("best_bilateral_slices.csv", "best_bilateral_slices",
         ["orientation","left_id","right_id","filename","left_pixels","right_pixels","minimum_pixels"]),
    ]:
        path = root / "reports/data_analysis" / filename
        if path.is_file():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                previous = [{field: str(row[field]) for field in fields} for row in csv.DictReader(handle)]
            current = [{field: str(row[field]) for field in fields} for row in index[key]]
            require(previous == current, f"Existing analysis disagrees: {filename}")
            checked_tables.append(filename)
    require(source_snapshot(root) == source, "Source changed during verification")
    return {"status": "passed", "dataset_version": manifest["dataset_version"],
            "source_file_count": len(source), "region_count": len(regions), "sample_count": len(bold),
            "slice_count": len(records), "mask_count": len(records), "t1_count": len(records),
            "empty_mask_count": sum(not r["visible_region_ids"] for r in records),
            "package_file_count": len(expected_files)+1, "existing_analysis_tables_checked": checked_tables,
            "checks": {"source_baseline_matches": True, "raw_values_preserved": True,
                       "zscore_verified": True, "all_masks_match_source_rgb": True,
                       "all_t1_copies_identical": True, "slice_index_verified": True},
            "external_requests": 0}


def prepare_package(root=ROOT, output=None):
    root = Path(root).resolve()
    output = checked_output(root, output)
    if output.exists():
        raise FileExistsError("Output already exists; use --verify-only or select a new output directory")
    source = source_snapshot(root)
    regions, bold, zscore = load_inputs(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    require(checked_output(root, output) == output, "Output path changed")
    with tempfile.TemporaryDirectory(prefix=".nervis-build-", dir=output.parent) as staging:
        stage = Path(staging).resolve()
        require(stage.is_relative_to(root / "data/processed"), "Unsafe staging directory")
        write_json(stage / "regions.json", regions)
        np.savez_compressed(stage / "signals.npz", bold=bold, zscore=zscore,
                            samples=np.arange(1,201), region_ids=np.arange(1,21))
        write_json(stage / "signals_display.json", display_signals(bold, zscore))
        records = []
        for orientation, name, t1, mask in source_slices(root, regions):
            record = slice_record(orientation, name, mask)
            for field in ("mask_path", "t1_path"):
                (stage / record[field]).parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(mask).save(stage / record["mask_path"])
            shutil.copyfile(t1, stage / record["t1_path"])
            records.append(record)
        write_json(stage / "slice_index.json", slice_index(records))
        script_hash = fingerprint(Path(__file__).resolve())["sha256"]
        manifest = {**MANIFEST_CONTRACT, "schema_version": SCHEMA,
                    "dataset_version": dataset_version(source, script_hash),
                    "generator": {"path": "scripts/prepare_app_data.py", "sha256": script_hash},
                    "source_files": source, "files": package_files(stage),
                    "dependencies": {"numpy": np.__version__, "pillow": Image.__version__}}
        write_json(stage / "manifest.json", manifest)
        report = verify_package(root, stage)
        # Both resolved paths were checked inside data/processed; originals cannot be a rename target.
        require(checked_output(root, output) == output and not output.exists(), "Output path changed or appeared")
        stage.rename(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Verify an existing package without rebuilding it")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/nervis_v1")
    args = parser.parse_args()
    report_path = (ROOT / "reports/data_preparation/validation.json").resolve()
    require(report_path.is_relative_to(ROOT / "reports/data_preparation"), "Unsafe report destination")
    report = verify_package(ROOT, args.output) if args.verify_only else prepare_package(ROOT, args.output)
    report["output"] = checked_output(ROOT, args.output).relative_to(ROOT).as_posix()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except (ValueError, OSError, KeyError) as exc:
        print(f"Preparation stopped: {exc}", file=sys.stderr)
        sys.exit(1)
