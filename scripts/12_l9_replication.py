"""Replicate the LST results with Landsat 9 (2022-2025).

Scenes: Landsat 8 (2013-2025) + Landsat 9 (2022-2025), Tier 1 L2SP, Jul-Aug, >= 50% of the city
clear (variant-B rule). Relative LST = pixel - scene city median.

A. Sensor agreement
   - Offset: scene city-median LST ~ T_air(BWI) + year + sensor  ->  L9 - L8 (deg C).
   - Pattern: mean relative LST 2022-2025 from L8 only vs L9 only (90 m blocks).
B. Independent change replication: late-period change in relative LST measured twice with
   no shared scenes:  dL8 = late(L8, 2022-25) - early(L8 odd years 2013-21)
                      dL9 = late(L9, 2022-25) - early(L8 even years 2014-20)
   Correlation of dL8 and dL9 across blocks > 0 means real spatial change, not noise.
C. Trends with more data (V1 = L8 + L9; V2 = L8 to 2021 + L9 only from 2022): per-pixel relative
   trends compared with the L8-only map (V0); citywide weather-normalized (C1) trend with b
   refitted (LST ~ T_air + year + sensor); impervious-gain effect re-estimated.

Outputs: data/processed/l9_replication/. Run after 01 (both sensors), 02, 03, 04, 06:
  conda run -p .\\env python scripts\\12_l9_replication.py
"""
import importlib.util
import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/l9_replication"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|Degrees of freedom", RuntimeWarning)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load_module("lst", ROOT / "scripts/02_lst_trend.py")
W = load_module("bwi", ROOT / "scripts/04_lst_bwi_normalized.py")
YEARS = L.YEARS


def block(a, k=3):
    h, w = (a.shape[-2] // k) * k, (a.shape[-1] // k) * k
    b = a[..., :h, :w].reshape(a.shape[:-2] + (h // k, k, w // k, k))
    return np.where(np.isfinite(b).sum((-3, -1)) >= k * k - 2, np.nanmean(b, (-3, -1)), np.nan)


def period_mean(rel, years, keep_years):
    """Equal weight per year: mean of annual means over the selected years."""
    ann = [np.nanmean(rel[years == y], 0) for y in keep_years if (years == y).any()]
    return np.nanmean(np.stack(ann), 0), len(ann)


def corr(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    r = stats.pearsonr(a[ok], b[ok])
    return {"r": float(r.statistic), "p": float(r.pvalue), "n_blocks": int(ok.sum()),
            "spearman": float(stats.spearmanr(a[ok], b[ok]).statistic)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ROOT / "data/processed/lst_trend/B_rel_slope_ols.tif") as s:
        tr, shape, prof = s.transform, s.shape, s.profile.copy()
    city = geometry_mask(gpd.read_file(L.NSA).to_crs(32618).geometry, out_shape=shape, transform=tr, invert=True)
    scenes, stack, _ = L.load_scenes(city, sensors=("LC08", "LC09"))
    scenes["sensor"] = scenes.scene_id.str[:4]
    isd = W.parse_isd()
    scenes["tair_C"] = [W.interp_at(isd.tair, W.scene_time(s)) for s in scenes.scene_id]
    use = (scenes.clear_frac_city >= L.MIN_CLEAR).values
    scenes["used"] = use
    scenes.drop(columns=["date"]).to_csv(OUT / "scenes_l8_l9.csv", index=False, float_format="%.3f")
    print(scenes.groupby(["sensor", "used"]).size())

    stack = np.where(city[None], stack, np.nan).astype("float32")  # city pixels only
    rel = (stack - scenes.lst_median.values[:, None, None].astype("float32"))
    yrs, sen = scenes.year.values, scenes.sensor.values
    res = {}

    # --- A. sensor offset and pattern agreement
    sb = scenes[use & scenes.tair_C.notna()]
    fA = smf.ols("lst_median ~ tair_C + year + C(sensor)", data=sb).fit()
    late = [y for y in YEARS if y >= 2022]
    l8m = use & (sen == "LC08")
    l9m = use & (sen == "LC09")
    late8, n8 = period_mean(rel[l8m], yrs[l8m], late)
    late9, n9 = period_mean(rel[l9m], yrs[l9m], late)
    res["A_sensor_offset_L9_minus_L8_C"] = {"coef": fA.params["C(sensor)[T.LC09]"],
                                            "ci95": fA.conf_int().loc["C(sensor)[T.LC09]"].tolist(),
                                            "p": fA.pvalues["C(sensor)[T.LC09]"], "scenes": int(fA.nobs)}
    res["A_late_pattern_L8_vs_L9"] = {**corr(block(late8), block(late9)), "years_L8": n8, "years_L9": n9,
                                      "mean_abs_diff_C": float(np.nanmean(np.abs(block(late8) - block(late9))))}

    # --- B. independent change replication
    odd = [y for y in YEARS if y <= 2021 and y % 2 == 1]
    even = [y for y in YEARS if y <= 2021 and y % 2 == 0]
    e_odd, n_odd = period_mean(rel[l8m], yrs[l8m], odd)
    e_even, n_even = period_mean(rel[l8m], yrs[l8m], even)
    d8, d9 = block(late8 - e_odd), block(late9 - e_even)
    res["B_change_L8_vs_L9"] = {**corr(d8, d9), "early_odd_years": n_odd, "early_even_years": n_even}
    # does each independent change map show warming where impervious increased (NLCD 2013-2025)?
    dimp = block(np.where(city, read_tif(ROOT / "data/processed/landcover/nlcd_dimp_2013_2025_pp.tif"), np.nan))
    gain = dimp >= 20
    stable = np.abs(dimp) < 5
    res["B_change_in_gain_blocks"] = {
        "dL8_median_gain_ge20": float(np.nanmedian(d8[gain])), "dL8_median_stable": float(np.nanmedian(d8[stable])),
        "dL9_median_gain_ge20": float(np.nanmedian(d9[gain])), "dL9_median_stable": float(np.nanmedian(d9[stable])),
        "gain_blocks": int(np.isfinite(d8[gain] + d9[gain]).sum())}

    # --- C. trend maps with more data
    variants = {"V0_L8": l8m, "V1_L8_L9": use,
                "V2_swap": use & (((sen == "LC08") & (yrs <= 2021)) | ((sen == "LC09") & (yrs >= 2022)))}
    summer = pd.Series({y: np.nanmean([W.interp_at(isd.tair, pd.Timestamp(f"{d:%Y-%m-%d}T15:46", tz="UTC"))
                                       for d in pd.date_range(f"{y}-07-01", f"{y}-08-31")]) for y in YEARS})
    v0 = None
    for name, m in variants.items():
        ann = L.annual_mean(rel[m], yrs[m])
        t = L.trends(ann)
        L.write(OUT / f"{name}_rel_slope_ols.tif", t["slope_ols"], prof, city, [f"{name} relative trend (C/yr)"])
        L.write(OUT / f"{name}_rel_p_ols.tif", t["p_ols"], prof, city, [f"{name} OLS p"])
        bt = block(t["slope_ols"])
        ok_g = np.isfinite(bt) & np.isfinite(dimp) & (dimp >= 5)
        lr = stats.linregress(dimp[ok_g], bt[ok_g])
        entry = {"scenes": int(m.sum()), "years": int(np.isfinite(ann[:, city]).any(1).sum()),
                 "pixel_median": float(np.nanmedian(t["slope_ols"][city])),
                 "frac_p_lt_0.05": float((t["p_ols"][city] < 0.05).sum() / np.isfinite(t["p_ols"][city]).sum()),
                 "gain_effect_C_per_yr_per_10pp": lr.slope * 10, "gain_effect_ci95": 1.96 * lr.stderr * 10,
                 "gain_effect_p": lr.pvalue}
        if v0 is None:
            v0 = bt
        else:
            entry["map_corr_with_V0"] = corr(v0, bt)
        # citywide weather-normalized trend (C1) for this scene set, on fixed common pixels
        s = scenes[m & scenes.tair_C.notna()].copy()
        has_two = s.sensor.nunique() > 1
        f = smf.ols("lst_median ~ tair_C + year" + (" + C(sensor)" if has_two else ""), data=s).fit()
        b = f.params.tair_C
        mi = m & scenes.tair_C.notna().values
        adj = stack[mi] - (b * (scenes.tair_C.values[mi] - summer.reindex(yrs[mi]).values))[:, None, None]
        ann1 = L.annual_mean(adj, yrs[mi])
        yv = [i for i in range(len(YEARS)) if np.isfinite(ann1[i][city]).any()]
        common = np.isfinite(ann1[yv]).all(0) & city
        series = np.array([np.nanmean(ann1[i][common]) for i in yv])
        r = stats.linregress(YEARS[yv], series)
        entry["C1_city"] = {"slope": r.slope, "ci95": stats.t.ppf(0.975, len(yv) - 2) * r.stderr, "p": r.pvalue,
                            "years": len(yv), "b": b, "common_pixels": int(common.sum())}
        res[f"C_{name}"] = entry

    (OUT / "summary.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))

    # --- preview
    fig, ax = plt.subplots(1, 3, figsize=(18, 5.5))
    for a, (x, y, t, xl, yl) in zip(ax, [
            (block(late8), block(late9), "A. Relative LST 2022–25: L8 vs L9", "L8 (°C)", "L9 (°C)"),
            (d8, d9, "B. Independent change: L8 vs L9", "ΔL8: late − odd years (°C)", "ΔL9: late − even years (°C)"),
            (v0, block(L.trends(L.annual_mean(rel[variants['V2_swap']], yrs[variants['V2_swap']]))["slope_ols"]),
             "C. Relative trend: L8 only vs swap", "V0 L8 (°C/yr)", "V2 swap (°C/yr)")]):
        ok = np.isfinite(x) & np.isfinite(y)
        a.hexbin(x[ok], y[ok], gridsize=60, bins="log", cmap="Greys", mincnt=1)
        lim = np.nanpercentile(np.abs(np.r_[x[ok], y[ok]]), 99.5)
        a.plot([-lim, lim], [-lim, lim], "r--", lw=1)
        a.set(xlim=(-lim, lim), ylim=(-lim, lim), title=f"{t}\nr = {stats.pearsonr(x[ok], y[ok]).statistic:.2f}",
              xlabel=xl, ylabel=yl)
    fig.text(0.99, 0.01, "90 m blocks. Landsat imagery courtesy of the U.S. Geological Survey", ha="right",
             fontsize=8, color="0.45")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "l9_replication_preview.png", dpi=150)


def read_tif(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


if __name__ == "__main__":
    main()
