"""Reproduce the exploratory analysis without modifying supplied data."""
from pathlib import Path
import hashlib
import json
import platform
import sys

import numpy as np
import pandas as pd
from PIL import Image
from scipy import signal as scipy_signal
import scipy
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "뇌영상 시계열 예시 데이터"
OUT = ROOT / "reports" / "data_analysis"


def asymmetry(left, right):
    return 100 * (right - left) / ((right + left) / 2)


def pca(values):
    centered = values - values.mean(axis=0)
    u, s, vh = np.linalg.svd(centered, full_matrices=False)
    signs = np.sign(vh[np.arange(len(vh)), np.abs(vh).argmax(axis=1)])
    vh *= signs[:, None]
    scores = u * s * signs
    assert np.allclose(scores @ vh, centered)
    ratios = s**2 / (s**2).sum()
    assert np.isclose(ratios.sum(), 1)
    return ratios, scores, vh


def periodogram(values, window):
    return scipy_signal.periodogram(values, fs=1.0, window=window,
                                    detrend="constant", scaling="density", axis=0)


def spaced_candidates(values, count=5):
    selected = []
    for index in np.argsort(-values, kind="stable"):
        if all(abs(int(index) - j) >= 10 for j in selected):
            selected.append(int(index))
        if len(selected) == count:
            break
    return [{"sample": i + 1, "score": float(values[i])} for i in selected]


def numerical_checks():
    assert asymmetry(2, 2) == 0 and np.isclose(asymmetry(2, 3), 40)
    assert np.isclose(asymmetry(3, 2), -40)
    samples = np.arange(200)
    sine = np.sin(2 * np.pi * .05 * samples)
    frequency, power = periodogram(sine, "boxcar")
    assert np.isclose(frequency[power.argmax()], .05)
    assert np.isclose(power.sum() * (frequency[1] - frequency[0]), sine.var())
    ratios, _, _ = pca(np.column_stack([sine, 2 * sine]))
    assert np.isclose(ratios[0], 1)
    assert np.isclose(pd.Series([1, 1, 3]).rank().iloc[0], 1.5)
    candidates = spaced_candidates(np.arange(30, dtype=float), 3)
    assert [r["sample"] for r in candidates] == [30, 20, 10]


def save_table(name, records):
    pd.DataFrame(records).to_csv(OUT / f"{name}.csv", index=False, encoding="utf-8-sig")


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze():
    OUT.mkdir(parents=True, exist_ok=True)
    numerical_checks()
    files = sorted(p for p in DATA.rglob("*") if p.is_file())
    manifest = [{"path": str(p.relative_to(DATA)), "bytes": p.stat().st_size,
                 "sha256": hash_file(p)} for p in files]
    assert len(files) == 105
    before = {r["path"]: r["sha256"] for r in manifest}
    palette = pd.read_csv(DATA / "Axial_PNG" / "region_colors_used.csv")
    assert palette.equals(pd.read_csv(DATA / "Coronal_PNG" / "region_colors_used.csv"))
    thickness = pd.read_csv(DATA / "cortical_thickness_20regions.csv")
    volume = pd.read_csv(DATA / "gray_matter_volume_20regions.csv")
    for frame in (palette, thickness, volume):
        assert frame.label_id.tolist() == list(range(1, 21))
        assert frame.hemisphere.tolist() == ["Left"] * 10 + ["Right"] * 10
    assert thickness.region_name.equals(volume.region_name)
    regions = thickness.merge(volume, on=["label_id", "hemisphere", "region_name"], validate="one_to_one")
    regions = regions.merge(palette, on=["label_id", "hemisphere"], validate="one_to_one")
    assert np.isfinite(regions[["thickness_mm", "volume_mm3"]]).all().all()
    assert (regions[["thickness_mm", "volume_mm3"]] > 0).all().all()
    x = np.loadtxt(DATA / "timeseries_FILT_bp_mean_200x20_demean.csv", delimiter=",")
    assert x.shape == (200, 20) and np.isfinite(x).all() and (x.std(axis=0) > 0).all()
    z = (x - x.mean(axis=0)) / x.std(axis=0)
    assert np.allclose(z.mean(axis=0), 0) and np.allclose(z.std(axis=0), 1)
    regions["mean"] = x.mean(axis=0)
    regions["std_ddof0"] = x.std(axis=0)
    regions["median"] = np.median(x, axis=0)
    regions["iqr"] = np.quantile(x, .75, axis=0) - np.quantile(x, .25, axis=0)
    regions["min"] = x.min(axis=0)
    regions["max"] = x.max(axis=0)
    regions["rms"] = np.sqrt((x*x).mean(axis=0))
    regions["mean_abs_difference"] = np.abs(np.diff(x, axis=0)).mean(axis=0)
    regions["lag1_correlation"] = [np.corrcoef(x[:-1, i], x[1:, i])[0, 1] for i in range(20)]
    regions["volume_share_selected_pct"] = 100 * regions.volume_mm3 / regions.volume_mm3.sum()
    save_table("region_metrics", regions)

    corr = np.corrcoef(x, rowvar=False)
    spearman = pd.DataFrame(x).rank().corr().to_numpy()
    trimmed = np.corrcoef(x[10:-10], rowvar=False)
    assert np.allclose(corr, corr.T) and np.allclose(np.diag(corr), 1)
    pd.DataFrame(corr, index=range(1, 21), columns=range(1, 21)).to_csv(OUT / "pearson_matrix.csv", index_label="label_id")
    pd.DataFrame(spearman, index=range(1, 21), columns=range(1, 21)).to_csv(OUT / "spearman_matrix.csv", index_label="label_id")
    pairs = [{"left_id": i+1, "right_id": j+1, "pearson": corr[i, j],
              "spearman": spearman[i, j], "trimmed_pearson": trimmed[i, j],
              "homologous": j == i + 10} for i in range(20) for j in range(i+1, 20)]
    pairs = pd.DataFrame(pairs)
    assert len(pairs) == 190
    rolling = []
    for width in (40, 50, 80):
        for start in range(0, len(x)-width+1, 10):
            matrix = np.corrcoef(x[start:start+width], rowvar=False)
            assert np.isfinite(matrix).all()
            rolling.extend({"window": width, "start_sample": start+1, "end_sample": start+width,
                            "left_id": int(r.left_id), "right_id": int(r.right_id),
                            "pearson": matrix[int(r.left_id)-1, int(r.right_id)-1]} for r in pairs.itertuples())
    rolling = pd.DataFrame(rolling)
    for width in (40, 50, 80):
        stats = rolling[rolling.window == width].groupby(["left_id", "right_id"]).pearson.agg(["min", "median", "max"])
        stats.columns = [f"w{width}_{col}" for col in stats.columns]
        pairs = pairs.merge(stats, on=["left_id", "right_id"], validate="one_to_one")
    save_table("pair_metrics", pairs.sort_values("pearson", ascending=False))
    save_table("rolling_correlations", rolling)
    asymmetries = []
    for i in range(10):
        left, right = regions.iloc[i], regions.iloc[i+10]
        item = {"left_id": i+1, "right_id": i+11, "region_name": left.region_name,
                "pearson": corr[i, i+10]}
        for metric in ("thickness_mm", "volume_mm3", "std_ddof0"):
            left_value, right_value = float(left[metric]), float(right[metric])
            item.update({f"left_{metric}": left_value, f"right_{metric}": right_value,
                         f"delta_{metric}": right_value-left_value,
                         f"asymmetry_pct_{metric}": asymmetry(left_value, right_value)})
        asymmetries.append(item)
    save_table("bilateral_comparison", asymmetries)

    rms_z = np.sqrt((z*z).mean(axis=1))
    rms_diff = np.r_[np.nan, np.sqrt((np.diff(z, axis=0)**2).mean(axis=1))]
    temporal = pd.DataFrame({"sample": np.arange(1, 201), "rms_z": rms_z,
                             "mean_z": z.mean(axis=1), "rms_delta_z": rms_diff})
    temporal["delta_defined"] = temporal["sample"] > 1
    save_table("timepoint_metrics", temporal)
    quarters = [{"start_sample": s+1, "end_sample": s+50,
                 "mean_rms_z": rms_z[s:s+50].mean(), "mean_signed_z": z[s:s+50].mean(),
                 "mean_within_quarter_rms_delta_z": np.sqrt((np.diff(z[s:s+50], axis=0)**2).mean(axis=1)).mean()}
                for s in range(0, 200, 50)]
    save_table("quarter_metrics", quarters)
    autocorrelation = [{"label_id": j+1, "lag_samples": lag,
                        "overlap_pearson": np.corrcoef(x[:-lag, j], x[lag:, j])[0, 1]}
                       for j in range(20) for lag in range(1, 21)]
    save_table("autocorrelation", autocorrelation)
    freq, hann = periodogram(x, "hann")
    _, box = periodogram(x, "boxcar")
    spectral_rows = [{"label_id": j+1, "cycles_per_sample": f,
                      "hann_psd": hann[k, j], "boxcar_psd": box[k, j]}
                     for j in range(20) for k, f in enumerate(freq)]
    save_table("spectra", spectral_rows)
    spectral_summary = []
    for j in range(20):
        k = 1 + hann[1:, j].argmax()
        cumulative = np.cumsum(hann[1:, j]) / hann[1:, j].sum()
        spectral_summary.append({"label_id": j+1, "hann_peak_cycles_per_sample": freq[k],
                                 "hann_peak_period_samples": 1/freq[k],
                                 "hann_median_cycles_per_sample": freq[1:][np.searchsorted(cumulative, .5)],
                                 "boxcar_peak_cycles_per_sample": freq[1+box[1:, j].argmax()]})
    save_table("spectral_summary", spectral_summary)
    pca_summary, component_rows, score_rows, loading_rows = {}, [], [], []
    for scale, values in (("original", x), ("zscore", z)):
        ratio, scores, loadings = pca(values)
        cumulative = ratio.cumsum()
        pca_summary[scale] = {"variance_ratios": ratio.tolist(), "cumulative_ratios": cumulative.tolist(),
                              "components_90pct": int(np.searchsorted(cumulative, .9)+1),
                              "components_95pct": int(np.searchsorted(cumulative, .95)+1)}
        component_rows.extend({"scale": scale, "component": i+1, "variance_ratio": r,
                               "cumulative_ratio": cumulative[i]} for i, r in enumerate(ratio))
        for j in range(200):
            score_rows.append({"scale": scale, "sample": j+1, **{f"PC{k+1}": scores[j, k] for k in range(20)}})
        for j in range(20):
            loading_rows.append({"scale": scale, "label_id": j+1, **{f"PC{k+1}": loadings[k, j] for k in range(20)}})
    save_table("pca_components", component_rows)
    save_table("pca_scores", score_rows)
    save_table("pca_loadings", loading_rows)
    cross = []
    for structure in ("thickness_mm", "volume_mm3"):
        for feature in ("std_ddof0", "mean_abs_difference"):
            observed = regions[[structure, feature]]
            leave_pair_out = [observed.drop(index=[i, i+10]).corr().iloc[0, 1] for i in range(10)]
            cross.append({"structure": structure, "signal_feature": feature,
                          "pearson": observed.corr().iloc[0, 1],
                          "spearman": observed.corr(method="spearman").iloc[0, 1],
                          "leave_pair_out_min": min(leave_pair_out), "leave_pair_out_max": max(leave_pair_out)})
    save_table("structure_signal_associations", cross)

    mask_rows, image_rows, empty = [], [], []
    color_codes = {int(r.R)*65536 + int(r.G)*256 + int(r.B): int(r.label_id) for r in palette.itertuples()}
    assert len(color_codes) == 20
    for orientation in ("Axial", "Coronal"):
        parent = DATA / f"{orientation}_PNG"
        names = sorted(p.name for p in (parent / "Labels").glob("*.png"))
        assert names == sorted(p.name for p in (parent / "T1").glob("*.png")) == sorted(p.name for p in (parent / "Overlay").glob("*.png"))
        for name in names:
            images = {}
            for kind in ("T1", "Overlay", "Labels"):
                with Image.open(parent / kind / name) as im:
                    im.load()
                    assert im.size == (1024, 1024) and im.mode == "RGB"
                    image_rows.append({"path": str((parent/kind/name).relative_to(DATA)),
                                       "width": im.width, "height": im.height, "mode": im.mode,
                                       "metadata": dict(im.info)})
                    images[kind] = np.asarray(im).copy()
            a = images["Labels"].astype(np.uint32)
            packed = a[:, :, 0]*65536 + a[:, :, 1]*256 + a[:, :, 2]
            unique, counts = np.unique(packed, return_counts=True)
            assert set(unique.tolist()) <= {0, *color_codes}
            background = packed == 0
            assert np.array_equal(images["T1"][background], images["Overlay"][background])
            if background.all():
                empty.append(f"{orientation}_PNG/Labels/{name}")
            count_by_id = {color_codes[int(c)]: int(n) for c, n in zip(unique, counts) if c}
            assert sum(count_by_id.values()) == int((~background).sum())
            for label_id in range(1, 21):
                pixels = count_by_id.get(label_id, 0)
                item = {"orientation": orientation, "filename": name,
                        "slice_index": int(Path(name).stem.split("_")[-1]), "label_id": label_id,
                        "pixels": pixels, "centroid_x": None, "centroid_y": None,
                        "x_min": None, "x_max": None, "y_min": None, "y_max": None}
                if pixels:
                    row = palette.iloc[label_id-1]
                    code = int(row.R)*65536 + int(row.G)*256 + int(row.B)
                    ys, xs = np.nonzero(packed == code)
                    item.update(centroid_x=float(xs.mean()), centroid_y=float(ys.mean()),
                                x_min=int(xs.min()), x_max=int(xs.max()), y_min=int(ys.min()), y_max=int(ys.max()))
                mask_rows.append(item)
    assert len(image_rows) == 99
    masks = pd.DataFrame(mask_rows)
    save_table("mask_geometry", masks)
    best_regions, best_pairs = [], []
    for orientation in ("Axial", "Coronal"):
        subset = masks[masks.orientation == orientation]
        for label_id in range(1, 21):
            visible = subset[subset.label_id == label_id]
            best = visible.loc[visible.pixels.idxmax()].to_dict()
            assert best["pixels"] > 0
            best["visible_slice_count"] = int((visible.pixels > 0).sum())
            best_regions.append(best)
        area = subset.pivot(index="filename", columns="label_id", values="pixels")
        for i in range(1, 11):
            balanced = area[[i, i+10]].min(axis=1)
            name = balanced.idxmax()
            best_pairs.append({"orientation": orientation, "left_id": i, "right_id": i+10,
                               "filename": name, "left_pixels": int(area.loc[name, i]),
                               "right_pixels": int(area.loc[name, i+10]), "minimum_pixels": int(balanced.loc[name])})
    save_table("best_region_slices", best_regions)
    save_table("best_bilateral_slices", best_pairs)
    save_table("source_manifest", manifest)
    after = {str(p.relative_to(DATA)): hash_file(p) for p in files}
    assert before == after
    top_pearson = set(zip(pairs.nlargest(10, "pearson").left_id, pairs.nlargest(10, "pearson").right_id))
    top_spearman = set(zip(pairs.nlargest(10, "spearman").left_id, pairs.nlargest(10, "spearman").right_id))
    result = {
        "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                        "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__,
                        "matplotlib": matplotlib.__version__},
        "checks": {"numerical_self_checks": "passed", "original_hashes_unchanged": True,
                   "file_count": len(files), "total_bytes": sum(p.stat().st_size for p in files),
                   "png_count": len(image_rows), "unknown_label_colors": 0, "palette_equal": True,
                   "overlay_background_matches_t1": True, "all_image_metadata_empty": all(not r['metadata'] for r in image_rows),
                   "shape": list(x.shape), "max_absolute_column_mean": float(np.abs(x.mean(axis=0)).max()),
                   "nonfinite_values": int((~np.isfinite(x)).sum()), "duplicate_rows": 200-len(np.unique(x, axis=0)),
                   "constant_columns": int((x.std(axis=0) == 0).sum()), "empty_label_images": empty},
        "regions": regions.to_dict("records"), "bilateral": asymmetries,
        "structure": {"selected_volume_total_mm3": float(regions.volume_mm3.sum()),
                      "left_volume_sum_mm3": float(regions.iloc[:10].volume_mm3.sum()),
                      "right_volume_sum_mm3": float(regions.iloc[10:].volume_mm3.sum()),
                      "thickness_unweighted_mean_mm": float(regions.thickness_mm.mean())},
        "relations": {"strongest": pairs.nlargest(10, "pearson").to_dict("records"),
                      "weakest": pairs.nsmallest(5, "pearson").to_dict("records"),
                      "homologous_median": float(pairs[pairs.homologous].pearson.median()),
                      "other_pairs_median": float(pairs[~pairs.homologous].pearson.median()),
                      "threshold_edge_counts": {str(t): int((pairs.pearson >= t).sum()) for t in (.5, .7, .9)},
                      "top10_pearson_spearman_overlap": len(top_pearson & top_spearman),
                      "largest_trim_difference": float((pairs.pearson-pairs.trimmed_pearson).abs().max()),
                      "rolling_window_counts": {str(w): len(range(0, 201-w, 10)) for w in (40, 50, 80)}},
        "temporal": {"large_relative_magnitude": spaced_candidates(rms_z),
                     "large_step_changes": spaced_candidates(np.nan_to_num(rms_diff, nan=-1)), "quarters": quarters},
        "spectral_summary": spectral_summary, "pca": pca_summary, "cross_modal": cross,
        "best_regions": best_regions, "best_pairs": best_pairs,
    }
    (OUT / "analysis_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return result, x, z, corr, rolling, masks, freq, hann


def plot_results(result, x, z, corr, rolling, masks, freq, hann):
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False,
                         "font.size": 10, "figure.dpi": 140, "savefig.facecolor": "white"})
    names = [r["region_name"].replace("Middle_Inferior_Temporal", "Mid/Inf Temporal") for r in result["regions"][:10]]
    fig, axes = plt.subplots(3, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1, 1]}, layout="constrained")
    im = axes[0].imshow(z.T, aspect="auto", origin="upper", cmap="RdBu_r", vmin=-3, vmax=3, extent=[.5,200.5,20.5,.5])
    axes[0].set(yticks=range(1,21), ylabel="영역 ID", title="영역별 상대 변화: z-score (표시 색상 범위 ±3)")
    fig.colorbar(im, ax=axes[0], label="각 영역 평균 대비 표준편차 단위")
    axes[1].plot(range(1,201), np.sqrt((z*z).mean(axis=1)), color="#2453a6")
    axes[1].set(ylabel="RMS(z)", title="여러 영역의 상대 변동 크기")
    axes[2].plot(range(2,201), np.sqrt((np.diff(z,axis=0)**2).mean(axis=1)), color="#b44724")
    axes[2].set(ylabel="RMS(Δz)", xlabel="시간점 (초가 아님)", title="이전 시간점과의 변화 크기")
    for ax in axes[1:]: ax.set_xlim(1,200)
    fig.savefig(OUT/"time_patterns.png"); plt.close(fig)

    fig, axes = plt.subplots(1,3,figsize=(14,5),layout="constrained")
    comparison = pd.DataFrame(result["bilateral"])
    for ax, metric, title in zip(axes[:2], ["thickness_mm","volume_mm3"], ["평균 피질 두께 (mm)","회백질 부피 (mm³)"]):
        ax.plot(comparison[f"left_{metric}"], range(10), "o-", label="좌")
        ax.plot(comparison[f"right_{metric}"], range(10), "s--", label="우")
        ax.set(yticks=range(10), yticklabels=names, title=title); ax.invert_yaxis(); ax.legend()
    axes[2].barh(np.arange(10)-.18, comparison.asymmetry_pct_thickness_mm, height=.35,label="두께")
    axes[2].barh(np.arange(10)+.18, comparison.asymmetry_pct_volume_mm3, height=.35,label="부피")
    axes[2].axvline(0,color="gray",lw=1)
    axes[2].set(yticks=range(10), yticklabels=names, title="좌우 차이: 100×(우-좌)/평균 (%)")
    axes[2].invert_yaxis(); axes[2].legend()
    fig.savefig(OUT/"structure_comparison.png"); plt.close(fig)

    fig, axes = plt.subplots(1,2,figsize=(12,6),layout="constrained")
    im=axes[0].imshow(corr,vmin=-1,vmax=1,cmap="RdBu_r",extent=[.5,20.5,20.5,.5])
    axes[0].set(xticks=range(1,21),yticks=range(1,21),xlabel="영역 ID",ylabel="영역 ID",title="전체 200점 Pearson 상관")
    fig.colorbar(im,ax=axes[0],label="r")
    for i in range(1,11):
        values=rolling[(rolling.window==50)&(rolling.left_id==i)&(rolling.right_id==i+10)].pearson
        axes[1].plot([values.min(),values.max()],[i,i],color="#5379a8",lw=3)
        axes[1].scatter([corr[i-1,i+9]],[i],color="black",s=25,zorder=3)
    axes[1].set(yticks=range(1,11),yticklabels=names,xlim=(-1,1),xlabel="Pearson r",title="좌우 대응 쌍: 50점 창의 범위와 전체 값(검정)")
    axes[1].invert_yaxis(); axes[1].axvline(0,color="gray",lw=1)
    fig.savefig(OUT/"correlation_patterns.png"); plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout="constrained")
    for scale,label in [("original","원척도"),("zscore","영역별 표준화")]:
        axes[0].plot(range(1,21),100*np.array(result["pca"][scale]["cumulative_ratios"]),"o-",label=label)
    axes[0].set(xticks=range(1,21,2),xlabel="성분 수",ylabel="누적 설명분산 (%)",title="PCA 요약과 스케일 민감도",ylim=(0,102)); axes[0].legend()
    shape=hann[1:]/hann[1:].sum(axis=0)
    for i in range(20): axes[1].plot(freq[1:],shape[:,i],alpha=.25,lw=.8)
    axes[1].plot(freq[1:],shape.mean(axis=1),color="black",lw=2,label="영역별 비DC 정규화 후 평균")
    axes[1].set(xlabel="cycles/sample (Hz가 아님)",ylabel="영역 내 비DC power 비율 / bin",title="표본 인덱스 기준 스펙트럼",xlim=(0,.5)); axes[1].legend(fontsize=8)
    fig.savefig(OUT/"components_and_spectra.png"); plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(12,6),layout="constrained")
    for ax,orientation in zip(axes,["Axial","Coronal"]):
        table=masks[masks.orientation==orientation].pivot(index="label_id",columns="slice_index",values="pixels")
        relative=table.div(table.max(axis=1),axis=0)
        im=ax.imshow(relative,aspect="auto",cmap="viridis",vmin=0,vmax=1)
        ax.set(xticks=range(len(table.columns)),xticklabels=table.columns,yticks=range(20),yticklabels=range(1,21),
               xlabel="파일명 단면 번호 (mm가 아님)",ylabel="영역 ID",title=f"{orientation}: 영역별 최대 면적 대비 노출")
        ax.tick_params(axis="x",labelrotation=90)
    fig.colorbar(im,ax=axes,label="렌더링 픽셀 수 / 영역별 최대 픽셀 수")
    fig.savefig(OUT/"spatial_coverage.png"); plt.close(fig)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    results = analyze()
    plot_results(*results)
    summary = results[0]
    print(json.dumps({k: summary[k] for k in ["checks","structure","relations","temporal","pca","cross_modal"]},ensure_ascii=False,indent=2))
    print("PASS: numerical checks, input validation, PCA reconstruction, matrix invariants, mask checks, and source hashes.")
