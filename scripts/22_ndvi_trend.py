"""Summer NDVI trend (Landsat 8, 2013-2025) and its relation to LST trends in forests.

NDVI from Collection 2 Level-2 surface reflectance: rho = DN * 0.0000275 - 0.2 for SR_B4 (red)
and SR_B5 (NIR); NDVI = (NIR - red) / (NIR + red), valid where both rho are in (0, 1]. Same
QA_PIXEL mask (bits 0-5) and the same variant-B scenes (>= 50% of the city clear) as the LST
trends, July-August; one mean composite per year, per-pixel OLS trend (NDVI units per year).

Tests of the forest-condition hypothesis for the upper Gwynns Falls warming:
  1. NSA series trends of NDVI (same method as 13_nsa_summary.py) for forested NSAs
     (CC canopy >= 55%), comparing the upper-Gwynns NSAs with other forested NSAs.
  2. Stable forest 90 m blocks (CC canopy >= 70% in 2013/14 and 2021/22, change < 2 pp):
     LST trend (C1, relative) ~ NDVI trend, SEs clustered by 1 km tile.
  3. NDVI trend along the named stream corridors (points from 21_stream_corridor_profiles.py).

Outputs: data/processed/ndvi/*.tif, *.csv; figures/ndvi/*.png.
Run after 01 (with SR bands), 02, 04, 09, 13, 21: conda run -p .\\env python scripts\\22_ndvi_trend.py
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
from matplotlib.ticker import MultipleLocator
from rasterio.features import geometry_mask, rasterize
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load_module("lst", ROOT / "scripts/02_lst_trend.py")
N = load_module("nsa", ROOT / "scripts/13_nsa_summary.py")
OUT = ROOT / "data/processed/ndvi"
FIG = ROOT / "figures/ndvi"
CC = ROOT / "data/processed/cc_lulc"
UPPER_GWYNNS = ["Dickeyville", "Franklintown", "Wakefield", "Hunting Ridge", "Gwynns Falls/Leakin Park"]
QA_BITS = 0b111111
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; canopy: Chesapeake Conservancy 1 m LULC"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|invalid value|divide by zero", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def read(p, band=None):
    with rasterio.open(p) as s:
        a = (s.read() if band is None else s.read(band)).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def ndvi_stack(scene_ids):
    out = []
    for sid in scene_ids:
        d = L.RAW / sid
        with rasterio.open(d / f"{sid}_QA_PIXEL_subset.tif") as s:
            qa = s.read(1)
        with rasterio.open(d / f"{sid}_SR_B4_subset.tif") as s:
            red = s.read(1).astype("float32")
        with rasterio.open(d / f"{sid}_SR_B5_subset.tif") as s:
            nir = s.read(1).astype("float32")
        ok = ((qa & QA_BITS) == 0) & (red > 0) & (nir > 0)
        r, n = red * 0.0000275 - 0.2, nir * 0.0000275 - 0.2
        ok &= (r > 0) & (r <= 1) & (n > 0) & (n <= 1)
        out.append(np.where(ok, (n - r) / (n + r), np.nan).astype("float32"))
    return np.stack(out)


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan)


def style(ax):
    ax.grid(which="both", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(which="both", colors="0.35")
    ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=1)
    ax.axvline(0, color="0.45", lw=1.2, ls="--", zorder=1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    with rasterio.open(L.OUT / "B_rel_slope_ols.tif") as s:
        tr, shape, prof = s.transform, s.shape, s.profile.copy()
    nsa = gpd.read_file(N.NSA)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
    scenes, _, _ = L.load_scenes(city)
    use = (scenes.clear_frac_city >= L.MIN_CLEAR).values
    nd = ndvi_stack(scenes.scene_id[use])
    yrs = scenes.year.values[use]
    ann = L.annual_mean(nd, yrs)
    t = L.trends(ann)
    L.write(OUT / "ndvi_annual.tif", ann, prof, city, [str(y) for y in L.YEARS])
    L.write(OUT / "ndvi_mean.tif", np.nanmean(ann, 0), prof, city, ["mean Jul-Aug NDVI"])
    L.write(OUT / "ndvi_slope_ols.tif", t["slope_ols"], prof, city, ["NDVI OLS slope (per yr)"])
    L.write(OUT / "ndvi_p_ols.tif", t["p_ols"], prof, city, ["NDVI OLS p"])
    print(f"scenes {use.sum()}, years {int(np.isfinite(ann[:, city]).any(1).sum())}; "
          f"city median NDVI {np.nanmedian(np.nanmean(ann, 0)[city]):.3f}, median slope {np.nanmedian(t['slope_ols'][city]):+.5f}/yr")

    # --- 1. NSA series trends
    nsa["nsa_id"] = np.arange(1, len(nsa) + 1)
    ids = rasterize(zip(nsa.geometry, nsa.nsa_id), out_shape=shape, transform=tr, fill=0, dtype="int32")
    water = read(CC / "cc_frac_water_2021_utm.tif", 1)
    ids = np.where(np.nan_to_num(water) >= 50, 0, ids)
    rows = []
    for nid, name in zip(nsa.nsa_id, nsa.Name):
        n_px = int((ids == nid).sum())
        if n_px == 0:
            continue
        s = N.series_trend(ann, ids, nid, n_px)
        rows.append({"Name": name, "ndvi_mean": np.nanmean(np.nanmean(ann, 0)[ids == nid]),
                     "ndvi_trend": s["slope"], "ndvi_ci95": s["ci95"], "ndvi_p": s["p"]})
    nt = pd.DataFrame(rows).merge(pd.read_csv(ROOT / "data/processed/nsa/nsa_lst_lc08.csv")[
        ["Name", "pixels", "canopy21", "d_canopy", "mean_rel", "rel_trend", "c1_trend", "c1_ci95", "rel_ci95"]], on="Name")
    nt["ndvi_q"] = N.bh_q(nt.ndvi_p)
    nt["group"] = np.where(nt.Name.isin(UPPER_GWYNNS), "Upper Gwynns Falls", "Other")
    nt.to_csv(OUT / "nsa_ndvi_trend.csv", index=False, float_format="%.5f")
    forest = nt[(nt.canopy21 >= 55) & (nt.pixels >= 100)].copy()
    pd.set_option("display.width", 220)
    show = ["Name", "group", "canopy21", "d_canopy", "ndvi_mean", "ndvi_trend", "ndvi_ci95", "ndvi_p", "c1_trend", "rel_trend"]
    print("\nForested NSAs (canopy >= 55%):\n", forest.sort_values("ndvi_trend")[show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    g = forest.groupby("group")[["ndvi_trend", "c1_trend", "rel_trend", "d_canopy"]].mean()
    print("\ngroup means:\n", g.round(4).to_string())
    mw = stats.mannwhitneyu(forest.loc[forest.group == "Upper Gwynns Falls", "ndvi_trend"],
                            forest.loc[forest.group == "Other", "ndvi_trend"])
    rho_f = stats.spearmanr(forest.ndvi_trend, forest.c1_trend)
    print(f"Mann-Whitney upper Gwynns vs other forested NSAs (NDVI trend): p = {mw.pvalue:.3f}; "
          f"Spearman NDVI trend vs C1 trend across forested NSAs: {rho_f.statistic:+.2f} (p {rho_f.pvalue:.3f}), n = {len(forest)}")

    # --- 2. stable forest blocks
    can13 = block(read(CC / "cc_frac_canopy_2013_utm.tif", 1)).ravel()
    can21 = block(read(CC / "cc_frac_canopy_2021_utm.tif", 1)).ravel()
    b = pd.DataFrame({"ndvi_trend": block(t["slope_ols"]).ravel(), "can21": can21, "dcan": can21 - can13,
                      "c1_trend": block(read(L.OUT / "C1_slope_ols.tif", 1)).ravel(),
                      "rel_trend": block(read(L.OUT / "B_rel_slope_ols.tif", 1)).ravel(),
                      "ids": block(np.where(ids > 0, ids, np.nan).astype(float)).ravel()})
    bh, bw = block(t["slope_ols"]).shape
    r, c = np.divmod(np.arange(bh * bw), bw)
    b["tile"] = (r // 11) * 1000 + (c // 11)
    sf = b[(can13 >= 70) & (can21 >= 70) & (b.dcan.abs() < 2)].dropna(subset=["ndvi_trend", "c1_trend", "rel_trend"]).copy()
    names = dict(zip(nsa.nsa_id, nsa.Name))
    sf["upper_gwynns"] = sf.ids.round().map(names).isin(UPPER_GWYNNS)
    res = {}
    for y in ("c1_trend", "rel_trend"):
        f = smf.ols(f"{y} ~ I(ndvi_trend * 100)", data=sf).fit(cov_type="cluster", cov_kwds={"groups": sf.tile})
        k = "I(ndvi_trend * 100)"
        res[y] = (f.params[k], *f.conf_int().loc[k], f.pvalues[k], stats.spearmanr(sf.ndvi_trend, sf[y]).statistic)
        print(f"stable forest blocks: {y} = {f.params[k]:+.3f} °C/yr per +0.01 NDVI/yr "
              f"[{res[y][1]:+.3f}, {res[y][2]:+.3f}], p {res[y][3]:.3g}, Spearman {res[y][4]:+.2f}, n = {len(sf)}")
    print("stable forest blocks, upper Gwynns vs elsewhere (median NDVI trend, C1 trend):\n",
          sf.groupby("upper_gwynns")[["ndvi_trend", "c1_trend", "rel_trend"]].median().round(5).to_string())
    sf.to_csv(OUT / "stable_forest_blocks.csv", index=False, float_format="%.5f")

    # --- 3. corridors
    prof_pts = pd.read_csv(ROOT / "data/processed/streams/corridor_profiles.csv")
    slope = t["slope_ols"]
    H, W = slope.shape
    vals = []
    for x, y in zip(prof_pts.x, prof_pts.y):
        c0, r0 = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
        yy, xx = np.mgrid[max(r0 - 5, 0):min(r0 + 6, H), max(c0 - 5, 0):min(c0 + 6, W)]
        m = np.hypot(tr.c + (xx + 0.5) * 30 - x, tr.f + (yy + 0.5) * tr.e - y) <= 135
        vals.append(np.nanmean(slope[yy[m], xx[m]]))
    prof_pts["ndvi_trend"] = vals
    prof_pts["section"] = prof_pts.groupby("stream").dist_km.transform(
        lambda d: pd.cut(d, 3, labels=["lower", "middle", "upper"]).astype(str))
    cor = prof_pts.groupby(["stream", "section"])[["canopy", "ndvi_trend"]].mean()
    cor.to_csv(OUT / "corridor_ndvi_trend.csv", float_format="%.5f")
    print("\ncorridor NDVI trend:\n", cor.round(5).to_string())

    # --- figures
    fig, ax = plt.subplots(figsize=(10, 7.5))
    for grp, colr, mk, s_ in [("Other", "#8c8c8c", "o", 60), ("Upper Gwynns Falls", "#b2182b", "D", 90)]:
        d = forest[forest.group == grp]
        ax.scatter(d.ndvi_trend * 100, d.c1_trend, s=s_, marker=mk, color=colr, edgecolor="white", lw=0.8,
                   label=f"{grp} (n={len(d)})", zorder=3)
    for _, row in forest[forest.group == "Upper Gwynns Falls"].iterrows():
        ax.annotate(row.Name.replace("Gwynns Falls/", ""), (row.ndvi_trend * 100, row.c1_trend), xytext=(6, 4),
                    textcoords="offset points", fontsize=12, color="#b2182b")
    style(ax)
    ax.set(xlabel="NDVI trend (0.01 per year)", ylabel="LST trend, C1: climate kept (°C/yr)",
           title="Forested neighbourhoods: greenness vs LST trend")
    ax.legend(fontsize=14, frameon=False, loc="center left")
    fig.text(0.99, 0.01, f"NSAs with ≥ 55% canopy (CC 2021/22). Spearman ρ = {rho_f.statistic:+.2f} (p = {rho_f.pvalue:.2f}); "
             f"upper Gwynns vs other NDVI trend, Mann-Whitney p = {mw.pvalue:.2f}.\nLandsat 8 Jul–Aug, 2013–2025. {CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG / "forest_nsa_ndvi_vs_lst_trend.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 7.5))
    samp = sf.sample(min(600, len(sf)), random_state=42)
    ax.scatter(samp.ndvi_trend * 100, samp.c1_trend, s=30, color="#3a6ea5", edgecolor="white", lw=0.6, alpha=0.5, zorder=2)
    bins = pd.qcut(sf.ndvi_trend, 10)
    gm = sf.groupby(bins, observed=True)[["ndvi_trend", "c1_trend"]].median()
    ax.plot(gm.ndvi_trend * 100, gm.c1_trend, "o-", color="#1d3f6e", lw=2, ms=8, zorder=4, label="Median by NDVI-trend decile")
    style(ax)
    ax.set(xlabel="NDVI trend (0.01 per year)", ylabel="LST trend, C1: climate kept (°C/yr)",
           title="Stable forest blocks: greenness vs LST trend")
    ax.legend(fontsize=14, frameon=False, loc="upper right")
    e = res["c1_trend"]
    fig.text(0.99, 0.01, f"{len(sf):,} 90 m blocks with ≥ 70% canopy in both periods (change < 2 pp); dots: random {len(samp)}.\n"
             f"Slope {e[0]:+.2f} °C/yr per +0.01 NDVI/yr (95% CI {e[1]:+.2f} to {e[2]:+.2f}, tile-clustered).\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.09, 1, 1))
    fig.savefig(FIG / "stable_forest_ndvi_vs_lst_trend.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
