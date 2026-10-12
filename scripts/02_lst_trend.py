"""Baltimore summer (Jul-Aug) LST composites and per-pixel trends, Landsat 8, 2013-2025.

Inputs: native-grid subsets from 01_acquire_landsat.py (ST_B10, QA_PIXEL, ST_QA), NSA boundaries.

Two variants, computed side by side:
  A  "GEE replication": every clear pixel of every scene -> per-pixel annual mean LST (deg C)
     -> OLS slope. Matches the original GEE script (QA_PIXEL bits 0-5 masked, >= 8 valid years).
  B  "Filtered relative": only scenes with >= MIN_CLEAR of the city clear; each scene converted
     to relative LST (pixel minus that scene's city median) -> annual mean -> OLS slope with
     p-value, Theil-Sen slope, Mann-Kendall p. Also an absolute annual mean from the same scenes.

Outputs (float32 COG, DEFLATE, nodata -9999) and tables in data/processed/lst_trend/.
Run: conda run -p .\\env python scripts\\02_lst_trend.py
"""
import json
import os
import warnings
from datetime import date
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/landsat"
NSA = ROOT / "data/vector/Neighborhood_Statistical_Area_(NSA)_Boundaries/Neighborhood_Statistical_Area_(NSA)_Boundaries.shp"
# Sensor set from env var LST_SENSORS (default Landsat 8 only), e.g. LST_SENSORS=LC08,LC09.
SENSORS = tuple(os.environ.get("LST_SENSORS", "LC08").split(","))
OUT = ROOT / "data/processed" / ("lst_trend" if SENSORS == ("LC08",) else "lst_trend_" + "_".join(SENSORS).lower())
YEARS = np.arange(2013, 2026)
QA_BITS = 0b111111   # fill, dilated cloud, cirrus, cloud, shadow, snow (as in the GEE script)
MIN_CLEAR = 0.5      # variant B: min clear fraction of city pixels for a scene to be used
MIN_YEARS = 8        # min valid annual composites for a pixel trend
NODATA = -9999.0
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)


def load_scenes(city, sensors=("LC08",)):
    recs, lst = [], []
    for d in sorted(p for s in sensors for p in RAW.glob(f"{s}_*")):
        sid = d.name
        with rasterio.open(d / f"{sid}_ST_B10_subset.tif") as s:
            st = s.read(1)
            profile = s.profile
        with rasterio.open(d / f"{sid}_QA_PIXEL_subset.tif") as s:
            qa = s.read(1)
        with rasterio.open(d / f"{sid}_ST_QA_subset.tif") as s:
            stqa = s.read(1)
        clear = ((qa & QA_BITS) == 0) & (st > 0)
        t = np.where(clear, st * 0.00341802 + 149.0 - 273.15, np.nan).astype("float32")
        tc = t[city]
        n_clear = np.isfinite(tc).sum()
        unc = stqa[city & clear]
        recs.append({
            "scene_id": sid, "sensor": sid[:4], "date": pd.Timestamp(sid[17:25]), "year": int(sid[17:21]),
            "clear_frac_city": n_clear / city.sum(),
            "lst_p05": np.nanpercentile(tc, 5) if n_clear else np.nan,
            "lst_median": np.nanmedian(tc) if n_clear else np.nan,
            "lst_p95": np.nanpercentile(tc, 95) if n_clear else np.nan,
            "st_qa_median_K": np.median(unc[unc > 0]) * 0.01 if (unc > 0).any() else np.nan,
        })
        lst.append(t)
    return pd.DataFrame(recs), np.stack(lst), profile


def annual_mean(stack, years_of_scene):
    out = np.full((len(YEARS),) + stack.shape[1:], np.nan, "float32")
    for i, y in enumerate(YEARS):
        sel = years_of_scene == y
        if sel.any():
            out[i] = np.nanmean(stack[sel], axis=0)
    return out


def trends(annual):
    """Per-pixel OLS (slope, p), Theil-Sen slope, Mann-Kendall p, n, on years since 2013."""
    x = (YEARS - YEARS[0]).astype("float64")[:, None, None]
    Y = annual.astype("float64")
    m = np.isfinite(Y)
    n = m.sum(0)
    X = np.where(m, x, np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        xm, ym = np.nanmean(X, 0), np.nanmean(Y, 0)
        sxx = np.nansum((X - xm) ** 2, 0)
        slope = np.nansum((X - xm) * (Y - ym), 0) / sxx
        resid = Y - (ym + slope * (X - xm))
        se = np.sqrt(np.nansum(resid ** 2, 0) / (n - 2) / sxx)
        p_ols = 2 * stats.t.sf(np.abs(slope / se), n - 2)
        # Theil-Sen and Mann-Kendall over all year pairs
        i, j = np.triu_indices(len(YEARS), 1)
        d = Y[j] - Y[i]
        sen = np.nanmedian(d / (x[j] - x[i]), 0)
        s = np.nansum(np.sign(d), 0)
        var = n * (n - 1) * (2 * n + 5) / 18.0
        z = np.where(s > 0, (s - 1) / np.sqrt(var), np.where(s < 0, (s + 1) / np.sqrt(var), 0))
        p_mk = 2 * stats.norm.sf(np.abs(z))
    ok = n >= MIN_YEARS
    f = lambda a: np.where(ok, a, np.nan).astype("float32")
    return {"slope_ols": f(slope), "p_ols": f(p_ols), "slope_sen": f(sen), "p_mk": f(p_mk),
            "n_years": n.astype("float32")}


def write(path, arr, profile, city, desc):
    if arr.ndim == 2:
        arr = arr[None]
    data = np.where(np.isfinite(arr) & city[None], arr, NODATA).astype("float32")
    p = profile.copy()
    p.update(driver="COG", dtype="float32", nodata=NODATA, count=data.shape[0],
             compress="DEFLATE", predictor=3)
    for k in ("blockxsize", "blockysize", "tiled", "interleave"):
        p.pop(k, None)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(data)
        for b, dsc in enumerate(desc, 1):
            dst.set_band_description(b, dsc)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(next(RAW.glob("LC08_*/*_ST_B10_subset.tif"))) as s:
        tr, shape = s.transform, s.shape
    nsa = gpd.read_file(NSA).to_crs(32618)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)

    scenes, lst, profile = load_scenes(city, SENSORS)
    scenes["used_B"] = scenes.clear_frac_city >= MIN_CLEAR
    scenes.to_csv(OUT / "scene_table.csv", index=False, float_format="%.3f")
    yrs = scenes.year.values

    # --- Variant A: GEE replication
    annA = annual_mean(lst, yrs)
    trA = trends(annA)
    meanA = np.nanmean(annA, 0)

    # --- Variant B: filtered scenes, relative LST
    useB = scenes.used_B.values
    rel = lst[useB] - scenes.loc[useB, "lst_median"].values[:, None, None].astype("float32")
    annB_rel = annual_mean(rel, yrs[useB])
    annB_abs = annual_mean(lst[useB], yrs[useB])
    trB = trends(annB_rel)
    trB_abs = trends(annB_abs)

    span = YEARS[-1] - YEARS[0]
    yb = [str(y) for y in YEARS]
    write(OUT / "A_annual_lst_C.tif", annA, profile, city, yb)
    write(OUT / "A_mean_lst_C.tif", meanA, profile, city, ["mean annual Jul-Aug LST (C)"])
    write(OUT / "A_slope_C_per_yr.tif", trA["slope_ols"], profile, city, ["OLS slope (C/yr)"])
    write(OUT / "A_change_C.tif", trA["slope_ols"] * span, profile, city, [f"OLS slope x {span} yr (C)"])
    write(OUT / "A_p_ols.tif", trA["p_ols"], profile, city, ["OLS p-value"])
    write(OUT / "A_n_years.tif", trA["n_years"], profile, city, ["valid annual composites"])
    write(OUT / "B_annual_rel_lst_C.tif", annB_rel, profile, city, yb)
    write(OUT / "B_mean_rel_lst_C.tif", np.nanmean(annB_rel, 0), profile, city, ["mean relative LST (C, vs city median)"])
    write(OUT / "B_mean_lst_C.tif", np.nanmean(annB_abs, 0), profile, city, ["mean annual Jul-Aug LST (C), filtered scenes"])
    for k, v in trB.items():
        write(OUT / f"B_rel_{k}.tif", v, profile, city, [f"{k} (relative LST)"])
    write(OUT / "B_abs_slope_ols.tif", trB_abs["slope_ols"], profile, city, ["OLS slope absolute LST (C/yr), filtered scenes"])
    write(OUT / "B_abs_p_ols.tif", trB_abs["p_ols"], profile, city, ["OLS p-value absolute LST, filtered scenes"])

    # --- City time series
    rows = []
    yrB = [i for i, y in enumerate(YEARS) if np.isfinite(annB_abs[i][city]).any()]
    common = np.isfinite(annB_abs[yrB]).all(0) & city
    for i, y in enumerate(YEARS):
        a, b = annA[i][city], annB_abs[i][city]
        rows.append({
            "year": y,
            "n_scenes": int((yrs == y).sum()), "n_scenes_B": int(((yrs == y) & useB).sum()),
            "A_cover": np.isfinite(a).mean(), "A_city_mean_C": np.nanmean(a) if np.isfinite(a).any() else np.nan,
            "B_cover": np.isfinite(b).mean(), "B_city_mean_C": np.nanmean(b) if np.isfinite(b).any() else np.nan,
            "B_common_px_mean_C": np.nanmean(annB_abs[i][common]) if i in yrB else np.nan,
        })
    ts = pd.DataFrame(rows)
    ts.to_csv(OUT / "city_timeseries.csv", index=False, float_format="%.3f")

    def cityfit(col):
        d = ts.dropna(subset=[col])
        r = stats.linregress(d.year, d[col])
        return {"slope": r.slope, "p": r.pvalue, "r2": r.rvalue ** 2, "n": len(d)}

    summary = {
        "run": date.today().isoformat(), "scenes": len(scenes), "scenes_used_B": int(useB.sum()),
        "common_pixels_B": int(common.sum()), "city_pixels": int(city.sum()),
        "city_trend_A": cityfit("A_city_mean_C"), "city_trend_B_common": cityfit("B_common_px_mean_C"),
    }
    for name, tr in [("A", trA), ("B_rel", trB), ("B_abs", trB_abs)]:
        s, p = tr["slope_ols"][city], tr["p_ols"][city]
        v = np.isfinite(s)
        summary[f"pixels_{name}"] = {
            "valid": int(v.sum()), "slope_mean": float(np.nanmean(s)), "slope_median": float(np.nanmedian(s)),
            "slope_p05_p95": [float(q) for q in np.nanpercentile(s, [5, 95])],
            "frac_p_lt_0.05": float((p[v] < 0.05).mean()),
            "frac_p_lt_0.05_pos": float(((p[v] < 0.05) & (s[v] > 0)).mean()),
            "frac_p_lt_0.05_neg": float(((p[v] < 0.05) & (s[v] < 0)).mean()),
        }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
    print(json.dumps(summary, indent=1, default=float))
    print(ts.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    # --- Preview chart
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for col, lab, c in [("A_city_mean_C", "A: all clear pixels (GEE method)", "#d73027"),
                        ("B_common_px_mean_C", f"B: scenes >= {MIN_CLEAR:.0%} clear, common pixels", "#4575b4")]:
        d = ts.dropna(subset=[col])
        ax.plot(d.year, d[col], "o-", color=c, label=lab)
        r = stats.linregress(d.year, d[col])
        ax.plot(d.year, r.intercept + r.slope * d.year, "--", color=c, lw=1,
                label=f"  OLS {r.slope:+.2f} C/yr, p={r.pvalue:.2f}, n={len(d)}")
    ax.set(xlabel="Year", ylabel="Mean LST (°C)", title="Baltimore City mean July–August LST, Landsat 8 (preliminary)")
    ax.set_xticks(YEARS)
    ax.legend(fontsize=8, frameon=False)
    ax.text(0.99, 0.01, "Landsat imagery courtesy of the U.S. Geological Survey", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(OUT / "city_timeseries_preview.png", dpi=150)


if __name__ == "__main__":
    main()
