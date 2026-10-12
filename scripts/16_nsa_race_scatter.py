"""Share of Black residents (2020 Census) vs summer LST metrics by NSA, plus population-weighted
exposure.

Inputs: NSA summary from 13_nsa_summary.py for the active sensor set (default Landsat 8) and the
NSA 2020 Census counts. x = Blk_AfAm / Population (%), NSAs with < 100 residents excluded.
y = mean relative summer LST, relative LST trend (B), weather-normalized trend with climate kept
(C1). Spearman/Pearson correlations across NSAs (neighbouring NSAs are not independent; this is
an area-level, ecological comparison).
Exposure: population-weighted mean of each NSA metric for Black and for white residents
(sum(group_i * metric_i) / sum(group_i)), with a 95% CI from a spatial block bootstrap of NSAs
(resampling 2 km tiles of NSA centroids).

Outputs: data/processed/nsa/nsa_race_lst_<sensors>.csv, figures/scatter_race/*.png.
Run: conda run -p .\\env python scripts\\16_nsa_race_scatter.py
"""
import importlib.util
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import MultipleLocator
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lst", ROOT / "scripts/02_lst_trend.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
TAG = "_".join(L.SENSORS).lower()
NSA_LST = ROOT / f"data/processed/nsa/nsa_lst_{TAG}.gpkg"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
FIG = ROOT / "figures/scatter_race"
MIN_POP = 100
TILE_M, N_BOOT, SEED = 2000, 2000, 42
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; population: 2020 Census via Baltimore City NSA data"

plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})
METRICS = [("mean_rel", "Mean relative summer LST (°C)", "Mean summer LST vs Black residents"),
           ("rel_trend", "Relative LST trend (°C/yr)", "Relative LST trend vs Black residents"),
           ("c1_trend", "LST trend, C1: climate kept (°C/yr)", "LST trend (climate kept) vs Black residents")]


def scatter(x, y, ylabel, title, path, note):
    ok = np.isfinite(x) & np.isfinite(y)
    rho, p_rho = stats.spearmanr(x[ok], y[ok])
    r, p_r = stats.pearsonr(x[ok], y[ok])
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.scatter(x, y, s=44, color="#3a6ea5", edgecolor="white", linewidth=0.8, alpha=0.85, zorder=3)
    ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=2)
    v = np.nanmax(np.abs(y[ok])) * 1.08
    ax.set(xlim=(-2, 102), ylim=(-v, v), xlabel="Black or African American residents, 2020 (%)", ylabel=ylabel, title=title)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.xaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(which="both", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(which="both", colors="0.35")
    stat = f"Spearman ρ = {rho:+.2f} (p = {p_rho:.2g}); Pearson r = {r:+.2f} (p = {p_r:.2g}); n = {ok.sum()} NSAs."
    fig.text(0.99, 0.01, f"{stat}\n{note}\n{CREDIT}", ha="right", va="bottom", fontsize=13, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return rho, p_rho, r, p_r


def exposure(d, col, rng):
    w = lambda s: {g: np.nansum(s[g] * s[col]) / np.nansum(s[g]) for g in ("Blk_AfAm", "White")}
    point = w(d)
    tiles = d.tile.values
    uniq = np.unique(tiles)
    by = {t: np.flatnonzero(tiles == t) for t in uniq}
    reps = []
    for _ in range(N_BOOT):
        idx = np.concatenate([by[t] for t in rng.choice(uniq, len(uniq), replace=True)])
        e = w(d.iloc[idx])
        reps.append([e["Blk_AfAm"], e["White"], e["Blk_AfAm"] - e["White"]])
    reps = np.array(reps)
    lo, hi = np.percentile(reps, [2.5, 97.5], axis=0)
    return {"black": point["Blk_AfAm"], "white": point["White"], "diff": point["Blk_AfAm"] - point["White"],
            "diff_ci95": (lo[2], hi[2])}


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    lst = gpd.read_file(NSA_LST)
    census = gpd.read_file(NSA).drop(columns="geometry")[["Name", "Blk_AfAm", "White"]]
    d = lst.merge(census, on="Name", how="left")
    d = d[d.Population >= MIN_POP].copy()
    d["pct_black"] = 100 * d.Blk_AfAm / d.Population
    c = d.geometry.representative_point()
    d["tile"] = (c.x // TILE_M).astype(int) * 1000 + (c.y // TILE_M).astype(int)
    d.drop(columns="geometry").to_csv(ROOT / f"data/processed/nsa/nsa_race_lst_{TAG}.csv", index=False, float_format="%.4f")

    rng = np.random.default_rng(SEED)
    note = f"One point per NSA with ≥ {MIN_POP} residents; Landsat 8, 2013–2025."
    for col, ylabel, title in METRICS:
        rho, prho, r, pr = scatter(d.pct_black.values, d[col].values, ylabel, title, FIG / f"pct_black_vs_{col}.png", note)
        e = exposure(d, col, rng)
        print(f"{col:9s} Spearman {rho:+.2f} (p {prho:.2g})  Pearson {r:+.2f} (p {pr:.2g}) | pop-weighted: "
              f"Black {e['black']:+.3f}  white {e['white']:+.3f}  diff {e['diff']:+.3f} "
              f"[{e['diff_ci95'][0]:+.3f}, {e['diff_ci95'][1]:+.3f}]")
    q = pd.qcut(d.pct_black, 4, labels=["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"])
    print("\nby quartile of % Black:\n", d.groupby(q, observed=True)[["pct_black", "mean_rel", "rel_trend", "c1_trend", "canopy21", "imperv21"]]
          .median().round(3).to_string())
    print(f"\nNSAs used: {len(d)} (excluded < {MIN_POP} residents)")


if __name__ == "__main__":
    main()
