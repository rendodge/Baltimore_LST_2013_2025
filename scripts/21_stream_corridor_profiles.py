"""Along-stream profiles of summer LST and surface cover for named Baltimore streams.

Streams (NHD HR flowlines in the city, by GNIS name) are merged into one line each and sampled
every 90 m. At each sample point, a 135 m-radius corridor (~270 m wide) is summarized from the
30 m rasters: mean relative summer LST (Landsat 8, variant B), CC 2021/22 canopy, impervious
(structures + roads + other) and structures %, and the share of nearby CC reaches with no
visible channel (cnctR >= 0.5). Distance is measured upstream from the downstream end (the end
nearer the harbour shoreline).

Outputs: data/processed/streams/corridor_profiles.csv, corridor_summary.csv,
figures/stream_distance/corridor_profiles.png.
Run: conda run -p .\\env python scripts\\21_stream_corridor_profiles.py
"""
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from shapely.ops import linemerge, unary_union

ROOT = Path(__file__).resolve().parents[1]
LST = ROOT / "data/processed/lst_trend"
CC = ROOT / "data/processed/cc_lulc"
VEC = ROOT / "data/vector"
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/stream_distance"
STREAMS = {"Gwynns Falls": "#b2182b", "Jones Falls": "#2166ac", "Herring Run": "#1b7837", "Stony Run": "#762a83"}
STEP, RADIUS = 90, 135
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; land cover: Chesapeake Conservancy; streams: USGS NHD"
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a), s.transform


def main():
    rel, tr = read(LST / "B_mean_rel_lst_C.tif")
    cov = {g: read(CC / f"cc_frac_{g}_2021_utm.tif")[0] for g in ("canopy", "structures", "roads", "other_imperv", "water")}
    cov["imperv"] = cov["structures"] + cov["roads"] + cov["other_imperv"]
    H, W = rel.shape
    yy, xx = np.mgrid[0:H, 0:W]
    px, py = tr.c + (xx + 0.5) * tr.a, tr.f + (yy + 0.5) * tr.e
    nhd = gpd.read_file(VEC / "streams_nhd_city.gpkg")
    shore = unary_union(nhd[nhd.ftype.astype(int) == 566].geometry)
    cc = gpd.read_file(VEC / "streams_cc_city.gpkg")
    sidx = cc.sindex

    rows = []
    for name in STREAMS:
        geom = linemerge(unary_union(nhd[nhd.gnis_name == name].geometry))
        line = max(getattr(geom, "geoms", [geom]), key=lambda g: g.length)
        a, b = line.interpolate(0), line.interpolate(line.length)
        flip = a.distance(shore) > b.distance(shore)  # measure from the end nearer the harbour
        for s in np.arange(0, line.length, STEP):
            p = line.interpolate(line.length - s if flip else s)
            c0, r0 = int((p.x - tr.c) / tr.a), int((p.y - tr.f) / tr.e)
            k = RADIUS // 30 + 1
            win = (slice(max(r0 - k, 0), min(r0 + k + 1, H)), slice(max(c0 - k, 0), min(c0 + k + 1, W)))
            m = np.hypot(px[win] - p.x, py[win] - p.y) <= RADIUS
            row = {"stream": name, "dist_km": s / 1000, "x": p.x, "y": p.y,
                   "mean_rel": np.nanmean(rel[win][m])}
            for g, arr in cov.items():
                row[g] = np.nanmean(arr[win][m])
            near = cc.iloc[sidx.query(p.buffer(RADIUS), predicate="intersects")]
            row["no_visible_channel_pct"] = 100 * (near.length_m * (near.cnctR >= 0.5)).sum() / near.length_m.sum() if len(near) else np.nan
            rows.append(row)
    prof = pd.DataFrame(rows)
    prof.to_csv(OUT / "corridor_profiles.csv", index=False, float_format="%.3f")

    # thirds of each stream's city length (downstream -> upstream)
    prof["section"] = prof.groupby("stream").dist_km.transform(
        lambda d: pd.cut(d, 3, labels=["lower third", "middle third", "upper third"]).astype(str))
    cols = ["mean_rel", "canopy", "imperv", "structures", "water", "no_visible_channel_pct"]
    summ = pd.concat([prof.groupby("stream")[cols].mean().assign(section="whole"),
                      prof.groupby(["stream", "section"])[cols].mean().reset_index("section")])
    summ["length_km"] = prof.groupby("stream").dist_km.max().reindex(summ.index).values
    summ = summ.reset_index().sort_values(["stream", "section"])
    summ.to_csv(OUT / "corridor_summary.csv", index=False, float_format="%.2f")
    pd.set_option("display.width", 200)
    print(summ.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
    print("\ncorr across all sample points: LST~canopy %.2f, LST~imperv %.2f"
          % (prof.mean_rel.corr(prof.canopy), prof.mean_rel.corr(prof.imperv)))

    fig, ax = plt.subplots(2, 1, figsize=(12, 11), sharex=True)
    for name, colr in STREAMS.items():
        s = prof[prof.stream == name].sort_values("dist_km")
        sm = lambda v: v.rolling(5, center=True, min_periods=2).mean()  # ~450 m smoothing
        ax[0].plot(s.dist_km, sm(s.mean_rel), color=colr, lw=2.2, label=name)
        ax[1].plot(s.dist_km, sm(s.canopy), color=colr, lw=2.2, label=name)
    ax[0].axhline(0, color="0.45", lw=1.2, ls="--")
    ax[0].set(ylabel="Relative summer LST (°C)", title="Stream corridors: LST and canopy along each stream")
    ax[1].set(ylabel="Tree canopy (%)", xlabel="Distance upstream from downstream city end (km)", ylim=(0, 100))
    for a in ax:
        a.grid(color="0.9", lw=0.8)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.xaxis.set_major_locator(plt.MultipleLocator(2))
        a.xaxis.set_minor_locator(plt.MultipleLocator(1))
    ax[0].legend(fontsize=15, frameon=False, ncol=2, loc="upper right")
    fig.text(0.99, 0.01, f"Corridor = 135 m radius around points every 90 m on NHD flowlines; 450 m running mean. Landsat 8, 2013–2025.\n{CREDIT}",
             ha="right", va="bottom", fontsize=12, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(FIG / "corridor_profiles.png", dpi=150)


if __name__ == "__main__":
    main()
