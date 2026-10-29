"""Deterministic local calculations; no web, model or session dependencies."""
from copy import deepcopy
from itertools import combinations

import numpy as np
from scipy.signal import periodogram
from scipy.stats import rankdata

from backend.analysis.data import Dataset


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in {low}..{high}")


def _ids(region_ids):
    if not isinstance(region_ids, list) or not region_ids:
        raise ValueError("region_ids must be a nonempty list")
    for region_id in region_ids:
        _integer(region_id, "region_id", 1, 20)
    if len(set(region_ids)) != len(region_ids):
        raise ValueError("region_ids must be distinct")


def _range(start, end, minimum=1):
    _integer(start, "start", 1, 200)
    _integer(end, "end", 1, 200)
    if end-start+1 < minimum:
        raise ValueError(f"Range must contain at least {minimum} sample(s)")
    return slice(start-1, end)


def _method(method):
    if type(method) is not str or method not in ("pearson", "spearman"):
        raise ValueError("method must be pearson or spearman")


def _correlation(a, b, method):
    if np.all(a == a[0]) or np.all(b == b[0]):
        return {"status": "unavailable", "correlation": None, "reason": "constant_signal"}
    if method == "spearman":
        a, b = rankdata(a, method="average"), rankdata(b, method="average")
    value = float(np.corrcoef(a, b)[0, 1])
    if not np.isfinite(value):
        return {"status": "unavailable", "correlation": None, "reason": "numerical_failure"}
    return {"status": "ok", "correlation": value}


def _result(data, analysis, parameters, **values):
    return {"dataset_version": data.dataset_version, "analysis": analysis,
            "parameters": parameters, "status": "ok", "warnings": [], **values}


def _time_parameters(start, end, **extra):
    return {"start_sample": start, "end_sample": end, "sample_count": end-start+1, **extra}


def _time_warnings(correlation=False):
    warnings = ["Time is sample index; the sampling interval in seconds is unknown."]
    if correlation:
        warnings.append("Correlation is descriptive, not causation, diagnosis or a neural fiber connection.")
        warnings.append("Sample count alone does not establish reliability; short ranges need caution.")
    return warnings


def get_dataset_summary(data: Dataset) -> dict:
    return _result(data, "get_dataset_summary", {}, region_count=len(data.regions),
                   sample_count=len(data.samples), slice_count=len(data.slice_index["slices"]),
                   signal_type="ROI-mean BOLD fMRI", units=deepcopy(data.manifest["units"]),
                   sample_interval_seconds=None, spatial_reference=data.manifest["spatial_reference"],
                   normalization=deepcopy(data.manifest["normalization"]))


def get_region_info(data: Dataset, region_id: int) -> dict:
    _ids([region_id])
    return _result(data, "get_region_info", {"region_id": region_id},
                   region=deepcopy(data.regions[region_id-1]))


def get_timeseries(data: Dataset, region_ids: list[int], start: int = 1, end: int = 200) -> dict:
    _ids(region_ids)
    interval = _range(start, end)
    columns = [i-1 for i in region_ids]
    return _result(data, "get_timeseries", _time_parameters(start, end, region_ids=region_ids.copy()),
                   region_ids=region_ids.copy(), samples=data.samples[interval].tolist(),
                   bold=data.bold[interval][:, columns].tolist(),
                   zscore=data.zscore[interval][:, columns].tolist(), axes=["sample", "region"],
                   normalization=deepcopy(data.manifest["normalization"]), warnings=_time_warnings())


def compare_regions(data: Dataset, region_a: int, region_b: int, start: int = 1,
                    end: int = 200, method: str = "pearson") -> dict:
    _ids([region_a, region_b])
    interval = _range(start, end, 3)
    _method(method)
    structure = {}
    for metric, unit in (("thickness_mm", "mm"), ("volume_mm3", "mm3")):
        a, b = (float(data.regions[i-1][metric]) for i in (region_a, region_b))
        structure[metric] = {"a": a, "b": b, "difference_b_minus_a": b-a, "unit": unit}
    result = get_timeseries(data, [region_a, region_b], start, end)
    result.update(analysis="compare_regions",
                  parameters=_time_parameters(start, end, region_a=region_a, region_b=region_b, method=method),
                  regions=deepcopy([data.regions[region_a-1], data.regions[region_b-1]]),
                  structure=structure, warnings=_time_warnings(correlation=True))
    result.update(_correlation(data.bold[interval, region_a-1], data.bold[interval, region_b-1], method))
    return result


def find_similar_pairs(data: Dataset, start: int = 1, end: int = 200, method: str = "pearson",
                       scope: str = "all", order: str = "descending", limit: int = 5) -> dict:
    interval = _range(start, end, 3)
    _method(method)
    if type(scope) is not str or scope not in ("all", "homologous"):
        raise ValueError("scope must be all or homologous")
    if type(order) is not str or order not in ("ascending", "descending"):
        raise ValueError("order must be ascending or descending")
    candidates = list(combinations(range(1, 21), 2)) if scope == "all" else [(i, i+10) for i in range(1, 11)]
    _integer(limit, "limit", 1, len(candidates))
    pairs, unavailable = [], []
    for a, b in candidates:
        result = {"region_a": a, "region_b": b,
                  **_correlation(data.bold[interval, a-1], data.bold[interval, b-1], method)}
        (pairs if result["status"] == "ok" else unavailable).append(result)
    sign = -1 if order == "descending" else 1
    pairs.sort(key=lambda r: (sign*r["correlation"], r["region_a"], r["region_b"]))
    warnings = _time_warnings(correlation=True)
    if unavailable:
        warnings.append("Unavailable pairs are excluded from ranking and listed separately.")
    return _result(data, "find_similar_pairs",
                   _time_parameters(start, end, method=method, scope=scope, order=order, limit=limit),
                   pairs=pairs[:limit], candidate_pair_count=len(candidates), valid_pair_count=len(pairs),
                   unavailable_pairs=unavailable, status="ok" if pairs else "unavailable", warnings=warnings)


def analyze_pair_over_windows(data: Dataset, region_a: int, region_b: int, start: int = 1,
                              end: int = 200, window: int = 50, step: int = 10,
                              method: str = "pearson") -> dict:
    _ids([region_a, region_b])
    _range(start, end, 3)
    _method(method)
    count = end-start+1
    _integer(window, "window", 3, count)
    _integer(step, "step", 1, count)
    windows = []
    for first in range(start, end-window+2, step):
        interval = slice(first-1, first+window-1)
        windows.append({"start_sample": first, "end_sample": first+window-1, "sample_count": window,
                        **_correlation(data.bold[interval, region_a-1], data.bold[interval, region_b-1], method)})
    valid = [r["correlation"] for r in windows if r["status"] == "ok"]
    return _result(data, "analyze_pair_over_windows",
                   _time_parameters(start, end, region_a=region_a, region_b=region_b,
                                    window=window, step=step, method=method),
                   windows=windows, valid_window_count=len(valid),
                   min_correlation=min(valid) if valid else None, max_correlation=max(valid) if valid else None,
                   status="ok" if valid else "unavailable", warnings=_time_warnings(correlation=True))


def get_region_slices(data: Dataset, region_id: int, orientation: str = "Axial") -> dict:
    _ids([region_id])
    if type(orientation) is not str or orientation not in ("Axial", "Coronal"):
        raise ValueError("orientation must be Axial or Coronal")
    records = [r for r in data.slice_index["slices"]
               if r["orientation"] == orientation and region_id in r["visible_region_ids"]]
    best = next((r for r in data.slice_index["best_region_slices"]
                 if r["orientation"] == orientation and r["label_id"] == region_id), None)
    recommended = next((r for r in records if best and r["filename"] == best["filename"]), None)
    return _result(data, "get_region_slices", {"region_id": region_id, "orientation": orientation},
                   slices=deepcopy(records), recommended_slice=deepcopy(recommended),
                   coordinate_system=data.slice_index["coordinate_system"])


def _statistics(values):
    return {"mean": float(values.mean()), "std_ddof0": 0.0 if np.all(values == values[0]) else float(values.std()),
            "iqr": float(np.percentile(values, 75)-np.percentile(values, 25)),
            "rms": float(np.sqrt(np.mean(values**2))),
            "rms_adjacent_change": float(np.sqrt(np.mean(np.diff(values)**2))) if len(values) > 1 else None}


def _major_points(values, start):
    selected = []
    for index in np.argsort(-values, kind="stable"):
        if all(abs(int(index)-other) >= 10 for other in selected):
            selected.append(int(index))
        if len(selected) == 5:
            break
    return [{"sample": start+i, "score": float(values[i])} for i in selected]


def analyze_region(data: Dataset, region_id: int, start: int = 1, end: int = 200) -> dict:
    series = get_timeseries(data, [region_id], start, end)
    region = get_region_info(data, region_id)['region']
    raw = np.asarray(series['bold'])[:, 0]
    z = np.asarray(series['zscore'])[:, 0]
    return _result(data, 'analyze_region', _time_parameters(start, end, region_id=region_id),
        region=region, signal_statistics={'bold': _statistics(raw), 'global_zscore': _statistics(z)},
        major_points={'deviation_z': _major_points(np.abs(z), start),
                      'adjacent_change_z': _major_points(np.abs(np.diff(z)), start+1)},
        comparison={**series, 'regions': [region], 'correlation': None},
        conditions={'signal_unit': 'unknown BOLD scale', 'zscore_reference': 'full 200 samples',
                    'sample_interval_seconds': None, 'major_points': 'up to 5 points, >=10 samples apart; change assigned to later sample'},
        warnings=_time_warnings())


def _pca_summary(values, selected_ids, standardize=False):
    constants = np.all(values == values[0], axis=0)
    centered = values-values.mean(axis=0)
    centered[:, constants] = 0  # Constant decimals can retain round-off after mean subtraction.
    if standardize:
        std = values.std(axis=0)
        centered = np.divide(centered, std, out=np.zeros_like(centered), where=std > 0)
    _, singular, vectors = np.linalg.svd(centered, full_matrices=False)
    energy = float(np.sum(singular**2))
    if energy == 0:
        return {"status": "unavailable", "reason": "all_constant_signals"}
    # Resolve sign ambiguity for reproducible loadings, as in the offline analysis.
    vectors *= np.sign(vectors[np.arange(len(vectors)), np.abs(vectors).argmax(axis=1)])[:, None]
    components = []
    rank = int(np.sum(singular > singular[0]*max(centered.shape)*np.finfo(float).eps))
    for index, vector in enumerate(vectors[:min(3, rank)]):
        top = np.argsort(-np.abs(vector), kind="stable")[:3]
        components.append({"component": index+1,
                           "selected_loadings": [{"region_id": i, "loading": float(vector[i-1])} for i in selected_ids],
                           "top_loadings": [{"region_id": int(i)+1, "loading": float(vector[i])} for i in top]})
    return {"status": "ok", "region_count": values.shape[1], "numerical_rank": rank, "constant_region_ids":
            (np.flatnonzero(constants)+1).tolist(),
            "explained_variance_ratio": (singular**2/energy).tolist(), "components": components}


def analyze_regions_detailed(data: Dataset, region_a: int, region_b: int, start: int = 1,
                             end: int = 200, method: str = "pearson", window: int | None = None,
                             step: int | None = None) -> dict:
    comparison = compare_regions(data, region_a, region_b, start, end, method)
    interval = _range(start, end, 3)
    count = end-start+1
    width = min(50, count) if window is None else window
    stride = min(10, count) if step is None else step
    windows = analyze_pair_over_windows(data, region_a, region_b, start, end, width, stride, method)
    ids = [region_a, region_b]
    x, z = data.bold[interval], data.zscore[interval]
    structures = deepcopy(comparison["structure"])
    for row in structures.values():
        denominator = (row["a"]+row["b"])/2
        row["relative_difference_percent"] = 100*(row["b"]-row["a"])/denominator if denominator else None
    stats, autocorrelation, spectra = [], [], []
    for region_id in ids:
        values = x[:, region_id-1]
        stats.append({"region_id": region_id, "bold": _statistics(values),
                      "global_zscore": _statistics(z[:, region_id-1])})
        lags = [{"lag_samples": lag, **_correlation(values[:-lag], values[lag:], "pearson")}
                for lag in range(1, min(20, count-3)+1)]
        available = any(r["status"] == "ok" for r in lags)
        reason = "fewer_than_4_samples" if not lags else "constant_signal" if np.all(values == values[0]) else "numerical_failure"
        autocorrelation.append({"region_id": region_id, "lags": lags,
                                "status": "ok" if available else "unavailable", "reason": None if available else reason})
        spectral = {"region_id": region_id, "unit": "cycles/sample"}
        if count < 8 or np.all(values == values[0]):
            spectral.update(status="unavailable", reason="fewer_than_8_samples" if count < 8 else "constant_signal")
        else:
            for taper in ("hann", "boxcar"):
                frequencies, power = periodogram(values, fs=1, window=taper, detrend="constant", scaling="density")
                peak = 1+int(np.argmax(power[1:]))
                spectral[taper+"_peak_cycles_per_sample"] = float(frequencies[peak])
                spectral[taper+"_peak_period_samples"] = float(1/frequencies[peak])
            spectral.update(status="ok", resolution_cycles_per_sample=1/count)
        spectra.append(spectral)
    all_pairs = find_similar_pairs(data, start, end, method, limit=190)
    homologous = find_similar_pairs(data, start, end, method, scope="homologous", limit=10)
    def rank(rows):
        return next((i+1 for i, row in enumerate(rows) if {row["region_a"], row["region_b"]} == set(ids)), None)
    rankings = {"method": method, "all_pair_rank": rank(all_pairs["pairs"]),
                "all_valid_pair_count": all_pairs["valid_pair_count"],
                "homologous_pair_rank": rank(homologous["pairs"]),
                "homologous_valid_pair_count": homologous["valid_pair_count"],
                "top_pairs": all_pairs["pairs"][:5], "related_to_selection": [
                    {"region_id": i, "pairs": [row for row in all_pairs["pairs"]
                     if i in (row["region_a"], row["region_b"])][:3]} for i in ids]}
    selected_z = z[:, [region_a-1, region_b-1]]
    points = {}
    for name, values in (("selected", selected_z), ("all_regions", z)):
        points[name+"_rms_z"] = _major_points(np.sqrt(np.mean(values**2, axis=1)), start)
        points[name+"_rms_adjacent_change_z"] = _major_points(np.sqrt(np.mean(np.diff(values, axis=0)**2, axis=1)), start+1)
    return _result(data, "analyze_regions_detailed", _time_parameters(start, end,
        region_a=region_a, region_b=region_b, method=method, window=width, step=stride),
        comparison=comparison, structure=structures, regions=deepcopy(comparison["regions"]),
        correlations={m: _correlation(x[:, region_a-1], x[:, region_b-1], m) for m in ("pearson", "spearman")},
        signal_statistics=stats, windows=windows, rankings=rankings, major_points=points,
        autocorrelation=autocorrelation, spectra=spectra,
        pca={"raw_centered": _pca_summary(x, ids), "within_range_zscore": _pca_summary(x, ids, True)},
        conditions={"signal_unit": "unknown BOLD scale", "zscore_reference": "full 200 samples",
                    "pca_scope": "all 20 regions within the requested range",
                    "relative_difference_formula": "100*(b-a)/((a+b)/2)",
                    "major_points": "up to 5 peaks, >=10 samples apart; change assigned to later sample",
                    "sample_interval_seconds": None}, warnings=_time_warnings(correlation=True))
