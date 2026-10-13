"""Riparian forest buffer width vs summer LST along Baltimore's open stream channels.

Sample points every 150 m along Chesapeake hyper-resolution reaches with an open channel
(cnctR < 0.5). Around each point (300 m radius), the CC 2021/22 1 m land cover gives canopy
fraction in distance bands from the channel (water pixels excluded from the denominator).
Forested buffer width = outer edge of the last band such that every band from the channel outward
has >= 50% canopy. Bands are distances from the channel with both banks pooled, so the width is a
PER-SIDE distance (corridor total ~2x); 0 if the 0-10 m band is < 50% canopy.

Outcomes (Landsat 8 Jul-Aug mean relative LST, variant B, 30 m pixels within 150 m along-stream):
  corridor  = pixels whose centres are <= 45 m from the channel
  spillover = pixels 100-200 m from the channel (cooling reaching the neighbourhood)
Model: outcome ~ C(width class, ref < 10 m) + impervious share 300-600 m from the point (wider
context), OLS with SEs clustered by 1 km tile; also a continuous hinge search for the width where
cooling levels off. Thermal data are acquired at ~100 m, so width effects below ~50-100 m are only
partly resolved.

Outputs: data/processed/streams/buffer_width_points.csv, buffer_width_model.csv,
figures/stream_distance/buffer_width.png. Run: conda run -p .\\env python scripts\\26_buffer_width.py
"""
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import shapely
import statsmodels.formula.api as smf
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
LULC = ROOT / "data/raw/cc_lulc/balt_24510_lulc_2021_2024-Edition.tif"
STREAMS = ROOT / "data/vector/streams_cc_city.gpkg"
LST = ROOT / "data/processed/lst_trend/B_mean_rel_lst_C.tif"
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/stream_distance"
CANOPY = [23, 24, 25, 26, 40, 41, 53, 54, 55, 63, 64, 65, 73, 74, 75]
IMPERV = [20, 21, 22, 31, 32]
WATER = [10, 11, 12, 13, 14]
BANDS = [0, 10, 20, 30, 50, 75, 100, 150, 200, 300]
WIDTH_BINS = [-1, 9, 29, 49, 99, 199, 1000]
WIDTH_LABELS = ["<10", "10-30", "30-50", "50-100", "100-200", "≥200"]
STEP, RADIUS, ALONG = 150, 300, 150
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; land cover and streams: Chesapeake Conservancy / UMBC"
warnings.filterwarnings("ignore", "Mean of empty slice|invalid value", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def main():
    cc = gpd.read_file(STREAMS)
    open_ = cc[cc.cnctR < 0.5].copy()
    with rasterio.open(LULC) as lu:
        lcrs = lu.crs
    open_lu = open_.to_crs(lcrs)
    with rasterio.open(LST) as s:
        lst = s.read(1).astype(float)
        lst[lst == s.nodata] = np.nan
        ltr = s.transform
    H, W = lst.shape

    pts = []
    for idx, g in zip(open_.index, open_.geometry):
        for d in np.arange(STEP / 2, g.length, STEP):
            pts.append((idx, g.interpolate(d)))
    pts = gpd.GeoDataFrame({"reach": [p[0] for p in pts]}, geometry=[p[1] for p in pts], crs=open_.crs)
    pts_lu = pts.to_crs(lcrs)
    print(f"{len(open_)} open reaches, {len(pts)} sample points")

    rows = []
    with rasterio.open(LULC) as lu:
        for i, (p_utm, p_lu) in enumerate(zip(pts.geometry, pts_lu.geometry)):
            b = (p_lu.x - RADIUS - 600, p_lu.y - RADIUS - 600, p_lu.x + RADIUS + 600, p_lu.y + RADIUS + 600)
            win = from_bounds(*b, transform=lu.transform).round_offsets().round_lengths()
            codes = lu.read(1, window=win, boundless=True, fill_value=0)
            wtr = lu.window_transform(win)
            ny, nx = codes.shape
            if (codes == 0).mean() > 0.10:
                continue
            near = open_lu.geometry.iloc[open_lu.sindex.query(p_lu.buffer(RADIUS + 600), predicate="intersects")]
            chan = rasterize([(g, 1) for g in near], out_shape=codes.shape, transform=wtr, fill=0, dtype="uint8")
            dist = distance_transform_edt(chan == 0)  # metres (1 m pixels)
            yy, xx = np.mgrid[0:ny, 0:nx]
            cx, cy = wtr.c + (xx + 0.5) * wtr.a, wtr.f + (yy + 0.5) * wtr.e
            r = np.hypot(cx - p_lu.x, cy - p_lu.y)
            local = r <= RADIUS
            land = ~np.isin(codes, WATER) & (codes > 0)
            can = np.isin(codes, CANOPY)
            rec = {"reach": pts.reach.iloc[i], "x": p_utm.x, "y": p_utm.y}
            width = 0
            ok = True
            for lo, hi in zip(BANDS[:-1], BANDS[1:]):
                m = local & land & (dist >= lo) & (dist < hi)
                frac = can[m].mean() if m.sum() > 50 else np.nan
                rec[f"can_{lo}_{hi}"] = frac
                if ok and np.isfinite(frac) and frac >= 0.5:
                    width = hi
                else:
                    ok = False
            rec["buffer_width_m"] = width
            ring = land & (r > 300) & (r <= 600) & (codes > 0)
            rec["imperv_300_600"] = 100 * np.isin(codes, IMPERV)[ring].mean() if ring.sum() > 1000 else np.nan
            rec["canopy_300_600"] = 100 * can[ring].mean() if ring.sum() > 1000 else np.nan
            rows.append(rec)
    d = pd.DataFrame(rows)

    # LST from 30 m pixels near each point, by distance to the channel (UTM)
    lines = shapely.union_all(open_.geometry.values)
    r0, c0 = np.mgrid[0:H, 0:W]
    px, py = ltr.c + (c0 + 0.5) * ltr.a, ltr.f + (r0 + 0.5) * ltr.e
    corridor, spill = [], []
    for x, y in zip(d.x, d.y):
        c_, r_ = int((x - ltr.c) / ltr.a), int((y - ltr.f) / ltr.e)
        w = 8
        sl = (slice(max(r_ - w, 0), min(r_ + w + 1, H)), slice(max(c_ - w, 0), min(c_ + w + 1, W)))
        gx, gy, gv = px[sl].ravel(), py[sl].ravel(), lst[sl].ravel()
        along = np.hypot(gx - x, gy - y) <= ALONG + 100
        dch = shapely.distance(shapely.points(gx, gy), lines)
        corridor.append(np.nanmean(gv[along & (dch <= 45)]) if (along & (dch <= 45)).any() else np.nan)
        m2 = along & (dch > 100) & (dch <= 200)
        spill.append(np.nanmean(gv[m2]) if m2.sum() >= 3 else np.nan)
    d["lst_corridor"], d["lst_spillover"] = corridor, spill
    d["width_cls"] = pd.cut(d.buffer_width_m, WIDTH_BINS, labels=WIDTH_LABELS).astype(str)
    d["tile"] = (d.x // 1000).astype(int) * 1000 + (d.y // 1000).astype(int)
    d.to_csv(OUT / "buffer_width_points.csv", index=False, float_format="%.3f")
    print(d.width_cls.value_counts().reindex(WIDTH_LABELS).to_string())

    res = []
    for y in ("lst_corridor", "lst_spillover"):
        for ctl in ("", " + imperv_300_600"):
            dd = d.dropna(subset=[y, "imperv_300_600"])
            m = smf.ols(f"{y} ~ C(width_cls, Treatment('<10')){ctl}", data=dd).fit(
                cov_type="cluster", cov_kwds={"groups": dd.tile})
            for lab in WIDTH_LABELS[1:]:
                t = f"C(width_cls, Treatment('<10'))[T.{lab}]"
                ci = m.conf_int().loc[t]
                res.append({"outcome": y, "control": "context impervious" if ctl else "none", "width": lab,
                            "n": int((dd.width_cls == lab).sum()), "coef_C": m.params[t], "ci_lo": ci[0],
                            "ci_hi": ci[1], "p": m.pvalues[t]})
    res = pd.DataFrame(res)
    res.to_csv(OUT / "buffer_width_model.csv", index=False, float_format="%.4f")
    med = d.groupby("width_cls")[["lst_corridor", "lst_spillover", "imperv_300_600", "canopy_300_600"]].median().reindex(WIDTH_LABELS)
    pd.set_option("display.width", 200)
    print("\nmedians by buffer width:\n", med.round(2).to_string())
    print("\nmodel (vs < 10 m buffer):\n", res.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # continuous: piecewise-linear hinge on width (0-300 m), corridor LST, controlling context
    dd = d.dropna(subset=["lst_corridor", "imperv_300_600"]).copy()
    best = None
    for h in range(10, 210, 10):
        dd["w1"] = dd.buffer_width_m.clip(upper=h)
        dd["w2"] = (dd.buffer_width_m - h).clip(lower=0)
        m = smf.ols("lst_corridor ~ w1 + w2 + imperv_300_600", data=dd).fit()
        if best is None or m.ssr < best[1]:
            best = (h, m.ssr, m.params.w1 * 10, m.params.w2 * 10)
    print(f"\nhinge: cooling slope {best[2]:+.3f} C per 10 m up to {best[0]} m, then {best[3]:+.3f} C per 10 m")
    pd.Series({"hinge_m": best[0], "slope_below_per10m": best[2], "slope_above_per10m": best[3]}).to_csv(OUT / "buffer_width_hinge.csv")
    plot(d, res)


def plot(d, res):
    fig, ax = plt.subplots(figsize=(11, 7.5))
    x = np.arange(len(WIDTH_LABELS))
    for k, (y, colr, mk, lab) in enumerate([("lst_corridor", "#1d3f6e", "o", "In the corridor (≤ 45 m from channel)"),
                                            ("lst_spillover", "#b2182b", "s", "Neighbourhood 100–200 m from channel")]):
        t = res[(res.outcome == y) & (res.control == "context impervious")].set_index("width").reindex(WIDTH_LABELS[1:])
        vals = np.r_[0, t.coef_C.values]
        lo = np.r_[0, t.ci_lo.values]
        hi = np.r_[0, t.ci_hi.values]
        ax.errorbar(x + (k - 0.5) * 0.18, vals, yerr=[vals - lo, hi - vals], fmt=mk, ms=9, color=colr, capsize=4, lw=1.6, label=lab)
    ax.axhline(0, color="0.45", lw=1.2, ls="--")
    ax.set_xticks(x, [f"{l} m\n(n={int((d.width_cls == l).sum())})" for l in WIDTH_LABELS], fontsize=15)
    ax.set(xlabel="Forested buffer width: distance from channel, per side (banks pooled, ≥ 50% canopy)",
           ylabel="Summer LST vs < 10 m buffer (°C)", title="Riparian forest buffer width and summer LST")
    ax.grid(axis="y", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(fontsize=14, frameon=False, loc="lower left")
    fig.text(0.99, 0.01, f"{len(d):,} points every 150 m on open channels; controls for impervious cover 300–600 m away; 95% CI clustered by 1 km tile.\n"
             f"Landsat 8 Jul–Aug mean relative LST, 2013–2025; thermal data acquired at ~100 m.\n{CREDIT}",
             ha="right", va="bottom", fontsize=10, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(FIG / "buffer_width.png", dpi=150)


if __name__ == "__main__":
    if "--plot-only" in sys.argv:  # redraw the figure from the saved tables
        pts = pd.read_csv(OUT / "buffer_width_points.csv")
        plot(pts, pd.read_csv(OUT / "buffer_width_model.csv"))
    else:
        main()
