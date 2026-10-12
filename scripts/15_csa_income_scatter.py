"""Median household income vs summer LST metrics by Community Statistical Area (CSA).

Income: BNIA Vital Signs median household income by CSA (ACS 5-year; field mhhi23 = 2019-2023,
nominal dollars; 55 CSAs). Income is only available for CSAs, so the LST metrics are recomputed
for each CSA from the pixels (same method as 13_nsa_summary.py: NSA-style mean annual series ->
OLS trend), rather than assigning CSA income to NSAs (which would repeat 55 values 279 times).

Metrics (active sensor set, default Landsat 8): relative LST trend (B), weather-normalized
trend with climate kept (C1), mean relative summer LST (B). One scatter plot per metric, with
Spearman and Pearson correlations (n = 55; neighbouring CSAs are not independent).

Outputs: data/processed/csa/csa_lst_income_<sensors>.csv, figures/scatter_income/*.png.
Run: conda run -p .\\env python scripts\\15_csa_income_scatter.py
"""
import importlib.util
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.ticker import FuncFormatter, MultipleLocator
from rasterio.features import rasterize
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nsa", ROOT / "scripts/13_nsa_summary.py")
N = importlib.util.module_from_spec(spec)
spec.loader.exec_module(N)
CSA = ROOT / "data/Median_Household_Income_-_Community_Statistical_Area/Median_Household_Income_-_Community_Statistical_Area.shp"
INCOME, INCOME_LABEL = "mhhi23", "Median household income, 2019–2023 ACS ($)"
OUT = ROOT / "data/processed/csa"
FIG = ROOT / "figures/scatter_income"
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; income: BNIA Vital Signs (ACS 2019–2023)"

plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def scatter(x, y, ylabel, title, path, ylim, zero_line, note):
    fig, ax = plt.subplots(figsize=(10, 7.5))
    ax.scatter(x / 1000, y, s=70, color="#3a6ea5", edgecolor="white", linewidth=0.8, alpha=0.9, zorder=3)
    if zero_line:
        ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=2)
    ok = np.isfinite(x) & np.isfinite(y)
    rho, p_rho = stats.spearmanr(x[ok], y[ok])
    r, p_r = stats.pearsonr(x[ok], y[ok])
    note = f"Spearman ρ = {rho:+.2f} (p = {p_rho:.2f}); Pearson r = {r:+.2f} (p = {p_r:.2f}); n = {ok.sum()} CSAs.\n{note}"
    ax.set(xlim=(0, 180), ylim=ylim, xlabel=INCOME_LABEL.replace("($)", "($1,000s)"), ylabel=ylabel, title=title)
    ax.xaxis.set_major_locator(MultipleLocator(20))
    ax.xaxis.set_minor_locator(MultipleLocator(10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    ax.grid(which="both", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(which="both", colors="0.35")
    fig.text(0.99, 0.01, f"{note}\n{CREDIT}", ha="right", va="bottom", fontsize=13, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return rho, p_rho, r, p_r


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    tag = "_".join(N.L.SENSORS).lower()
    with rasterio.open(N.LST / "B_rel_slope_ols.tif") as s:
        tr, shape = s.transform, s.shape
    csa = gpd.read_file(CSA).to_crs(32618)
    csa["zone"] = np.arange(1, len(csa) + 1)
    ids = rasterize(zip(csa.geometry, csa.zone), out_shape=shape, transform=tr, fill=0, dtype="int32")
    water = N.read(N.CC / "cc_frac_water_2021_utm.tif", 1)
    ids = np.where(np.nan_to_num(water) >= 50, 0, ids)
    mean_rel = N.read(N.LST / "B_mean_rel_lst_C.tif", 1)
    ann_rel, ann_c1 = N.read(N.LST / "B_annual_rel_lst_C.tif"), N.read(N.LST / "C1_annual_lst_C.tif")

    rows = []
    for z in csa.zone:
        n_px = int((ids == z).sum())
        r = {"zone": z, "pixels": n_px, "mean_rel": np.nanmean(mean_rel[ids == z])}
        for name, ann in (("rel", ann_rel), ("c1", ann_c1)):
            t = N.series_trend(ann, ids, z, n_px)
            r.update({f"{name}_trend": t["slope"], f"{name}_ci95": t["ci95"], f"{name}_p": t["p"]})
        rows.append(r)
    df = csa[["zone", "CSA2020", "mhhi13", INCOME]].merge(pd.DataFrame(rows), on="zone")
    df.to_csv(OUT / f"csa_lst_income_{tag}.csv", index=False, float_format="%.4f")

    note = "One point per CSA; LST metrics recomputed per CSA."
    res = {}
    for col, ylabel, title, zero in [
            ("rel_trend", "Relative LST trend (°C/yr)", "Relative LST trend vs income", True),
            ("c1_trend", "LST trend, C1: climate kept (°C/yr)", "LST trend (climate kept) vs income", True),
            ("mean_rel", "Mean relative summer LST (°C)", "Mean summer LST vs income", True)]:
        y = df[col].values
        v = np.nanmax(np.abs(y)) * 1.1
        ylim = (-v, v) if col != "c1_trend" else (min(-0.1, np.nanmin(y) * 1.2), np.nanmax(y) * 1.15)
        res[col] = scatter(df[INCOME].values.astype(float), y, ylabel, title, FIG / f"income_vs_{col}.png", ylim, zero, note)
    for k, (rho, prho, r, pr) in res.items():
        print(f"{k:10s} Spearman {rho:+.2f} (p {prho:.3f})  Pearson {r:+.2f} (p {pr:.3f})")
    print(df[["CSA2020", INCOME, "mean_rel", "rel_trend", "rel_p", "c1_trend"]].sort_values(INCOME)
          .to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
