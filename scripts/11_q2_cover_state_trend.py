"""Q2: did areas with different (unchanging) land cover warm differently? Chesapeake 1 m LULC.

Stable blocks only: 90 m blocks whose cover fractions changed < 2 pp in every group between
2013/14 and 2021/22 (CC), with full CC coverage and < 10% water, so cover *change* (Q3) does
not leak in. Cover state = 2013/14 fractions.

1. Pixel trends by cover state: relative trend (B) and absolute weather-normalized trend (C1)
   by decile of impervious (structures + roads + other) and of canopy, and by cover type
   (ordered rules: canopy >= 50% -> roof-dominated (structures >= 35%) -> pavement-dominated
   (roads + other impervious >= 50%) -> turf >= 35% -> herbaceous/shrub >= 35% -> mixed).
   B and C1 subtract a per-scene constant from every pixel, so differences *between* cover
   states are nearly identical in both; only the level differs.
   95% CIs from a spatial block bootstrap (1 km tiles = 11 x 11 blocks, 1000 resamples).
2. Weather-adjusted trend per cover type with its own air-temperature sensitivity: for each
   variant-B scene, the median LST of each type's stable blocks is regressed on BWI air
   temperature at overpass and year (LST ~ T_air + year). Also the type-minus-all-stable gap
   ~ T_air + year: a T_air slope means the gap widens on hotter days (amplification); a year
   slope means the gap changed over time with weather held constant.

Outputs: data/processed/cc_lulc/q2_*.csv, q2_*.png. Run after 02, 04, 09:
  conda run -p .\\env python scripts\\11_q2_cover_state_trend.py
"""
import importlib.util
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

ROOT = Path(__file__).resolve().parents[1]
CC = ROOT / "data/processed/cc_lulc"
LST = ROOT / "data/processed/lst_trend"
GROUPS = ["canopy", "structures", "roads", "other_imperv", "turf", "bare", "herb_shrub", "water"]
STABLE_PP = 2.0
TILE = 11          # blocks per bootstrap tile side (~1 km)
N_BOOT = 1000
SEED = 42
TYPES = ["Tree canopy", "Turf-dominated", "Herbaceous/shrub", "Mixed", "Pavement-dominated", "Roof-dominated"]
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def block(a, k=3):
    """3x3 block mean (>= 7 valid) for a 2-D array or a stack of 2-D arrays."""
    h, w = (a.shape[-2] // k) * k, (a.shape[-1] // k) * k
    b = a[..., :h, :w].reshape(a.shape[:-2] + (h // k, k, w // k, k))
    return np.where(np.isfinite(b).sum((-3, -1)) >= k * k - 2, np.nanmean(b, (-3, -1)), np.nan)


def cover_type(d):
    t = np.full(len(d), "Mixed", dtype=object)
    rules = [("Herbaceous/shrub", d.herb_shrub >= 35), ("Turf-dominated", d.turf >= 35),
             ("Pavement-dominated", d.paved >= 50), ("Roof-dominated", d.structures >= 35),
             ("Tree canopy", d.canopy >= 50)]
    for name, cond in rules:  # applied in reverse priority, so the last rule wins
        t[cond.values] = name
    return t


def boot_medians(d, col, by, rng):
    """Median of `col` per category of `by`, with 95% CI from resampling tiles."""
    tiles = d.tile.values
    uniq = np.unique(tiles)
    idx_by_tile = {t: np.flatnonzero(tiles == t) for t in uniq}
    cats = d[by].values
    vals = d[col].values
    point = d.groupby(by)[col].median()
    reps = []
    for _ in range(N_BOOT):
        pick = np.concatenate([idx_by_tile[t] for t in rng.choice(uniq, len(uniq), replace=True)])
        s = pd.Series(vals[pick]).groupby(cats[pick]).median()
        reps.append(s)
    reps = pd.DataFrame(reps)
    return pd.DataFrame({"median": point, "ci_lo": reps.quantile(0.025), "ci_hi": reps.quantile(0.975),
                         "blocks": d.groupby(by)[col].size()})


def main():
    rng = np.random.default_rng(SEED)
    fr = {y: {g: block(read(CC / f"cc_frac_{g}_{y}_utm.tif")) for g in GROUPS} for y in (2013, 2021)}
    va = {y: block(read(CC / f"cc_frac_valid_pct_{y}_utm.tif")) for y in (2013, 2021)}
    bh, bw = fr[2013]["canopy"].shape
    d = pd.DataFrame({g: fr[2013][g].ravel() for g in GROUPS})
    d["imperv"] = d.structures + d.roads + d.other_imperv
    d["paved"] = d.roads + d.other_imperv
    d["trend_B_rel"] = block(read(LST / "B_rel_slope_ols.tif")).ravel()
    d["trend_C1"] = block(read(LST / "C1_slope_ols.tif")).ravel()
    r, c = np.divmod(np.arange(bh * bw), bw)
    d["tile"] = (r // TILE) * 1000 + (c // TILE)
    stable = np.logical_and.reduce([np.abs(fr[2021][g] - fr[2013][g]).ravel() < STABLE_PP
                                    for g in GROUPS if g != "water"])
    keep = stable & (va[2013].ravel() >= 99) & (va[2021].ravel() >= 99) & (d.water < 10).values
    keep &= d.trend_B_rel.notna().values & d.trend_C1.notna().values
    d["block_id"] = np.arange(bh * bw)
    d = d[keep].copy()
    d["type"] = cover_type(d)
    d["imperv_decile"] = pd.qcut(d.imperv, 10, labels=False, duplicates="drop") + 1
    d["canopy_decile"] = pd.qcut(d.canopy.rank(method="first"), 10, labels=False) + 1
    print(f"stable blocks: {len(d)}; tiles: {d.tile.nunique()}")

    # --- 1. trends by cover state
    tables = []
    for by in ("imperv_decile", "canopy_decile", "type"):
        for col in ("trend_B_rel", "trend_C1"):
            t = boot_medians(d, col, by, rng)
            t["grouping"], t["trend"] = by, col
            mean_cov = d.groupby(by)[["imperv", "canopy", "structures", "paved", "turf"]].mean()
            tables.append(t.join(mean_cov).reset_index(names="category"))
    q2 = pd.concat(tables)
    q2.to_csv(CC / "q2_trend_by_cover_state.csv", index=False, float_format="%.4f")
    # continuous: Spearman of trend with impervious / canopy, and an OLS on fractions (turf reference)
    fit = smf.ols("trend_B_rel ~ canopy + structures + roads + other_imperv + herb_shrub + bare", data=d).fit()
    thin = d[(d.block_id // bw % 4 == 0) & (d.block_id % bw % 4 == 0)]
    fit_t = smf.ols("trend_B_rel ~ canopy + structures + roads + other_imperv + herb_shrub + bare", data=thin).fit()
    coefs = pd.DataFrame({"coef_per_10pp": fit.params * 10, "p": fit.pvalues,
                          "coef_thinned_per_10pp": fit_t.params * 10, "p_thinned": fit_t.pvalues}).drop("Intercept")
    coefs.to_csv(CC / "q2_trend_vs_fractions_ols.csv", float_format="%.5g")

    # --- 2. per-type weather-adjusted trend with type-specific air-temperature sensitivity
    lstm = load_module("lst", ROOT / "scripts/02_lst_trend.py")
    with rasterio.open(LST / "B_rel_slope_ols.tif") as s:
        tr, shape = s.transform, s.shape
    city = geometry_mask(gpd.read_file(lstm.NSA).to_crs(32618).geometry, out_shape=shape, transform=tr, invert=True)
    scenes, stack, _ = lstm.load_scenes(city)
    wx = pd.read_csv(LST / "C_scene_weather.csv")[["scene_id", "tair_C"]]
    scenes = scenes.merge(wx, on="scene_id", how="left")
    use = ((scenes.clear_frac_city >= lstm.MIN_CLEAR) & scenes.tair_C.notna()).values
    bstack = block(stack[use].astype("float64")).reshape(int(use.sum()), -1)[:, d.block_id.values]
    sc = scenes[use].reset_index(drop=True)
    rows = []
    for i in range(len(sc)):
        v = bstack[i]
        ok = np.isfinite(v)
        if ok.mean() < 0.5:
            continue
        allmed = np.median(v[ok])
        for t in TYPES:
            m = ok & (d.type.values == t)
            if m.sum() >= 30 and m.sum() >= 0.5 * (d.type.values == t).sum():
                rows.append({"scene_id": sc.scene_id[i], "year": sc.year[i], "tair_C": sc.tair_C[i], "type": t,
                             "median_lst": np.median(v[m]), "gap_vs_all_stable": np.median(v[m]) - allmed})
    sm = pd.DataFrame(rows)
    sm.to_csv(CC / "q2_scene_type_medians.csv", index=False, float_format="%.3f")
    wrows = []
    for t in TYPES:
        s_ = sm[sm.type == t]
        if len(s_) < 8:
            continue
        f1 = smf.ols("median_lst ~ tair_C + year", data=s_).fit()
        f2 = smf.ols("gap_vs_all_stable ~ tair_C + year", data=s_).fit()
        wrows.append({"type": t, "scenes": len(s_), "b_tair": f1.params.tair_C, "b_tair_se": f1.bse.tair_C,
                      "adj_trend_C_per_yr": f1.params.year, "adj_trend_lo": f1.conf_int().loc["year", 0],
                      "adj_trend_hi": f1.conf_int().loc["year", 1], "adj_trend_p": f1.pvalues.year,
                      "mean_gap_C": s_.gap_vs_all_stable.mean(),
                      "gap_tair_slope": f2.params.tair_C, "gap_tair_p": f2.pvalues.tair_C,
                      "gap_year_slope": f2.params.year, "gap_year_lo": f2.conf_int().loc["year", 0],
                      "gap_year_hi": f2.conf_int().loc["year", 1], "gap_year_p": f2.pvalues.year})
    wa = pd.DataFrame(wrows)
    wa.to_csv(CC / "q2_type_weather_adjusted.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 220)
    show = q2[q2.trend == "trend_B_rel"][["grouping", "category", "blocks", "imperv", "canopy", "median", "ci_lo", "ci_hi"]]
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    c1 = q2[(q2.trend == "trend_C1") & (q2.grouping == "type")][["category", "median", "ci_lo", "ci_hi"]]
    print("\nC1 (absolute) by type:\n", c1.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print("\nOLS trend_B_rel ~ fractions (turf reference), per 10 pp:\n", coefs.to_string(float_format=lambda v: f"{v:.4g}"))
    print("\nweather-adjusted by type:\n", wa.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # --- preview
    fig, ax = plt.subplots(1, 3, figsize=(19, 5.5))
    for a, by, xl in [(ax[0], "imperv_decile", "Impervious decile (1 = least)"),
                      (ax[1], "canopy_decile", "Canopy decile (1 = least)")]:
        t = q2[(q2.grouping == by) & (q2.trend == "trend_B_rel")].sort_values("category")
        a.errorbar(t.category, t["median"], yerr=[t["median"] - t.ci_lo, t.ci_hi - t["median"]], fmt="o-",
                   color="#3a6ea5", capsize=3)
        a.axhline(0, color="0.45", lw=1, ls="--")
        a.set(xlabel=xl, ylabel="Median relative LST trend (°C/yr)", title=f"Stable blocks by {by.split('_')[0]} decile")
        a.set_xticks(range(1, 11))
    t = q2[(q2.grouping == "type") & (q2.trend == "trend_B_rel")].set_index("category").reindex(TYPES).dropna(subset=["median"])
    ax[2].errorbar(range(len(t)), t["median"], yerr=[t["median"] - t.ci_lo, t.ci_hi - t["median"]], fmt="o",
                   color="#3a6ea5", capsize=4)
    ax[2].set_xticks(range(len(t)), [f"{i}\n(n={int(n)})" for i, n in zip(t.index, t.blocks)], rotation=25, ha="right")
    ax[2].axhline(0, color="0.45", lw=1, ls="--")
    ax[2].set(ylabel="Median relative LST trend (°C/yr)", title="Stable blocks by cover type")
    fig.text(0.99, 0.01, "95% CI: spatial block bootstrap (1 km tiles). Landsat courtesy of USGS; land cover: Chesapeake Conservancy 1 m LULC",
             ha="right", fontsize=8, color="0.45")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CC / "q2_trend_by_cover_state_preview.png", dpi=150)


if __name__ == "__main__":
    main()
