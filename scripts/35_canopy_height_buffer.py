"""Does riparian tree height add cooling beyond buffer width? (Meta 1 m canopy height x buffer deep dive)

Canopy height: Meta / WRI 1 m global canopy height v1 (34_acquire_canopy_height.py), a model estimate
from leaf-on imagery (mostly 2018-2020). The four tile subsets are mosaicked (EPSG:3857) and, around
each buffer point of 29_buffer_points.py, warped (bilinear) onto the Chesapeake Conservancy 1 m LULC
grid so heights align pixel-for-pixel with the 2021/22 canopy classes.

Per point (local frame: +-150 m along the reach, distance from the open channel, banks pooled):
  h_buf        mean height of CC canopy pixels inside the continuous forested buffer (distance < w_pool)
  h_can_a_b    mean height of CC canopy pixels in distance band a-b m (0-30, 30-100, 100-300)
  can_a_b      CC canopy share of land in the band; vol_a_b = mean height over all land (extent x height)
Agreement check: share of CC canopy pixels with height >= 3 m, and of other land with height >= 5 m.

Models (outcome: Jul-Aug corridor relative LST, Landsat 8; OLS, SEs clustered by 1 km tile; CTRL2 and
width classes from 30_buffer_analysis.py):
  H1  height at fixed width: points with w_pool >= 30 m, y ~ width class + h_buf + CTRL2 (+ tile FE);
      repeated for DJF/MAM/JJA/SON corridor LST (falsification: a leaf-driven effect should fade in winter)
  H2  extent vs height: y ~ can_0_100 | vol_0_100 | can_0_100 + h_can_0_100, each + CTRL2 (AIC, R2)
  H3  does height change the width effect: width class x tall (h_buf >= median), points with w_pool >= 10

Outputs: data/processed/canopy_height/{meta_chm_mosaic_3857.tif, chm_mean_30m.tif, buffer_height.csv,
height_models.csv}, figures/buffer_deepdive/canopy_height.png.
Run after 29, 30, 34: conda run -p .\\env python scripts\\35_canopy_height_buffer.py
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
import shapely
import statsmodels.formula.api as smf
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.merge import merge
from rasterio.vrt import WarpedVRT
from rasterio.warp import reproject
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/canopy_height"
OUT = ROOT / "data/processed/canopy_height"
FIG = ROOT / "figures/buffer_deepdive"
LULC = ROOT / "data/raw/cc_lulc/balt_24510_lulc_2021_2024-Edition.tif"
CANOPY = [23, 24, 25, 26, 40, 41, 53, 54, 55, 63, 64, 65, 73, 74, 75]
WATER = [10, 11, 12, 13, 14]
ALONG, ACROSS = 150, 300
BANDS = [(0, 30), (30, 100), (100, 300), (0, 100)]
CREDIT = ("Canopy height: Meta / WRI (Tolan et al. 2024, CC BY 4.0); Landsat imagery courtesy of the U.S. Geological Survey;"
          " land cover and streams: Chesapeake Conservancy / UMBC")
warnings.filterwarnings("ignore")
spec = importlib.util.spec_from_file_location("bd", ROOT / "scripts/30_buffer_analysis.py")
BD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BD)


def mosaic():
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "meta_chm_mosaic_3857.tif"
    if not dst.exists():
        srcs = [rasterio.open(p) for p in sorted(RAW.glob("meta_chm_*_subset.tif"))]
        arr, tr = merge(srcs)
        prof = srcs[0].profile.copy()
        prof.update(width=arr.shape[2], height=arr.shape[1], transform=tr, compress="deflate", predictor=2, tiled=True)
        with rasterio.open(dst, "w", **prof) as o:
            o.write(arr)
        for s in srcs:
            s.close()
    # 30 m mean height (all pixels, i.e. extent x height) on the Landsat grid, for mapping
    d30 = OUT / "chm_mean_30m.tif"
    if not d30.exists():
        with rasterio.open(ROOT / "data/processed/lst_trend/B_mean_rel_lst_C.tif") as ref, rasterio.open(dst) as src:
            out = np.full((ref.height, ref.width), np.nan, "float32")
            reproject(src.read(1).astype("float32"), out, src_transform=src.transform, src_crs=src.crs,
                      dst_transform=ref.transform, dst_crs=ref.crs, resampling=Resampling.average)
            p = ref.profile.copy()
            p.update(dtype="float32", nodata=-9999.0, compress="deflate", count=1)
            with rasterio.open(d30, "w", **p) as o:
                o.write(np.where(np.isfinite(out), out, -9999.0).astype("float32"), 1)
                o.set_band_description(1, "Mean canopy height over all pixels (m), Meta 1 m CHM aggregated to 30 m")
    return dst


def point_heights(chm_path, d):
    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    open_ = cc[cc.cnctR < 0.5]
    lu = rasterio.open(LULC)
    open_lu = open_.to_crs(lu.crs)
    chm = rasterio.open(chm_path)
    pts_lu = gpd.GeoSeries(gpd.points_from_xy(d.x, d.y), crs=32618).to_crs(lu.crs)
    agree = np.zeros(4)  # canopy px, canopy px >= 3 m, other land px, other land >= 5 m
    rows = []
    for k, (rid, x, y, p, w) in enumerate(zip(d.reach, d.x, d.y, pts_lu, d.w_pool)):
        g = open_.loc[rid].geometry
        s_ = g.project(shapely.Point(x, y))
        a, c_ = g.interpolate(max(s_ - 5, 0)), g.interpolate(min(s_ + 5, g.length))
        t = np.array([c_.x - a.x, c_.y - a.y])
        tx, ty = t / (np.linalg.norm(t) or 1)
        rad = ACROSS + 120
        b = (p.x - rad, p.y - rad, p.x + rad, p.y + rad)
        win = from_bounds(*b, transform=lu.transform).round_offsets().round_lengths()
        codes = lu.read(1, window=win, boundless=True, fill_value=0)
        wtr = lu.window_transform(win)
        ny, nx = codes.shape
        with WarpedVRT(chm, crs=lu.crs, transform=wtr, width=nx, height=ny, resampling=Resampling.bilinear,
                       nodata=255) as v:
            h = v.read(1).astype("float32")
        h[h == 255] = np.nan
        near = open_lu.geometry.iloc[open_lu.sindex.query(shapely.box(*b), predicate="intersects")]
        dist = distance_transform_edt(rasterize([(gg, 1) for gg in near], out_shape=(ny, nx), transform=wtr,
                                                fill=0, dtype="uint8") == 0)
        yy, xx = np.mgrid[0:ny, 0:nx]
        vx, vy = wtr.c + (xx + 0.5) * wtr.a - p.x, wtr.f + (yy + 0.5) * wtr.e - p.y
        frame = (np.abs(vx * tx + vy * ty) <= ALONG) & (dist <= ACROSS) & np.isfinite(h)
        land = (codes > 0) & ~np.isin(codes, WATER)
        can = np.isin(codes, CANOPY)
        m = frame & land
        agree += [(m & can).sum(), (m & can & (h >= 3)).sum(), (m & ~can).sum(), (m & ~can & (h >= 5)).sum()]
        rec = {"k": k}
        for lo, hi in BANDS:
            band = m & (dist >= lo) & (dist < hi)
            cb = band & can
            rec[f"can_{lo}_{hi}"] = cb.sum() / band.sum() if band.sum() > 30 else np.nan
            rec[f"vol_{lo}_{hi}"] = h[band].mean() if band.sum() > 30 else np.nan
            rec[f"h_can_{lo}_{hi}"] = h[cb].mean() if cb.sum() > 30 else np.nan
        cb = m & can & (dist < w)
        rec["h_buf"] = h[cb].mean() if (w >= 10 and cb.sum() > 30) else np.nan
        rec["h_buf_p90"] = np.percentile(h[cb], 90) if (w >= 10 and cb.sum() > 30) else np.nan
        rows.append(rec)
        if k % 100 == 0:
            print(k, flush=True)
    lu.close()
    chm.close()
    return pd.DataFrame(rows), agree


def coef(f, term, scale=1.0):
    ci = f.conf_int().loc[term] * scale
    return {"coef": f.params[term] * scale, "ci_lo": ci[0], "ci_hi": ci[1], "p": f.pvalues[term], "n": int(f.nobs)}


def ols(d, formula):
    return smf.ols(formula, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.tile})


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    chm_path = mosaic()
    d = BD.prep(pd.read_csv(ROOT / "data/processed/streams/buffer_points_v2.csv"))
    d["k"] = np.arange(len(d))
    cache = OUT / "buffer_height.csv"
    if cache.exists():
        hgt = pd.read_csv(cache)
    else:
        hgt, agree = point_heights(chm_path, d)
        hgt.to_csv(cache, index=False, float_format="%.4f")
        print(f"agreement: CC canopy px with height >= 3 m {agree[1] / agree[0]:.1%}; "
              f"other land px with height >= 5 m {agree[3] / agree[2]:.1%}")
    d = d.merge(hgt, on="k")
    y = "jja_julaug_corr"
    print("h_buf (m): " + d.h_buf.describe().round(1).to_string().replace("\n", "; "))
    print("by width class, median h_buf:", d.groupby("cls_pool").h_buf.median().reindex(BD.WLAB).round(1).to_dict())
    print(f"corr(w_pool, h_buf) = {d[['w_pool', 'h_buf']].corr().iloc[0, 1]:.2f} (w >= 10)")

    res = []
    cls = f"C(cls_pool, Treatment('{BD.REF}'))"
    # H1: height at fixed width, wide-enough buffers
    h1 = d[(d.w_pool >= 30)].dropna(subset=["h_buf", y]).copy()
    h1["h5"] = h1.h_buf / 5
    for lab, rhs in (("M2", BD.CTRL2), ("M3 tile FE", BD.CTRL2 + " + C(tile)")):
        f = ols(h1, f"{y} ~ {cls} + h5 + {rhs}")
        res.append({"test": "H1 height at fixed width", "model": lab, "outcome": y, "term": "per +5 m mean buffer height", **coef(f, "h5")})
    for s in ("JJA", "MAM", "SON", "DJF"):
        hs = h1.dropna(subset=[f"{s}_corr"])
        f = ols(hs, f"{s}_corr ~ {cls} + h5 + {BD.CTRL2}")
        res.append({"test": "H1 seasonal", "model": "M2", "outcome": f"{s}_corr", "term": "per +5 m mean buffer height", **coef(f, "h5")})
    # H2: extent vs height, all points with valid 0-100 m measures
    h2 = d.dropna(subset=[y, "can_0_100", "vol_0_100"]).copy()
    h2["hc"] = h2.h_can_0_100.fillna(0)
    h2["can10"], h2["vol5"], h2["hc5"] = h2.can_0_100 * 10, h2.vol_0_100 / 5, h2.hc / 5
    for lab, rhs, terms in (("canopy share 0-100 m", "can10", ["can10"]), ("canopy volume 0-100 m", "vol5", ["vol5"]),
                            ("share + height of canopy", "can10 + hc5", ["can10", "hc5"])):
        f = ols(h2, f"{y} ~ {rhs} + {BD.CTRL2}")
        for t in terms:
            unit = {"can10": "per +10 pp canopy", "vol5": "per +5 m mean height (all land)", "hc5": "per +5 m canopy height"}[t]
            res.append({"test": "H2 extent vs height", "model": lab, "outcome": y, "term": unit, **coef(f, t),
                        "aic": f.aic, "r2": f.rsquared})
    # H3: does height modify the width effect
    h3 = d[(d.w_pool >= 10)].dropna(subset=["h_buf", y]).copy()
    med = h3.h_buf.median()
    h3["tall"] = (h3.h_buf >= med).astype(int)
    h3["w_c"] = pd.Categorical(h3.cls_pool, categories=["10-30", "30-50", "50-100", "100-200", "≥200"])
    f = ols(h3, f"{y} ~ C(w_c, Treatment('≥200')) * tall + {BD.CTRL2}")
    for t in f.params.index:
        if "tall" in t:
            res.append({"test": f"H3 width x tall (h_buf >= {med:.1f} m)", "model": "M2", "outcome": y, "term": t, **coef(f, t)})
    res = pd.DataFrame(res)
    res.to_csv(OUT / "height_models.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 220)
    print(res.drop(columns=["outcome"]).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # figure: (a) partial relation height vs corridor LST at fixed width; (b) seasonal height coefficients
    fig, ax = plt.subplots(1, 2, figsize=(18, 7.5), gridspec_kw={"width_ratios": [1.3, 1]})
    fr = ols(h1, f"{y} ~ {cls} + {BD.CTRL2}")
    fh = ols(h1, f"h_buf ~ {cls} + {BD.CTRL2}")
    rx, ry = fh.resid + h1.h_buf.mean(), fr.resid
    ax[0].scatter(rx, ry, s=22, color="#1b7837", alpha=0.45, lw=0)
    bins = np.quantile(rx, np.linspace(0, 1, 9))
    mid = pd.cut(rx, bins, include_lowest=True)
    gm = pd.DataFrame({"x": rx, "y": ry, "b": mid}).groupby("b", observed=True).mean()
    ax[0].plot(gm.x, gm.y, "o-", color="0.15", lw=2.2, ms=8)
    BD.style(ax[0])
    h1row = res[(res.test == "H1 height at fixed width") & (res.model == "M2")].iloc[0]
    ax[0].set(xlabel="Mean canopy height in the forested buffer (m, adjusted)", ylabel="Corridor relative LST (°C, adjusted)",
              title="Taller buffer trees, same width")
    sea = res[res.test == "H1 seasonal"].copy()
    sea["s"] = sea.outcome.str[:3]
    xs = np.arange(len(sea))
    ax[1].bar(xs, sea.coef, color=["#d73027", "#fdae61", "#fdae61", "#4575b4"], width=0.6)
    ax[1].errorbar(xs, sea.coef, yerr=[sea.coef - sea.ci_lo, sea.ci_hi - sea.coef], fmt="none", color="0.2", capsize=4, lw=1.4)
    ax[1].set_xticks(xs, sea.s)
    BD.style(ax[1])
    ax[1].set(ylabel="°C per +5 m buffer canopy height", title="Height effect by season")
    fig.suptitle("Riparian tree height and corridor surface temperature (buffers ≥ 30 m per side)", fontsize=22)
    fig.text(0.99, 0.01, f"Left: partial residuals after width class and controls; black = binned means (8 quantile bins). "
             f"H1 (M2): {h1row.coef:+.2f} °C per +5 m, 95% CI {h1row.ci_lo:+.2f} to {h1row.ci_hi:+.2f}, n = {h1row.n}.\n"
             f"OLS with rich controls; 95% CI clustered by 1 km tile. {CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(FIG / "canopy_height.png", dpi=150)


if __name__ == "__main__":
    main()
