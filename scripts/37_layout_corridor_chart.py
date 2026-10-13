"""Inset chart for the stream-corridor layout: summer relative LST of corridor pixels by tree canopy.

Corridor = 30 m pixels within 60 m of an open CC channel (cnctR < 0.5), inside the city. Values: Jul-Aug mean
relative LST 2013-2025 (Landsat 8) and CC 2021/22 canopy fraction at 30 m. Also reports the corridor share of
the city's coolest fifth (used in the layout caption).

Output: figures/layouts/corridor_lst_by_canopy.png
Run: conda run -p .\\env python scripts\\37_layout_corridor_chart.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures/layouts/corridor_lst_by_canopy.png"
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"], "font.size": 9})


def main():
    with rasterio.open(ROOT / "data/processed/lst_trend/B_mean_rel_lst_C.tif") as s:
        a = s.read(1).astype(float)
        a[a == s.nodata] = np.nan
        shape, tr = a.shape, s.transform
    nsa = gpd.read_file(ROOT / "data/vector/nsa_boundaries_32618.gpkg")
    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    city = geometry_mask(nsa.geometry, shape, tr, invert=True) & np.isfinite(a)
    corr = geometry_mask(cc[cc.cnctR < 0.5].buffer(60).geometry, shape, tr, invert=True) & city
    with rasterio.open(ROOT / "data/processed/cc_lulc/cc_frac_canopy_2021_utm.tif") as s:
        can = s.read(1).astype(float)
    q20 = np.percentile(a[city], 20)
    print(f"corridor = {corr.sum() / city.sum():.1%} of city; {((a <= q20) & corr).sum() / ((a <= q20) & city).sum():.1%} "
          f"of coolest fifth; {(a[corr] <= q20).mean():.1%} of corridor pixels in coolest fifth (rest {(a[city & ~corr] <= q20).mean():.1%})")
    df = pd.DataFrame({"lst": a[corr], "can": can[corr]})
    labs = ["< 25%", "25–50%", "50–75%", "> 75%"]
    df["cls"] = pd.cut(df.can, [-1, 25, 50, 75, 101], labels=labs)
    g = df.groupby("cls", observed=True).lst
    med, q1, q3, n = g.median(), g.quantile(0.25), g.quantile(0.75), g.size()
    rest = np.median(a[city & ~corr])

    # sized for a 106 x 83 mm slot in the layout; fonts at 2x the original layout spec
    fig, ax = plt.subplots(figsize=(4.19, 3.27), dpi=300)
    x = np.arange(len(labs))
    cols = ["#c7e9c0", "#74c476", "#31a354", "#006d2c"]
    ax.bar(x, med.values, color=cols, width=0.7, edgecolor="white", linewidth=0.8)
    for xi, m in zip(x, med.values):
        ax.text(xi, m + 0.25, f"{m:.1f}", ha="center", va="bottom", fontsize=13, color="white" if xi > 1 else "0.15",
                fontweight="bold")
    ax.axhline(0, color="0.3", lw=0.9)
    ax.axhline(rest, color="#b2182b", lw=1.4, ls="--")
    ax.text(3.45, rest + 0.2, "rest of city", ha="right", va="bottom", fontsize=12, color="#b2182b")
    ax.set_xticks(x, ["<25", "25–50", "50–75", ">75"], fontsize=14)
    ax.tick_params(axis="y", labelsize=14)
    ax.set_xlabel("Canopy in corridor (%)", fontsize=15)
    ax.set_ylabel("°C vs median", fontsize=15)
    ax.set_yticks([0, -2, -4, -6, -8])
    ax.set_ylim(min(med.values) - 0.6, 1.6)
    ax.grid(axis="y", color="0.9", lw=0.6)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300)
    print(pd.DataFrame({"median": med, "q1": q1, "q3": q3, "n": n}).round(2).to_string())


if __name__ == "__main__":
    main()
