"""Compare local functions with saved analysis; never regenerate references."""
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import numpy as np
from scipy.stats import spearmanr

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend import analysis
from backend.data import load_dataset
from scripts.prepare_app_data import fingerprint, require, source_snapshot, verify_package


ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-12


def compare_values(actual, expected, name):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    require(a.shape == b.shape and a.size > 0, f"{name}: shapes differ or empty comparison")
    require(np.isfinite(a).all() and np.isfinite(b).all(), f"{name}: nonfinite value")
    require(np.allclose(a, b, rtol=0, atol=TOLERANCE), f"{name}: numerical results differ")
    return float(np.max(np.abs(a-b)))


def read_matrix(path):
    try:
        with Path(path).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            require(reader.fieldnames == ["label_id", *map(str, range(1, 21))], "Invalid matrix header")
            rows = list(reader)
        require([int(r["label_id"]) for r in rows] == list(range(1, 21)), "Matrix IDs differ")
        matrix = np.array([[float(r[str(i)]) for i in range(1, 21)] for r in rows])
        require(matrix.shape == (20, 20) and np.isfinite(matrix).all(), "Invalid reference matrix")
        compare_values(matrix, matrix.T, "reference symmetry")
        compare_values(np.diag(matrix), np.ones(20), "reference diagonal")
        return matrix
    except (OSError, KeyError, TypeError) as exc:
        raise ValueError(f"Cannot read reference matrix: {exc}") from exc


def verify_reports(data, reference_dir):
    """Read existing CSV references; a missing or changed value is a failure."""
    reference_dir = Path(reference_dir)
    checks = {}
    for method in ("pearson", "spearman"):
        matrix = read_matrix(reference_dir / f"{method}_matrix.csv")
        result = analysis.find_similar_pairs(data, method=method, limit=190)
        require(len(result["pairs"]) == 190 and not result["unavailable_pairs"], "Missing pair results")
        expected = [matrix[r["region_a"]-1, r["region_b"]-1] for r in result["pairs"]]
        checks[method] = {"compared_pairs": 190, "max_absolute_error": compare_values(
            [r["correlation"] for r in result["pairs"]], expected, method)}

    with (reference_dir / "rolling_correlations.csv").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == ["window", "start_sample", "end_sample", "left_id", "right_id", "pearson"],
                "Invalid rolling reference header")
        references = {}
        for row in reader:
            key = tuple(int(row[k]) for k in ("window", "start_sample", "end_sample", "left_id", "right_id"))
            require(key not in references, "Duplicate rolling reference")
            references[key] = float(row["pearson"])
    actual = {}
    for a in range(1, 21):
        for b in range(a+1, 21):
            for width in (40, 50, 80):
                result = analysis.analyze_pair_over_windows(data, a, b, window=width)
                for row in result["windows"]:
                    require(row["status"] == "ok", "Unavailable real-data window")
                    actual[(width, row["start_sample"], row["end_sample"], a, b)] = row["correlation"]
    require(actual.keys() == references.keys(), "Rolling window boundaries or pairs differ")
    checks["rolling"] = {"compared_windows": len(actual), "max_absolute_error": compare_values(
        list(actual.values()), [references[k] for k in actual], "rolling")}

    for region in data.regions:
        require(analysis.get_region_info(data, region["label_id"])["region"] == region, "Region lookup differs")
    for best in data.slice_index["best_region_slices"]:
        result = analysis.get_region_slices(data, best["label_id"], best["orientation"])
        require(result["recommended_slice"]["filename"] == best["filename"], "Slice recommendation differs")
    for start, end in ((17, 123), (91, 150)):
        series = analysis.get_timeseries(data, [20, 1], start, end)
        compare_values(series["bold"], data.bold[start-1:end][:, [19, 0]], "selected range")
        for method in ("pearson", "spearman"):
            a, b = data.bold[start-1:end, 0], data.bold[start-1:end, 19]
            expected = np.corrcoef(a, b)[0, 1] if method == "pearson" else spearmanr(a, b).statistic
            compare_values([analysis.compare_regions(data, 1, 20, start, end, method)["correlation"]],
                           [expected], "subrange correlation")
    checks.update(region_lookups=20, recommended_slices=len(data.slice_index["best_region_slices"]),
                  independent_subrange_correlations=4)
    return checks


def _report_path(root):
    root = Path(root).resolve()
    requested = root / "reports/local_analysis/validation.json"
    path = requested.resolve()
    require(path.is_relative_to(root / "reports/local_analysis")
            and not path.is_relative_to((root / "뇌영상 시계열 예시 데이터").resolve())
            and not path.is_relative_to((root / "data/processed").resolve()), "Unsafe report destination")
    if requested.exists() or requested.is_symlink():
        raise FileExistsError("Existing local-analysis report will not be overwritten")
    return path


def write_report(root, report):
    path = _report_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return path


def _package_snapshot(package):
    return {p.relative_to(package).as_posix(): fingerprint(p) for p in package.rglob("*") if p.is_file()}


def verify_local_analysis(root=ROOT):
    root = Path(root).resolve()
    _report_path(root)
    package = root / "data/processed/nervis_v1"
    report = {"status": "failed", "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "absolute_tolerance": TOLERANCE, "relative_tolerance": 0, "external_requests": 0}
    before_source = before_package = None
    try:
        before_source = source_snapshot(root)
        before_package = _package_snapshot(package)
        report["offline_package_verification"] = verify_package(root, package)["status"]
        data = load_dataset(package)
        arrays_before = (data.bold.tobytes(), data.zscore.tobytes())
        report["checks"] = verify_reports(data, root / "reports/data_analysis")
        require(arrays_before == (data.bold.tobytes(), data.zscore.tobytes()), "Functions modified signal arrays")
        report.update(dataset_version=data.dataset_version, array_values_unchanged=True, status="passed")
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        report["error"] = str(exc)
    finally:
        try:
            source = source_snapshot(root)
            current_package = _package_snapshot(package)
            require(before_source is not None and source == before_source, "Source changed or initial check failed")
            require(before_package is not None and current_package == before_package, "Package changed or initial check failed")
            report.update(source_files_verified=len(source), source_unchanged=True,
                          package_files_verified=len(current_package), package_unchanged=True)
        except (ValueError, OSError) as exc:
            report.update(status="failed", preservation_error=str(exc))
    write_report(root, report)
    if report["status"] != "passed":
        raise ValueError(report.get("preservation_error", report.get("error", "Verification failed")))
    return report


if __name__ == "__main__":
    try:
        result = verify_local_analysis()
        print(json.dumps({k: result[k] for k in ("status", "source_files_verified", "package_files_verified", "checks")},
                         ensure_ascii=False, indent=2))
    except (ValueError, OSError) as exc:
        print(f"Local verification stopped: {exc}", file=sys.stderr)
        sys.exit(1)
