"""Separate stream cooling from valley topography, and test whether larger streams cool more.

Terrain (from 19_acquire_terrain.py), on a 10 m UTM grid aligned with the Landsat 30 m grid:
  - 3DEP 1/3 arc-second DEM, bilinear to 10 m: elevation; slope; topographic position index
    (TPI = elevation minus mean within ~300 m and ~1 km square windows); solar illumination at the
    mean overpass (cos of incidence angle; sun position for 31 July, 15:46 UTC, 39.3 N 76.6 W).
  - CC geomorphon 10 m (nearest): share of each 90 m block in valley-type forms (hollow,
    footslope, valley, pit) and in ridge-type forms (peak, ridge, shoulder, spur).
Aggregated to the 90 m blocks of 18_stream_distance_lst.py (mean relative summer LST, Landsat 8).

Models (OLS, SEs clustered by 1 km tile):
  M1 cover:            mean_rel ~ cover fractions + C(distance-to-open-channel bin)
  M2 cover + terrain:  M1 + elevation + slope + TPI300 + TPI1000 + illumination + valley + ridge shares
  M3 + surroundings:   M2 + canopy and impervious share of the surrounding 3x3 and 7x7 blocks
                       (park-scale cooling that extends beyond a block's own cover)
Distance-bin coefficients are relative to 450-1000 m. Stream size: for blocks <= 180 m from an
open channel, cover-adjusted and cover+terrain-adjusted LST by Strahler order and channel width
of the nearest open reach.

Outputs: data/processed/streams/terrain_*.csv; figures/stream_distance/{terrain_bins,stream_size}.png.
Run after 17, 18, 19: conda run -p .\\env python scripts\\20_stream_terrain_lst.py
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
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from scipy.ndimage import uniform_filter

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/terrain"
LST = ROOT / "data/processed/lst_trend"
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/stream_distance"
DEM = RAW / "3dep_n40w077-13_baltimore_subset.tif"
GEOM = RAW / "huc_02060003_geomorphon10m.tif"
PAD = 1530  # m, multiple of 90 so 10 m cells stay aligned with 90 m blocks
COVER = "canopy + structures + roads + other_imperv + bare + herb_shrub"
TERRAIN = "elev + slope + tpi300 + tpi1000 + illum + valley + ridge"
NEIGH = "canopy_n3 + canopy_n7 + imperv_n3 + imperv_n7"  # surrounding cover, 3x3 and 7x7 blocks (270 / 630 m)
BINS = [0, 90, 180, 270, 360, 450, 1000, np.inf]
LABELS = ["0-90", "90-180", "180-270", "270-360", "360-450", "450-1000", ">1000"]
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; USGS 3DEP; Chesapeake Hyper-Resolution Hydrography"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|invalid value", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def sun_position(doy=212, utc_h=15.77, lat=39.3, lon=-76.6):
    """Approximate solar elevation and azimuth (degrees; azimuth clockwise from north)."""
    g = 2 * np.pi / 365 * (doy - 1 + (utc_h - 12) / 24)
    decl = 0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    ha = np.radians((utc_h * 60 + eot + 4 * lon) / 4 - 180)
    phi = np.radians(lat)
    cz = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(ha)
    z = np.arccos(cz)
    az = np.degrees(np.arccos((np.sin(decl) - np.sin(phi) * cz) / (np.cos(phi) * np.sin(z))))
    return 90 - np.degrees(z), (360 - az) if ha > 0 else az


def nanmean_filter(a, size):
    ok = np.isfinite(a)
    num = uniform_filter(np.where(ok, a, 0.0), size, mode="constant")
    den = uniform_filter(ok.astype(float), size, mode="constant")
    return np.where(den > 0.5, num / np.maximum(den, 1e-9), np.nan)


def agg(a, k):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= 0.75 * k * k, np.nanmean(b, (1, 3)), np.nan)


def terrain_blocks():
    with rasterio.open(LST / "B_mean_rel_lst_C.tif") as s:
        t30, (H, W) = s.transform, s.shape
    x0, y0 = t30.c - PAD, t30.f + PAD
    w10, h10 = (W * 30 + 2 * PAD) // 10, (H * 30 + 2 * PAD) // 10
    t10 = from_origin(x0, y0, 10, 10)
    dem = np.full((h10, w10), np.nan, "float32")
    with rasterio.open(DEM) as src:
        reproject(rasterio.band(src, 1), dem, src_nodata=src.nodata, dst_transform=t10, dst_crs="EPSG:32618",
                  dst_nodata=np.nan, resampling=Resampling.bilinear)
    geo = np.zeros((h10, w10), "uint8")
    with rasterio.open(GEOM) as src:
        reproject(rasterio.band(src, 1), geo, src_nodata=src.nodata, dst_transform=t10, dst_crs="EPSG:32618",
                  dst_nodata=0, resampling=Resampling.nearest)
    gy, gx = np.gradient(dem, 10)  # rows run north -> south
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)  # downslope direction, clockwise from north
    elev_sun, az_sun = sun_position()
    zs, azs = np.radians(90 - elev_sun), np.radians(az_sun)
    illum = np.cos(zs) * np.cos(slope) + np.sin(zs) * np.sin(slope) * np.cos(azs - aspect)
    layers = {"elev": dem, "slope": np.degrees(slope), "illum": illum,
              "tpi300": dem - nanmean_filter(dem, 61), "tpi1000": dem - nanmean_filter(dem, 201),
              "valley": np.where(geo > 0, np.isin(geo, [7, 8, 9, 10]), np.nan).astype("float32"),
              "ridge": np.where(geo > 0, np.isin(geo, [2, 3, 4, 5]), np.nan).astype("float32")}
    p = PAD // 10
    out = {k: agg(v[p:p + H * 3, p:p + W * 3], 9) for k, v in layers.items()}  # 10 m -> 90 m blocks
    out["valley"], out["ridge"] = out["valley"] * 100, out["ridge"] * 100
    print(f"sun at overpass: elevation {elev_sun:.1f} deg, azimuth {az_sun:.1f} deg")
    return out, t30


def binned_model(d, formula, label):
    f = smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.tile})
    rows = []
    for lab in LABELS:
        term = f"C(dist_bin, Treatment('450-1000'))[T.{lab}]"
        if term in f.params:
            ci = f.conf_int().loc[term]
            rows.append({"model": label, "bin": lab, "coef_C": f.params[term], "ci_lo": ci[0], "ci_hi": ci[1],
                         "p": f.pvalues[term]})
        elif lab == "450-1000":
            rows.append({"model": label, "bin": lab, "coef_C": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "p": np.nan})
    return pd.DataFrame(rows), f


def main():
    d = pd.read_csv(OUT / "stream_distance_blocks.csv")
    ter, t30 = terrain_blocks()
    r = np.round((t30.f - d.y) / 90 - 0.5).astype(int)
    c = np.round((d.x - t30.c) / 90 - 0.5).astype(int)
    for k, a in ter.items():
        d[k] = a[r, c]
    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    pts = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.x, d.y), crs=32618)
    near = gpd.sjoin_nearest(pts, cc[cc.cnctR < 0.5][["strOrder", "wdAvg", "geometry"]], how="left")
    near = near[~near.index.duplicated()]
    d["near_order"], d["near_width"] = near.strOrder.values, near.wdAvg.values
    # surrounding cover: block-grid means over 3x3 and 7x7 neighbourhoods (water blocks count as missing)
    shape = ter["elev"].shape
    for name, cols in (("canopy", ["canopy"]), ("imperv", ["structures", "roads", "other_imperv"])):
        grid = np.full(shape, np.nan)
        grid[r, c] = d[cols].sum(axis=1).values
        for k in (3, 7):
            d[f"{name}_n{k}"] = nanmean_filter(grid, k)[r, c]
    d["dist_bin"] = pd.cut(d.dist_open, BINS, labels=LABELS, right=False).astype(str)
    d = d.dropna(subset=["elev", "slope", "tpi300", "tpi1000", "illum", "valley", "ridge",
                         "canopy_n3", "canopy_n7", "imperv_n3", "imperv_n7"])
    print(f"blocks with terrain: {len(d)}")

    b1, f1 = binned_model(d, f"mean_rel ~ {COVER} + C(dist_bin, Treatment('450-1000'))", "cover")
    b2, f2 = binned_model(d, f"mean_rel ~ {COVER} + {TERRAIN} + C(dist_bin, Treatment('450-1000'))", "cover + terrain")
    b3, f3 = binned_model(d, f"mean_rel ~ {COVER} + {TERRAIN} + {NEIGH} + C(dist_bin, Treatment('450-1000'))",
                          "cover + terrain + surroundings")
    bins = pd.concat([b1, b2, b3])
    bins.to_csv(OUT / "terrain_distance_bins.csv", index=False, float_format="%.4f")
    terr = pd.DataFrame({"coef": f2.params, "ci_lo": f2.conf_int()[0], "ci_hi": f2.conf_int()[1], "p": f2.pvalues})
    terr = terr.loc[[t.strip() for t in TERRAIN.split("+")]]
    terr.to_csv(OUT / "terrain_coefficients.csv", float_format="%.5g")

    # stream size: blocks within 180 m of an open channel; residuals from models without the distance term
    r1 = smf.ols(f"mean_rel ~ {COVER}", data=d).fit().resid
    r2 = smf.ols(f"mean_rel ~ {COVER} + {TERRAIN}", data=d).fit().resid
    r3 = smf.ols(f"mean_rel ~ {COVER} + {TERRAIN} + {NEIGH}", data=d).fit().resid
    d["resid_cover"], d["resid_terrain"], d["resid_surround"] = r1, r2, r3
    nr = d[d.dist_open < 180].copy()
    nr["order_cls"] = pd.cut(nr.near_order, [0, 1, 2, 3, 10], labels=["1", "2", "3", "4–6"]).astype(str)
    nr["width_cls"] = pd.qcut(nr.near_width, 4, labels=["Q1 narrowest", "Q2", "Q3", "Q4 widest"]).astype(str)
    size_rows = []
    for grp in ("order_cls", "width_cls"):
        for col in ("resid_cover", "resid_terrain", "resid_surround"):
            m = smf.ols(f"{col} ~ C({grp})", data=nr).fit(cov_type="cluster", cov_kwds={"groups": nr.tile})
            g = nr.groupby(grp)
            for lvl, s in g:
                size_rows.append({"grouping": grp, "class": lvl, "adjustment": col, "blocks": len(s),
                                  "median": s[col].median(), "mean": s[col].mean(),
                                  "mean_ci95": 1.96 * m.bse.iloc[0] if lvl == sorted(g.groups)[0] else np.nan,
                                  "width_m_median": s.near_width.median(), "canopy_median": s.canopy.median()})
            size_rows.append({"grouping": grp, "class": "joint test p", "adjustment": col,
                              "median": m.f_pvalue})
    size = pd.DataFrame(size_rows)
    size.to_csv(OUT / "terrain_stream_size.csv", index=False, float_format="%.4f")
    rho_w = nr[["near_width", "resid_cover", "resid_terrain"]].corr("spearman").iloc[0, 1:]

    pd.set_option("display.width", 220)
    fmt = lambda v: f"{v:.3f}"
    print(f"\nR2: cover {f1.rsquared:.3f}; cover + terrain {f2.rsquared:.3f}; + surroundings {f3.rsquared:.3f}")
    print(bins.to_string(index=False, float_format=fmt))
    print("\nterrain coefficients (per unit):\n", terr.to_string(float_format=lambda v: f"{v:.4g}"))
    print("\nstream size (blocks < 180 m from open channel):\n", size.to_string(index=False, float_format=fmt))
    print("Spearman width vs resid_cover %.3f, vs resid_terrain %.3f" % tuple(rho_w))

    # --- figures
    fig, ax = plt.subplots(figsize=(10, 7.5))
    x = np.arange(len(LABELS))
    for k, (lab, colr, off, mk) in enumerate([("cover", "#3a6ea5", -0.18, "o"), ("cover + terrain", "#b2182b", 0.0, "s"),
                                              ("cover + terrain + surroundings", "#4d4d4d", 0.18, "D")]):
        t = bins[bins.model == lab].set_index("bin").reindex(LABELS)
        ax.errorbar(x + off, t.coef_C, yerr=[t.coef_C - t.ci_lo, t.ci_hi - t.coef_C], fmt=mk, ms=9, color=colr,
                    capsize=4, lw=1.6, label=f"Adjusted for {lab}")
    ax.axhline(0, color="0.45", lw=1.2, ls="--")
    ax.set_xticks(x, LABELS, rotation=30, ha="right")
    ax.set(xlabel="Distance to nearest open stream channel (m)", ylabel="LST vs 450–1000 m (°C)",
           title="Stream-distance effect under added controls")
    ax.grid(axis="y", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(fontsize=15, frameon=False, loc="lower right")
    fig.text(0.99, 0.01, f"OLS on {len(d):,} 90 m blocks; 95% CI clustered by 1 km tile. Mean relative summer LST, Landsat 8.\n{CREDIT}",
             ha="right", va="bottom", fontsize=12, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG / "terrain_bins.png", dpi=150)
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(16, 7), sharey=True)
    for a, grp, xl in [(axs[0], "order_cls", "Strahler order of nearest open reach"),
                       (axs[1], "width_cls", "Channel width of nearest open reach (quartile)")]:
        lv = sorted(nr[grp].unique())
        for col, colr, off, mk, lab in [("resid_cover", "#3a6ea5", -0.18, "o", "Adjusted for cover"),
                                        ("resid_terrain", "#b2182b", 0.0, "s", "Adjusted for cover + terrain"),
                                        ("resid_surround", "#4d4d4d", 0.18, "D", "+ surrounding cover")]:
            means = [nr.loc[nr[grp] == l, col].mean() for l in lv]
            ses = [nr.loc[nr[grp] == l, col].std() / np.sqrt(nr.loc[nr[grp] == l].tile.nunique()) for l in lv]
            a.errorbar(np.arange(len(lv)) + off, means, yerr=1.96 * np.array(ses), fmt=mk, ms=9, color=colr,
                       capsize=4, lw=1.6, label=lab)
        a.axhline(0, color="0.45", lw=1.2, ls="--")
        a.set_xticks(range(len(lv)), [f"{l}\n(n={int((nr[grp] == l).sum())})" for l in lv], fontsize=15)
        a.set(xlabel=xl)
        a.grid(axis="y", color="0.9", lw=0.8)
        a.set_axisbelow(True)
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
    axs[0].set_ylabel("Adjusted LST, blocks < 180 m (°C)")
    axs[1].legend(fontsize=14, frameon=False, loc="lower left")
    fig.suptitle("Do larger streams cool more?", fontsize=24)
    fig.text(0.99, 0.01, f"Mean ± 95% CI (SE from number of 1 km tiles). {len(nr):,} blocks within 180 m of an open channel.\n{CREDIT}",
             ha="right", va="bottom", fontsize=12, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(FIG / "stream_size.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
