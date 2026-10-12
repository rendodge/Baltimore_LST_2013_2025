"""Scatter plots: % impervious surface (Annual NLCD) vs summer LST and vs LST trend layers.

For each NLCD year (2013, 2025):
  - impervious % vs that year's observed mean July-August LST (variant-B scenes, absolute)
  - impervious % vs each per-pixel trend layer (OLS: A, B relative, B absolute, C1, C2;
    Theil-Sen: B relative, C1, C2)
and change in impervious 2013-2025 (pp) vs the B relative and C2 trends (all changed blocks
plus a random sample of stable ones).
Pixels are averaged to 90 m blocks (3x3, >= 7 valid; closer to the 100 m thermal resolution),
and the same random sample of blocks is plotted in every figure. Each layer uses the same
y-range in both years.

Outputs: figures/scatter_impervious/*.png. Run after 02, 04 and 06:
  conda run -p .\\env python scripts\\07_scatter_impervious.py
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.ticker import MultipleLocator
from rasterio.features import geometry_mask

ROOT = Path(__file__).resolve().parents[1]
LST = ROOT / "data/processed/lst_trend"
LC = ROOT / "data/processed/landcover"
OUT = ROOT / "figures/scatter_impervious"
YEARS = (2013, 2025)
N_SAMPLE = 400
SEED = 42
DIMP_MIN = 5                                        # pp; "changed" blocks for the Δ-impervious plots
DIMP_TRENDS = ("B_rel_slope_ols", "C2_slope_ols")  # primary (relative) and surface-only trends
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; USGS Annual NLCD"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)

# Style: matplotlib default sizes x2; Helvetica, falling back to Arial where not installed.
plt.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20,
    "xtick.labelsize": 20, "ytick.labelsize": 20,
})

TRENDS = [  # (file, short name, axis label)
    ("A_slope_C_per_yr.tif", "A_slope_ols", "LST trend, A: all clear pixels (°C/yr)"),
    ("B_rel_slope_ols.tif", "B_rel_slope_ols", "Relative LST trend, B (°C/yr)"),
    ("B_abs_slope_ols.tif", "B_abs_slope_ols", "LST trend, B: filtered scenes (°C/yr)"),
    ("C1_slope_ols.tif", "C1_slope_ols", "LST trend, C1: sampling removed (°C/yr)"),
    ("C2_slope_ols.tif", "C2_slope_ols", "LST trend, C2: surface only (°C/yr)"),
    ("B_rel_slope_sen.tif", "B_rel_slope_sen", "Relative LST trend, B, Theil–Sen (°C/yr)"),
    ("C1_slope_sen.tif", "C1_slope_sen", "LST trend, C1, Theil–Sen (°C/yr)"),
    ("C2_slope_sen.tif", "C2_slope_sen", "LST trend, C2, Theil–Sen (°C/yr)"),
]


def read(path):
    with rasterio.open(path) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan).ravel()


def annual_b_abs_lst(year):
    """Observed (absolute) mean Jul-Aug LST for one year from variant-B scenes."""
    spec = importlib.util.spec_from_file_location("lst", ROOT / "scripts/02_lst_trend.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    with rasterio.open(LST / "B_mean_lst_C.tif") as s:
        tr, shape = s.transform, s.shape
    city = geometry_mask(gpd.read_file(m.NSA).to_crs(32618).geometry, out_shape=shape, transform=tr, invert=True)
    scenes, stack, _ = m.load_scenes(city)
    sel = ((scenes.clear_frac_city >= m.MIN_CLEAR) & (scenes.year == year)).values
    return np.where(city, np.nanmean(stack[sel], 0), np.nan), int(sel.sum())


def scatter(x, y, ylabel, title, path, ylim, zero_line=False, note="",
            xlabel="Impervious surface (%)", xlim=(-2, 102), zero_vline=False):
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.scatter(x, y, s=44, color="#3a6ea5", edgecolor="white", linewidth=0.8, alpha=0.85, zorder=3)
    if zero_line:
        ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=2)
    if zero_vline:
        ax.axvline(0, color="0.45", lw=1.2, ls="--", zorder=2)
    ax.set(xlim=xlim, ylim=ylim, xlabel=xlabel, ylabel=ylabel, title=title)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.xaxis.set_minor_locator(MultipleLocator(10))
    ax.grid(which="both", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(which="both", colors="0.35")
    fig.text(0.99, 0.01, f"{note}\n{CREDIT}", ha="right", va="bottom", fontsize=13, color="0.45",
             linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def sym_lim(*arrays):
    """Symmetric about zero, covering every plotted point, rounded up to 0.1 with headroom."""
    v = np.nanmax(np.abs(np.concatenate([a[np.isfinite(a)] for a in arrays])))
    v = np.ceil(v * 1.05 * 10) / 10
    return (-v, v)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    imp = {y: block(read(LC / f"nlcd_fctimp_{y}_utm.tif")) for y in YEARS}
    lst, nsc = {}, {}
    for y in YEARS:
        a, nsc[y] = annual_b_abs_lst(y)
        lst[y] = block(a)
    trends = {name: (block(read(LST / f)), lab) for f, name, lab in TRENDS}

    valid = np.logical_and.reduce([np.isfinite(imp[y]) for y in YEARS] + [np.isfinite(lst[y]) for y in YEARS]
                                  + [np.isfinite(t) for t, _ in trends.values()])
    idx = np.random.default_rng(SEED).choice(np.flatnonzero(valid), N_SAMPLE, replace=False)
    note = f"Random sample of {N_SAMPLE} 90 m blocks."

    lo = np.floor(min(np.nanmin(lst[y][idx]) for y in YEARS) / 5) * 5
    hi = np.ceil(max(np.nanmax(lst[y][idx]) for y in YEARS) / 5) * 5
    for y in YEARS:
        scatter(imp[y][idx], lst[y][idx], "July–August LST (°C)",
                f"Summer LST vs impervious surface, {y}", OUT / f"imp{y}_vs_lst{y}.png", (lo, hi),
                note=f"{note} LST: {nsc[y]} scene{'s' if nsc[y] != 1 else ''} ≥ 50% clear.")
        for name, (t, lab) in trends.items():
            scatter(imp[y][idx], t[idx], lab, f"LST trend 2013–2025 vs impervious surface, {y}",
                    OUT / f"imp{y}_vs_{name}.png", sym_lim(t[idx]), zero_line=True, note=note)

    # Change in impervious vs the relevant trend layers. Most blocks did not change, so plot
    # every block that changed by >= DIMP_MIN pp plus a random sample of stable blocks.
    dimp = block(read(LC / f"nlcd_dimp_{YEARS[0]}_{YEARS[1]}_pp.tif"))
    vd = np.logical_and.reduce([np.isfinite(dimp)] + [np.isfinite(trends[n][0]) for n in DIMP_TRENDS])
    changed = np.flatnonzero(vd & (np.abs(dimp) >= DIMP_MIN))
    stable = np.random.default_rng(SEED).choice(np.flatnonzero(vd & (np.abs(dimp) < DIMP_MIN)), N_SAMPLE, replace=False)
    jd = np.concatenate([changed, stable])
    xlim = (np.floor(dimp[jd].min() / 10) * 10, np.ceil(dimp[jd].max() / 10) * 10)
    note_d = (f"All {changed.size:,} 90 m blocks with |Δ impervious| ≥ {DIMP_MIN} pp, "
              f"plus a random {N_SAMPLE} of the {np.sum(vd & (np.abs(dimp) < DIMP_MIN)):,} stable blocks.")
    for name in DIMP_TRENDS:
        t, lab = trends[name]
        scatter(dimp[jd], t[jd], lab, f"LST trend vs impervious change, {YEARS[0]}–{YEARS[1]}",
                OUT / f"dimp_vs_{name}.png", sym_lim(t[jd]), zero_line=True, zero_vline=True, note=note_d,
                xlabel=f"Change in impervious surface, {YEARS[0]}–{YEARS[1]} (pp)", xlim=xlim)
    print(f"{len(list(OUT.glob('*.png')))} figures -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
