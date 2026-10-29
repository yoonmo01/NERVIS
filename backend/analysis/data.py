"""Load a verified app package without reading originals or credentials."""
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

import numpy as np

from scripts.prepare_app_data import (
    MANIFEST_CONTRACT, SCHEMA, dataset_version, display_signals,
    fingerprint, require, slice_index,
)


@dataclass(frozen=True)
class Dataset:
    dataset_version: str
    manifest: dict
    regions: list[dict]
    bold: np.ndarray
    zscore: np.ndarray
    samples: np.ndarray
    region_ids: np.ndarray
    slice_index: dict


def _package_path(package: Path, name: str) -> Path:
    require(isinstance(name, str) and bool(name), "Invalid package path")
    require(not PureWindowsPath(name).drive and not PurePosixPath(name).is_absolute()
            and "\\" not in name and ":" not in name
            and all(part not in ("", ".", "..") for part in name.split("/")),
            "Package path must be relative without traversal")
    path = package / name
    require(path.resolve().is_relative_to(package) and path.is_file(),
            "Package file missing or resolves outside package")
    return path


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _readonly(values: np.ndarray) -> np.ndarray:
    return np.frombuffer(values.tobytes(), dtype=values.dtype).reshape(values.shape)


def _load(package: Path) -> Dataset:
    manifest = _read_json(_package_path(package, "manifest.json"))
    require(manifest["schema_version"] == SCHEMA, "Unsupported package schema")
    require(all(manifest.get(k) == v for k, v in MANIFEST_CONTRACT.items()),
            "Package axes, units, timing or normalization differ")
    generator = manifest["generator"]
    require(generator["path"] == "scripts/prepare_app_data.py", "Invalid generator")
    script_hash = generator["sha256"]
    require(isinstance(script_hash, str) and len(script_hash) == 64
            and all(c in "0123456789abcdef" for c in script_hash), "Invalid generator hash")
    require(manifest["dataset_version"] == dataset_version(manifest["source_files"], script_hash),
            "Dataset version mismatch")
    files = manifest["files"]
    require(isinstance(files, dict), "Invalid file inventory")
    for name, expected in files.items():
        require(fingerprint(_package_path(package, name)) == expected, f"Package hash mismatch: {name}")
    actual = {p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file()}
    require(actual == set(files) | {"manifest.json"}, "Unexpected package files")

    regions = _read_json(_package_path(package, "regions.json"))
    require(isinstance(regions, list) and len(regions) == 20, "Expected 20 regions")
    for i, region in enumerate(regions, 1):
        require(type(region["label_id"]) is int and region["label_id"] == i,
                "Region IDs must be ordered 1..20")
        require(region["hemisphere"] == ("Left" if i <= 10 else "Right")
                and type(region["contralateral_id"]) is int
                and region["contralateral_id"] == (i+10 if i <= 10 else i-10),
                "Invalid region hemisphere or counterpart")
        require(all(isinstance(region[k], str) and region[k] for k in ("region_name", "name_ko")),
                "Missing region name")
        require(all(type(region[k]) in (int, float) and np.isfinite(region[k]) and region[k] > 0
                    for k in ("thickness_mm", "volume_mm3")), "Invalid structural values")
        rgb = region["color_rgb"]
        require(isinstance(rgb, list) and len(rgb) == 3
                and all(type(c) is int and 0 <= c <= 255 for c in rgb) and any(rgb),
                "Invalid region color")
    require(len({tuple(r["color_rgb"]) for r in regions}) == 20, "Duplicate colors")
    require(all(regions[i]["region_name"] == regions[i+10]["region_name"] for i in range(10)),
            "Counterpart names differ")

    with np.load(_package_path(package, "signals.npz"), allow_pickle=False) as source:
        require(set(source.files) == {"bold", "zscore", "samples", "region_ids"}, "Unexpected arrays")
        arrays = {k: source[k] for k in source.files}
    for name, shape in {"bold": (200, 20), "zscore": (200, 20), "samples": (200,), "region_ids": (20,)}.items():
        a = arrays[name]
        require(a.shape == shape and a.dtype.kind in "fiu" and np.isfinite(a).all(),
                f"Invalid array: {name}")
    require(np.array_equal(arrays["samples"], np.arange(1, 201))
            and np.array_equal(arrays["region_ids"], np.arange(1, 21)), "Signal ID order mismatch")
    bold, zscore = arrays["bold"], arrays["zscore"]
    std = bold.std(axis=0, ddof=0)
    require((std > 0).all(), "Constant full-length signal")
    require(np.allclose(zscore, (bold-bold.mean(axis=0))/std, rtol=0, atol=1e-12),
            "Display normalization differs")
    require(_read_json(_package_path(package, "signals_display.json")) == display_signals(bold, zscore),
            "Browser signals differ from numerical arrays")

    index = _read_json(_package_path(package, "slice_index.json"))
    records = index["slices"]
    require(isinstance(records, list) and len(records) == 33, "Expected 33 slices")
    expected_files = {"regions.json", "signals.npz", "signals_display.json", "slice_index.json"}
    seen = set()
    for record in records:
        orientation, number = record["orientation"], record["slice_index"]
        require(orientation in ("Axial", "Coronal") and type(number) is int and number >= 0,
                "Invalid slice orientation/index")
        identity = (orientation, number)
        require(identity not in seen, "Duplicate slice")
        seen.add(identity)
        filename = f"{orientation.lower()}_voxel_{number:03}.png"
        require(record["filename"] == filename, "Slice filename/index mismatch")
        for key, folder in (("t1_path", "slices"), ("mask_path", "masks")):
            name = record[key]
            require(name == f"{folder}/{orientation}/{filename}" and name in files, "Invalid slice path")
            _package_path(package, name)
            expected_files.add(name)
        counts = record["pixel_counts"]
        require(set(counts) == {str(i) for i in range(1, 21)}
                and all(type(v) is int and 0 <= v <= 1024**2 for v in counts.values()),
                "Invalid slice pixel counts")
        visible = [i for i in range(1, 21) if counts[str(i)] > 0]
        require(record["visible_region_ids"] == visible, "Invalid visible region IDs")
        bounds = record["bounds_xyxy_inclusive"]
        require(set(bounds) == {str(i) for i in visible}, "Invalid bounding box IDs")
        for box in bounds.values():
            require(isinstance(box, list) and len(box) == 4
                    and all(type(v) is int and 0 <= v < 1024 for v in box)
                    and box[0] <= box[2] and box[1] <= box[3], "Invalid bounding box")
    require(set(files) == expected_files, "Package inventory differs from slice index")
    require(index == slice_index(records), "Slice recommendations or coordinate metadata differ")
    return Dataset(manifest["dataset_version"], manifest, regions,
                   *(_readonly(arrays[k]) for k in ("bold", "zscore", "samples", "region_ids")), index)


def load_dataset(package_dir: Path) -> Dataset:
    """Load once; originals are checked separately by the offline verifier."""
    try:
        return _load(Path(package_dir).resolve())
    except (OSError, KeyError, TypeError, OverflowError) as exc:
        raise ValueError(f"Invalid app package: {exc}") from exc
