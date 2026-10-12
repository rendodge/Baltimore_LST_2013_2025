"""Summer LST of 90 m blocks vs distance to the nearest stream (Landsat 8, 2013-2025).

Blocks: 3x3 means of the 30 m mean relative summer LST (variant B; deg C vs city median) and of
the Chesapeake Conservancy cover fractions (2021/22). Blocks with >= 10% water are excluded.
Distance from each block centre to the nearest stream line:
  - CC hyper-resolution reaches with an open channel (cnctR < 0.5);
  - CC reaches with mostly no visible channel (cnctR >= 0.5; likely piped/culverted/under road);
  - NHD coastline (harbour shoreline), used to separate harbour cooling.
LST is examined raw and after removing surface-cover effects (residual of
mean_rel ~ canopy + structures + roads + other impervious + bare + herbaceous, turf reference),
i.e. the stream effect beyond the vegetation/impervious mix of the block itself.
Near-vs-far difference (<= 90 m vs 450-1000 m) with a 95% CI from a spatial block bootstrap
(1 km tiles). Analyses repeated for blocks > 1 km from the harbour shoreline.

Outputs: data/processed/streams/stream_distance_blocks.csv, ..._bins.csv,
figures/stream_distance/*.png. Run: conda run -p .\\env python scripts\\18_stream_distance_lst.py
"""
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
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
LST = ROOT / "data/processed/lst_trend"
CC = ROOT / "data/processed/cc_lulc"
VEC = ROOT / "data/vector"
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/stream_distance"
GROUPS = ["canopy", "structures", "roads", "other_imperv", "turf", "bare", "herb_shrub", "water"]
BINS = [0, 90, 180, 270, 360, 450, 600, 800, 1000, 1500, np.inf]
NEAR, FAR = (0, 90), (450, 1000)
N_SAMPLE, SEED, TILE_M, N_BOOT = 400, 42, 1000, 1000
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; streams: Chesapeake Hyper-Resolution Hydrography"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a), s.transform


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan)


def nearest_dist(pts, lines):
    j = gpd.sjoin_nearest(pts, lines[["geometry"]], how="left", distance_col="d")
    return j.groupby(level=0).d.min().reindex(pts.index).values


def boot_diff(d, col, dist, rng):
    near = d[(d[dist] >= NEAR[0]) & (d[dist] <= NEAR[1])]
    far = d[(d[dist] >= FAR[0]) & (d[dist] <= FAR[1])]
    point = near[col].median() - far[col].median()
    tiles = d.tile.unique()
    reps = []
    for _ in range(N_BOOT):
        pick = pd.Series(rng.choice(tiles, len(tiles), replace=True)).value_counts()
        w_n = near.tile.map(pick).fillna(0).astype(int)
        w_f = far.tile.map(pick).fillna(0).astype(int)
        n_vals = np.repeat(near[col].values, w_n.values)
        f_vals = np.repeat(far[col].values, w_f.values)
        if n_vals.size and f_vals.size:
            reps.append(np.median(n_vals) - np.median(f_vals))
    lo, hi = np.percentile(reps, [2.5, 97.5])
    return point, lo, hi, len(near), len(far)


def style(ax, xlabel, ylabel, title):
    ax.set(xlim=(0, 1500), xlabel=xlabel, ylabel=ylabel, title=title)
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.xaxis.set_minor_locator(MultipleLocator(100))
    ax.grid(which="both", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(which="both", colors="0.35")
    ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=2)


def binned(d, dist, col):
    b = pd.cut(d[dist], BINS, right=False)
    g = d.groupby(b, observed=True)[col]
    mid = [(i.left + min(i.right, 1700)) / 2 for i in g.median().index]
    return np.array(mid), g.median().values, g.quantile(0.25).values, g.quantile(0.75).values, g.size().values


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    rel, tr = read(LST / "B_mean_rel_lst_C.tif")
    d = pd.DataFrame({"mean_rel": block(rel).ravel()})
    for g in GROUPS:
        d[g] = block(read(CC / f"cc_frac_{g}_2021_utm.tif")[0]).ravel()
    bh, bw = block(rel).shape
    r, c = np.divmod(np.arange(bh * bw), bw)
    d["x"] = tr.c + (c * 3 + 1.5) * tr.a
    d["y"] = tr.f + (r * 3 + 1.5) * tr.e
    d = d[d.mean_rel.notna() & d.canopy.notna() & (d.water < 10)].copy()
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.x, d.y), crs=32618)

    cc = gpd.read_file(VEC / "streams_cc_city.gpkg")
    nhd = gpd.read_file(VEC / "streams_nhd_city.gpkg")
    d["dist_open"] = nearest_dist(pts, cc[cc.cnctR < 0.5])
    d["dist_hidden"] = nearest_dist(pts, cc[cc.cnctR >= 0.5])
    d["dist_harbour"] = nearest_dist(pts, nhd[nhd.ftype.astype(int) == 566])
    d["tile"] = (d.x // TILE_M).astype(int) * 1000 + (d.y // TILE_M).astype(int)

    fit = smf.ols("mean_rel ~ canopy + structures + roads + other_imperv + bare + herb_shrub", data=d).fit()
    d["resid"] = fit.resid
    d.to_csv(OUT / "stream_distance_blocks.csv", index=False, float_format="%.3f")

    rng = np.random.default_rng(SEED)
    rows = []
    for subset, sel in [("all blocks", np.ones(len(d), bool)), ("> 1 km from harbour", (d.dist_harbour > 1000).values)]:
        s = d[sel]
        for dist in ("dist_open", "dist_hidden"):
            for col in ("mean_rel", "resid", "canopy"):
                pt, lo, hi, nn, nf = boot_diff(s, col, dist, rng)
                rho = stats.spearmanr(s[dist].clip(upper=1500), s[col]).statistic
                rows.append({"subset": subset, "distance_to": dist, "variable": col, "near_minus_far": pt,
                             "ci95_lo": lo, "ci95_hi": hi, "n_near": nn, "n_far": nf, "spearman_dist": rho})
    res = pd.DataFrame(rows)
    res.to_csv(OUT / "stream_distance_effects.csv", index=False, float_format="%.4f")
    bins = []
    for dist in ("dist_open", "dist_hidden"):
        for col in ("mean_rel", "resid", "canopy"):
            mid, med, q1, q3, n = binned(d, dist, col)
            bins.append(pd.DataFrame({"distance_to": dist, "variable": col, "bin_mid_m": mid, "median": med,
                                      "q25": q1, "q75": q3, "blocks": n}))
    pd.concat(bins).to_csv(OUT / "stream_distance_bins.csv", index=False, float_format="%.3f")

    # --- figures
    samp = d.sample(N_SAMPLE, random_state=SEED)
    note = f"{len(d):,} 90 m blocks (< 10% water); dots: random {N_SAMPLE}; line and band: median and IQR by distance."
    for col, ylabel, title, fname in [
            ("mean_rel", "Mean relative summer LST (°C)", "Summer LST vs distance to stream", "lst_vs_dist_open.png"),
            ("resid", "LST beyond surface cover (°C)", "Cover-adjusted LST vs distance to stream", "resid_vs_dist_open.png")]:
        fig, ax = plt.subplots(figsize=(10, 7.5))
        ax.scatter(samp.dist_open, samp[col], s=30, color="#3a6ea5", edgecolor="white", linewidth=0.6, alpha=0.45, zorder=3)
        mid, med, q1, q3, _ = binned(d, "dist_open", col)
        k = mid <= 1500
        ax.fill_between(mid[k], q1[k], q3[k], color="#3a6ea5", alpha=0.15, lw=0, zorder=2)
        ax.plot(mid[k], med[k], "o-", color="#1d3f6e", lw=2, ms=8, zorder=4)
        style(ax, "Distance to nearest open stream channel (m)", ylabel, title)
        v = np.nanpercentile(np.abs(samp[col]), 99) * 1.1
        ax.set_ylim(-v, v)
        e = res[(res.subset == "all blocks") & (res.distance_to == "dist_open") & (res.variable == col)].iloc[0]
        stat = f"Within 90 m minus 450–1000 m: {e.near_minus_far:+.2f} °C (95% CI {e.ci95_lo:+.2f} to {e.ci95_hi:+.2f}); Spearman ρ = {e.spearman_dist:+.2f}."
        fig.text(0.99, 0.01, f"{stat}\n{note}\n{CREDIT}", ha="right", va="bottom", fontsize=12, color="0.45", linespacing=1.3)
        fig.tight_layout(rect=(0, 0.10, 1, 1))
        fig.savefig(FIG / fname, dpi=150)
        plt.close(fig)
    # open channel vs no visible channel (binned medians of cover-adjusted LST)
    fig, ax = plt.subplots(figsize=(10, 7.5))
    for dist, lab, colr, ls in [("dist_open", "Open channel", "#1d3f6e", "-"),
                                ("dist_hidden", "No visible channel (piped/culverted)", "#8a6d3b", "--")]:
        mid, med, q1, q3, _ = binned(d, dist, "resid")
        k = mid <= 1500
        ax.plot(mid[k], med[k], marker="o", ls=ls, color=colr, lw=2, ms=8, label=lab, zorder=4)
    style(ax, "Distance to nearest stream reach (m)", "LST beyond surface cover (°C, median)",
          "Open vs buried streams: cover-adjusted LST")
    ax.legend(fontsize=14, frameon=False, loc="lower right")
    eo = res[(res.subset == "all blocks") & (res.distance_to == "dist_open") & (res.variable == "resid")].iloc[0]
    eh = res[(res.subset == "all blocks") & (res.distance_to == "dist_hidden") & (res.variable == "resid")].iloc[0]
    stat = (f"Within 90 m minus 450–1000 m: open {eo.near_minus_far:+.2f} °C ({eo.ci95_lo:+.2f} to {eo.ci95_hi:+.2f}); "
            f"no visible channel {eh.near_minus_far:+.2f} °C ({eh.ci95_lo:+.2f} to {eh.ci95_hi:+.2f}).")
    fig.text(0.99, 0.01, f"{stat}\n{len(d):,} 90 m blocks (< 10% water).\n{CREDIT}", ha="right", va="bottom",
             fontsize=12, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(FIG / "resid_open_vs_hidden.png", dpi=150)
    plt.close(fig)

    pd.set_option("display.width", 220)
    print(f"blocks {len(d)}; cover model r2 {fit.rsquared:.3f}")
    print(res.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(pd.concat(bins).query("distance_to == 'dist_open'").to_string(index=False, float_format=lambda v: f"{v:.2f}"))


if __name__ == "__main__":
    main()
