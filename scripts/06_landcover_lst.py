"""Land-cover change (Annual NLCD C1.2, 2013 -> 2025) and its relation to summer LST trends.

1. Resample NLCD subsets (CONUS Albers / WGS 84) onto the Landsat UTM 18N grid:
   Land Cover -> nearest neighbour (categorical); Fractional Impervious -> bilinear (continuous).
2. Within the city (NSA union): 2013->2025 transition matrix, change in impervious (pp).
3. Compare per-pixel LST trends (B relative, C1, C2; OLS deg C/yr) across change classes, and
   regress them on change in impervious at 90 m blocks (3x3 means; closer to the 100 m native
   thermal resolution and less pseudo-replication; p-values still optimistic, see notes).
4. Space-for-time check: does the 12-yr relative-LST change per pp of impervious gained match
   the cross-sectional relation between mean relative LST and impervious?
Open water (class 11 in either year) is excluded from the LST comparisons.

Outputs: data/processed/landcover/. Run: conda run -p .\\env python scripts\\06_landcover_lst.py
"""
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
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
NLCD = ROOT / "data/raw/nlcd"
LST = ROOT / "data/processed/lst_trend"
OUT = ROOT / "data/processed/landcover"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
Y0, Y1 = 2013, 2025
SPAN = Y1 - Y0
NODATA = -9999.0
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)

NAMES = {11: "Open water", 21: "Developed, open space", 22: "Developed, low", 23: "Developed, medium",
         24: "Developed, high", 31: "Barren", 41: "Deciduous forest", 42: "Evergreen forest",
         43: "Mixed forest", 52: "Shrub/scrub", 71: "Grassland", 81: "Pasture/hay", 82: "Cultivated crops",
         90: "Woody wetlands", 95: "Emergent herbaceous wetlands"}
DEV = {21: 1, 22: 2, 23: 3, 24: 4}  # development intensity rank
GREEN = {31, 41, 42, 43, 52, 71, 81, 82, 90, 95}


def to_grid(src_path, profile, resampling, dtype):
    with rasterio.open(src_path) as src:
        dst = np.full((profile["height"], profile["width"]), np.nan if dtype == "float32" else 0, dtype)
        reproject(rasterio.band(src, 1), dst, src_nodata=src.nodata,
                  dst_transform=profile["transform"], dst_crs=profile["crs"],
                  dst_nodata=np.nan if dtype == "float32" else 0, resampling=resampling)
        cmap = src.colormap(1) if resampling == Resampling.nearest else None
    return dst, cmap


def write(path, arr, profile, nodata, dtype, cmap=None, desc=None):
    p = profile.copy()
    p.update(driver="COG", dtype=dtype, nodata=nodata, count=1, compress="DEFLATE")
    for k in ("blockxsize", "blockysize", "tiled", "interleave", "predictor"):
        p.pop(k, None)
    with rasterio.open(path, "w", **p) as d:
        d.write(arr.astype(dtype), 1)
        if cmap:
            d.write_colormap(1, cmap)
        if desc:
            d.set_band_description(1, desc)


def change_class(lc0, lc1, dimp):
    """Meaningful change classes from class codes (never subtracted IDs) and impervious change."""
    out = np.full(lc0.shape, "", dtype=object)
    r0 = np.vectorize(lambda c: DEV.get(c, 0))(lc0)
    r1 = np.vectorize(lambda c: DEV.get(c, 0))(lc1)
    g0, g1 = np.isin(lc0, list(GREEN)), np.isin(lc1, list(GREEN))
    out[(lc0 == lc1)] = "Stable class"
    out[g0 & (r1 > 0)] = "Vegetated/barren -> developed"
    out[(r0 > 0) & g1] = "Developed -> vegetated/barren"
    out[(r0 > 0) & (r1 > r0)] = "Development intensified"
    out[(r0 > 0) & (r1 > 0) & (r1 < r0)] = "Development de-intensified"
    out[g0 & g1 & (lc0 != lc1)] = "Other vegetated change"
    out[(lc0 == 11) | (lc1 == 11)] = "Water"
    return out


def block_mean(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    n = np.isfinite(b).sum((1, 3))
    m = np.nanmean(b, (1, 3))
    return np.where(n >= k * k - 2, m, np.nan)  # need >= 7 of 9 valid pixels


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(LST / "B_rel_slope_ols.tif") as s:
        prof = s.profile.copy()
    nsa = gpd.read_file(NSA)
    city = geometry_mask(nsa.geometry, out_shape=(prof["height"], prof["width"]),
                         transform=prof["transform"], invert=True)

    lc, imp = {}, {}
    for y in (Y0, Y1):
        lc[y], cmap = to_grid(NLCD / f"Annual_NLCD_LndCov_{y}_CU_C1V2_baltimore_subset.tif", prof,
                              Resampling.nearest, "uint8")
        imp[y], _ = to_grid(NLCD / f"Annual_NLCD_FctImp_{y}_CU_C1V2_baltimore_subset.tif", prof,
                            Resampling.bilinear, "float32")
        lc[y] = np.where(city, lc[y], 0)
        imp[y] = np.where(city & (imp[y] <= 100), imp[y], np.nan)
        write(OUT / f"nlcd_lndcov_{y}_utm.tif", lc[y], prof, 0, "uint8", cmap, f"NLCD land cover {y}")
        write(OUT / f"nlcd_fctimp_{y}_utm.tif", np.nan_to_num(imp[y], nan=NODATA), prof, NODATA, "float32",
              desc=f"NLCD fractional impervious {y} (%)")
    dimp = imp[Y1] - imp[Y0]
    write(OUT / f"nlcd_dimp_{Y0}_{Y1}_pp.tif", np.nan_to_num(dimp, nan=NODATA), prof, NODATA, "float32",
          desc=f"change in impervious {Y0}-{Y1} (percentage points)")
    trans = np.where(city, lc[Y0].astype("int32") * 100 + lc[Y1], 0)  # from*100+to, a label, not arithmetic
    write(OUT / f"nlcd_transition_{Y0}_{Y1}.tif", trans, prof, 0, "int32", desc="from_class*100 + to_class")

    # --- transition matrix (km2)
    v = city & (lc[Y0] > 0) & (lc[Y1] > 0)
    tm = pd.crosstab(pd.Series(lc[Y0][v], name=f"from_{Y0}"), pd.Series(lc[Y1][v], name=f"to_{Y1}")) * 900 / 1e6
    tm.index = [f"{c} {NAMES[c]}" for c in tm.index]
    tm.columns = [f"{c} {NAMES[c]}" for c in tm.columns]
    tm.to_csv(OUT / f"transition_matrix_{Y0}_{Y1}_km2.csv", float_format="%.4f")
    changed = (lc[Y0] != lc[Y1]) & v
    print(f"city {v.sum() * 900 / 1e6:.1f} km2; class changed {changed.sum() * 900 / 1e6:.2f} km2 "
          f"({changed.sum() / v.sum():.1%}); mean impervious {np.nanmean(imp[Y0]):.1f} -> {np.nanmean(imp[Y1]):.1f}%")

    # --- LST trends vs change
    slopes = {}
    for k, f in [("B_rel", "B_rel_slope_ols.tif"), ("C1", "C1_slope_ols.tif"), ("C2", "C2_slope_ols.tif"),
                 ("B_rel_mean", "B_mean_rel_lst_C.tif")]:
        with rasterio.open(LST / f) as s:
            a = s.read(1).astype("float64")
            slopes[k] = np.where(a == s.nodata, np.nan, a)
    cc = change_class(lc[Y0], lc[Y1], dimp)
    land = v & (cc != "Water") & np.isfinite(dimp)

    rows = []
    bins = [-101, -20, -5, 5, 20, 101]
    labels = ["<= -20 pp", "-20 to -5 pp", "-5 to +5 pp", "+5 to +20 pp", ">= +20 pp"]
    dbin = pd.cut(pd.Series(dimp[land]), bins, labels=labels)
    groups = [("change_class", pd.Series(cc[land])), ("dimp_bin", dbin)]
    for gname, g in groups:
        for lab in g.dropna().unique():
            sel = (g == lab).values
            r = {"grouping": gname, "class": lab, "pixels": int(sel.sum()), "km2": sel.sum() * 900 / 1e6,
                 "mean_dimp_pp": float(np.nanmean(dimp[land][sel]))}
            for k in ("B_rel", "C1", "C2"):
                x = slopes[k][land][sel]
                r[f"{k}_median"] = float(np.nanmedian(x)) if np.isfinite(x).any() else np.nan
                r[f"{k}_q25"], r[f"{k}_q75"] = (np.nanpercentile(x, [25, 75]) if np.isfinite(x).any() else (np.nan,) * 2)
            rows.append(r)
    cs = pd.DataFrame(rows).sort_values(["grouping", "mean_dimp_pp"])
    cs.to_csv(OUT / "lst_trend_by_change_class.csv", index=False, float_format="%.4f")

    # --- 90 m block regressions
    blk = lambda a: block_mean(np.where(land, a, np.nan))
    bd = blk(dimp)
    res = {}
    for k in ("B_rel", "C1", "C2"):
        by = blk(slopes[k])
        ok = np.isfinite(bd) & np.isfinite(by)
        lr = stats.linregress(bd[ok], by[ok])
        res[f"{k}_vs_dimp_90m"] = {"slope_C_per_yr_per_10pp": lr.slope * 10, "r": lr.rvalue, "p": lr.pvalue,
                                   "n_blocks": int(ok.sum()),
                                   "spearman_rho": float(stats.spearmanr(bd[ok], by[ok]).statistic)}
    # space-for-time: cross-sectional relation of mean relative LST with impervious (2013)
    bm, bi = blk(slopes["B_rel_mean"]), blk(imp[Y0])
    ok = np.isfinite(bm) & np.isfinite(bi)
    cross = stats.linregress(bi[ok], bm[ok])
    temporal = res["B_rel_vs_dimp_90m"]["slope_C_per_yr_per_10pp"] * SPAN
    res["cross_sectional_rel_lst_per_10pp_imp"] = {"slope_C": cross.slope * 10, "r": cross.rvalue, "n_blocks": int(ok.sum())}
    res["temporal_rel_lst_change_per_10pp_gained_over_12yr"] = temporal
    res["area"] = {"city_km2": v.sum() * 900 / 1e6, "class_changed_km2": changed.sum() * 900 / 1e6,
                   "imp_mean_2013": float(np.nanmean(imp[Y0])), "imp_mean_2025": float(np.nanmean(imp[Y1])),
                   "km2_dimp_ge_5pp": float((dimp[land] >= 5).sum() * 900 / 1e6),
                   "km2_dimp_le_-5pp": float((dimp[land] <= -5).sum() * 900 / 1e6)}
    (OUT / "summary.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(cs[["grouping", "class", "km2", "mean_dimp_pp", "B_rel_median", "B_rel_q25", "B_rel_q75",
                  "C1_median", "C2_median"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- preview figure
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    sub = cs[cs.grouping == "dimp_bin"].set_index("class").reindex(labels)
    data = [slopes["B_rel"][land][(dbin == l).values] for l in labels]
    data = [d[np.isfinite(d)] for d in data]
    ax[0].boxplot(data, showfliers=False)
    ax[0].set_xticks(range(1, 6), [f"{l}\n({s:.1f} km²)" for l, s in zip(labels, sub.km2)], fontsize=8)
    ax[0].axhline(0, color="k", lw=0.6)
    ax[0].set(ylabel="Relative LST trend (°C/yr)", title=f"Relative LST trend by impervious change {Y0}–{Y1}")
    ok = np.isfinite(bd) & np.isfinite(blk(slopes["B_rel"]))
    ax[1].hexbin(bd[ok], blk(slopes["B_rel"])[ok], gridsize=50, bins="log", cmap="Greys", extent=(-40, 60, -0.4, 0.4))
    r = res["B_rel_vs_dimp_90m"]
    xx = np.array([-40, 60])
    lr = stats.linregress(bd[ok], blk(slopes["B_rel"])[ok])
    ax[1].plot(xx, lr.intercept + lr.slope * xx, "r-", label=f"{r['slope_C_per_yr_per_10pp']:+.3f} °C/yr per 10 pp, r={r['r']:.2f}")
    ax[1].axhline(0, color="k", lw=0.5); ax[1].axvline(0, color="k", lw=0.5)
    ax[1].set(xlabel="Δ impervious (pp), 90 m blocks", ylabel="Relative LST trend (°C/yr)", title="90 m blocks")
    ax[1].legend(fontsize=8, frameon=False)
    ax[2].hexbin(bi[ok], bm[ok], gridsize=50, bins="log", cmap="Greys")
    xx = np.array([0, 100])
    ax[2].plot(xx, cross.intercept + cross.slope * xx, "r-", label=f"cross-section: {cross.slope * 10:+.2f} °C per 10 pp")
    ax[2].plot(xx, cross.intercept + temporal / 10 * xx, "b--", label=f"temporal (12 yr): {temporal:+.2f} °C per 10 pp")
    ax[2].set(xlabel=f"Impervious {Y0} (%), 90 m blocks", ylabel="Mean relative LST (°C)", title="Space-for-time check")
    ax[2].legend(fontsize=8, frameon=False)
    fig.text(0.99, 0.01, "Landsat imagery courtesy of the U.S. Geological Survey; land cover: USGS Annual NLCD C1.2",
             ha="right", fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(OUT / "landcover_lst_preview.png", dpi=150)


if __name__ == "__main__":
    main()
