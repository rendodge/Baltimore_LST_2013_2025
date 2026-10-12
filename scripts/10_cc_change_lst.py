"""Relate 1 m surface-cover change (Chesapeake Conservancy LULC, 2013/14 -> 2021/22) to summer LST.

Uses the 30 m cover fractions from 09_cc_fractions.py, averaged to 90 m blocks (3x3; closer to
the 100 m thermal resolution). Blocks need full CC coverage in both periods and < 10% water.

1. Cross-section: mean relative LST (B) ~ cover fractions (2013/14).
2. Change: LST trend (B relative, C2) ~ change in each cover group (2021/22 - 2013/14, pp).
   Fractions sum to 100%, so turf is the omitted reference: each coefficient is the effect of
   10 pp of that cover replacing turf grass.
3. Replacement: for blocks that lost >= 5 pp impervious (structures + roads + other), which
   cover gained most, and how does the LST trend differ by replacement? Same for gains.
Regressions are also run on a thinned grid (every 4th block each way, ~360 m spacing) as a
rough check on spatial autocorrelation; full-grid p-values are optimistic.

Outputs: data/processed/cc_lulc/cc_change_*.csv, cc_change_summary.json, preview PNG.
Run: conda run -p .\\env python scripts\\10_cc_change_lst.py
"""
import json
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
CC = ROOT / "data/processed/cc_lulc"
LST = ROOT / "data/processed/lst_trend"
LC = ROOT / "data/processed/landcover"
Y0, Y1 = 2013, 2021
GROUPS = ["canopy", "structures", "roads", "other_imperv", "turf", "bare", "herb_shrub", "water"]
PREDICTORS = ["canopy", "structures", "roads", "other_imperv", "bare", "herb_shrub"]  # turf = reference
LOSS_GAIN = 5.0  # pp impervious change defining loss / gain blocks
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan)


def ols(df, y, xs, label):
    d = df.dropna(subset=[y] + xs)
    fit = sm.OLS(d[y], sm.add_constant(d[xs])).fit()
    ci = fit.conf_int()
    return pd.DataFrame({"model": label, "term": xs, "coef_per_10pp": fit.params[xs].values * 10,
                         "ci95_lo": ci.loc[xs, 0].values * 10, "ci95_hi": ci.loc[xs, 1].values * 10,
                         "p": fit.pvalues[xs].values, "n": int(fit.nobs), "r2": fit.rsquared})


def write_change_maps():
    """30 m change rasters (pp) for display: canopy and impervious (structures + roads + other)."""
    f = lambda g, y: read(CC / f"cc_frac_{g}_{y}_utm.tif")
    imp = {y: f("structures", y) + f("roads", y) + f("other_imperv", y) for y in (Y0, Y1)}
    with rasterio.open(CC / f"cc_frac_canopy_{Y0}_utm.tif") as s:
        prof = s.profile.copy()
    for name, arr in [("canopy", f("canopy", Y1) - f("canopy", Y0)), ("imperv", imp[Y1] - imp[Y0])]:
        with rasterio.open(CC / f"cc_d_{name}_{Y0}_{Y1}_utm.tif", "w", **prof) as d:
            d.write(np.where(np.isfinite(arr), arr, prof["nodata"]).astype("float32"), 1)
            d.set_band_description(1, f"change in {name} {Y0}/14-{Y1}/22 (pp of 30 m cell)")


def main():
    write_change_maps()
    frac ={y: {g: block(read(CC / f"cc_frac_{g}_{y}_utm.tif")) for g in GROUPS} for y in (Y0, Y1)}
    valid = {y: block(read(CC / f"cc_frac_valid_pct_{y}_utm.tif")) for y in (Y0, Y1)}
    df = pd.DataFrame({f"{g}_{y}": frac[y][g].ravel() for y in (Y0, Y1) for g in GROUPS})
    for g in GROUPS:
        df[f"d_{g}"] = df[f"{g}_{Y1}"] - df[f"{g}_{Y0}"]
    for y in (Y0, Y1):
        df[f"imperv_{y}"] = df[[f"{g}_{y}" for g in ("structures", "roads", "other_imperv")]].sum(axis=1, min_count=3)
    df["d_imperv"] = df[f"imperv_{Y1}"] - df[f"imperv_{Y0}"]
    for k, f in [("trend_B_rel", "B_rel_slope_ols.tif"), ("trend_C2", "C2_slope_ols.tif"),
                 ("mean_rel_lst", "B_mean_rel_lst_C.tif")]:
        df[k] = block(read(LST / f)).ravel()
    df["nlcd_dimp"] = block(read(LC / "nlcd_dimp_2013_2025_pp.tif")).ravel()
    bh, bw = frac[Y0]["canopy"].shape
    r, c = np.divmod(np.arange(bh * bw), bw)
    df["thin"] = (r % 4 == 0) & (c % 4 == 0)
    keep = (valid[Y0].ravel() >= 99) & (valid[Y1].ravel() >= 99) & (df[f"water_{Y0}"] < 10) & (df[f"water_{Y1}"] < 10)
    df = df[keep & df.trend_B_rel.notna()].copy()
    print(f"blocks used: {len(df)} (thinned {int(df.thin.sum())})")

    # agreement with NLCD impervious change (different periods: CC 2013/14-2021/22, NLCD 2013-2025)
    agree = df[["d_imperv", "nlcd_dimp"]].dropna().corr().iloc[0, 1]

    # 1-2. regressions
    res = [ols(df, "mean_rel_lst", [f"{g}_{Y0}" for g in PREDICTORS], "cross-section: mean rel LST")]
    for y in ("trend_B_rel", "trend_C2"):
        res.append(ols(df, y, [f"d_{g}" for g in PREDICTORS], f"change: {y}"))
        res.append(ols(df[df.thin], y, [f"d_{g}" for g in PREDICTORS], f"change: {y} (thinned)"))
    coefs = pd.concat(res)
    coefs.to_csv(CC / "cc_change_regression.csv", index=False, float_format="%.5g")

    # 3. replacement classes
    cover = ["canopy", "turf", "bare", "herb_shrub"]
    df["group"] = "stable"
    stable = (df[[f"d_{g}" for g in GROUPS if g != "water"]].abs() < 2).all(axis=1)
    df.loc[~stable, "group"] = "other change"
    loss = df.d_imperv <= -LOSS_GAIN
    gain = df.d_imperv >= LOSS_GAIN
    df.loc[loss, "group"] = "loss -> " + df.loc[loss, [f"d_{g}" for g in cover]].idxmax(axis=1).str[2:]
    df.loc[gain, "group"] = "gain <- " + df.loc[gain, [f"d_{g}" for g in cover]].idxmin(axis=1).str[2:]
    summ = (df.groupby("group")
              .agg(blocks=("trend_B_rel", "size"), d_imperv=("d_imperv", "mean"), d_canopy=("d_canopy", "mean"),
                   d_turf=("d_turf", "mean"), d_bare=("d_bare", "mean"), d_herb=("d_herb_shrub", "mean"),
                   B_rel_median=("trend_B_rel", "median"),
                   B_rel_q25=("trend_B_rel", lambda s: s.quantile(0.25)),
                   B_rel_q75=("trend_B_rel", lambda s: s.quantile(0.75)),
                   C2_median=("trend_C2", "median"))
              .sort_values("d_imperv"))
    summ.to_csv(CC / "cc_change_replacement.csv", float_format="%.4f")

    out = {"blocks": len(df), "blocks_thinned": int(df.thin.sum()), "periods": f"CC {Y0}/14 -> {Y1}/22",
           "corr_cc_dimperv_vs_nlcd_dimp": agree,
           "city_mean_pct": {f"{g}_{y}": float(df[f"{g}_{y}"].mean()) for y in (Y0, Y1) for g in GROUPS}}
    (CC / "cc_change_summary.json").write_text(json.dumps(out, indent=1, default=float))
    pd.set_option("display.width", 220)
    print(json.dumps({k: v for k, v in out.items() if k != "city_mean_pct"}, indent=1, default=float))
    print(coefs.to_string(index=False, float_format=lambda v: f"{v:.4g}"))
    print(summ.to_string(float_format=lambda v: f"{v:.3f}"))

    # preview: trend by replacement class
    order = [g for g in summ.index if g.startswith("loss")] + ["stable"] + [g for g in summ.index if g.startswith("gain")]
    order = [g for g in order if summ.loc[g, "blocks"] >= 10]
    fig, ax = plt.subplots(1, 2, figsize=(16, 6))
    ax[0].boxplot([df.loc[df.group == g, "trend_B_rel"].dropna() for g in order], showfliers=False)
    ax[0].set_xticks(range(1, len(order) + 1), [f"{g}\n(n={summ.loc[g, 'blocks']})" for g in order], rotation=30,
                     ha="right", fontsize=9)
    ax[0].axhline(0, color="0.45", lw=1, ls="--")
    ax[0].set(ylabel="Relative LST trend, B (°C/yr)", title=f"Trend by impervious change and replacement cover (≥{LOSS_GAIN:.0f} pp)")
    m = coefs[coefs.model == "change: trend_B_rel"]
    ax[1].errorbar(m.coef_per_10pp, range(len(m)), xerr=[m.coef_per_10pp - m.ci95_lo, m.ci95_hi - m.coef_per_10pp],
                   fmt="o", color="#3a6ea5", capsize=4)
    ax[1].set_yticks(range(len(m)), [t[2:] for t in m.term])
    ax[1].axvline(0, color="0.45", lw=1, ls="--")
    ax[1].set(xlabel="°C/yr per 10 pp replacing turf grass", title="Relative LST trend vs cover change (90 m blocks)")
    fig.text(0.99, 0.01, "Landsat imagery courtesy of the U.S. Geological Survey; land cover: Chesapeake Conservancy 1 m LULC (2024 Ed.)",
             ha="right", fontsize=8, color="0.45")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(CC / "cc_change_lst_preview.png", dpi=150)


if __name__ == "__main__":
    main()
