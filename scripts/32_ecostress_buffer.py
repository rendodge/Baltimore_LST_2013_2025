"""Riparian buffer width vs ECOSTRESS LST by time of day (June-August, 2018-2025, 70 m).

Per granule (31_acquire_ecostress.py subsets): LST (K) kept where cloud == 0, QC mandatory bits (0-1)
are 0 or 1 (best / nominal), and 250 K < LST < 350 K; scenes need >= 50% of city pixels valid.
Relative LST = pixel - scene city median. Local time = UTC - 4 h (EDT); bins: night 22-05,
morning 06-09, midday 10-13, afternoon 14-17, evening 18-21. Per bin, mean relative LST per pixel
(>= 3 scenes). Buffer points and widths from 29/30 (per-side width, banks pooled; reference >= 200 m);
corridor (0-60 m) and neighbourhood (90-210 m) means of 70 m pixels in the local along-stream frame;
model M2 from 30_buffer_analysis.py (rich controls, SEs clustered by 1 km tile), per bin.

Outputs: data/processed/ecostress/rel_mean_<bin>.tif, scenes.csv, buffer_by_time.csv,
figures/buffer_deepdive/ecostress_time_of_day.png.
Run after 29, 31: conda run -p .\\env python scripts\\32_ecostress_buffer.py
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
from rasterio.features import geometry_mask

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/ecostress"
OUT = ROOT / "data/processed/ecostress"
FIG = ROOT / "figures/buffer_deepdive"
BINS = {"night": list(range(22, 24)) + list(range(0, 6)), "morning": range(6, 10), "midday": range(10, 14),
        "afternoon": range(14, 18), "evening": range(18, 22)}
CREDIT = "ECOSTRESS LST: NASA JPL / LP DAAC (ECO_L2T_LSTE v002); land cover and streams: Chesapeake Conservancy / UMBC"
warnings.filterwarnings("ignore")
spec = importlib.util.spec_from_file_location("bd", ROOT / "scripts/30_buffer_analysis.py")
BD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BD)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gs = pd.read_csv(RAW / "granules_jja.csv")
    gs["time_utc"] = pd.to_datetime(gs.time_utc, utc=True, format="mixed")
    nsa = gpd.read_file(ROOT / "data/vector/nsa_boundaries_32618.gpkg")
    stack, meta = [], []
    prof = city = None
    for g in gs.itertuples(index=False):
        d = RAW / g.granule
        try:
            with rasterio.open(d / f"{g.granule}_LST_subset.tif") as s:
                lst = s.read(1).astype("float32")
                if prof is None:
                    prof, tr, shape = s.profile.copy(), s.transform, s.shape
                    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
            with rasterio.open(d / f"{g.granule}_cloud_subset.tif") as s:
                cloud = s.read(1)
            with rasterio.open(d / f"{g.granule}_QC_subset.tif") as s:
                qc = s.read(1).astype("int64")
        except Exception:
            continue
        if lst.shape != shape:
            continue
        ok = (cloud == 0) & ((qc & 0b11) <= 1) & (lst > 250) & (lst < 350)
        frac = (ok & city).sum() / city.sum()
        local_h = (g.time_utc.hour - 4) % 24
        meta.append({"granule": g.granule, "time_utc": g.time_utc, "local_hour": local_h, "clear_frac": frac})
        if frac >= 0.5:
            v = np.where(ok, lst - 273.15, np.nan)
            stack.append(v - np.nanmedian(v[city]))
        else:
            stack.append(None)
    meta = pd.DataFrame(meta)
    meta["used"] = [s is not None for s in stack]
    meta["bin"] = meta.local_hour.map({h: b for b, hs in BINS.items() for h in hs})
    meta.to_csv(OUT / "scenes.csv", index=False)
    print(f"granules read {len(meta)}, used (>= 50% clear) {meta.used.sum()}; by bin:",
          meta[meta.used].bin.value_counts().reindex(list(BINS)).to_dict())

    means = {}
    p = prof.copy()
    p.update(driver="GTiff", dtype="float32", nodata=-9999.0, count=1, compress="deflate")
    for b in BINS:
        idx = [i for i, (u, bb) in enumerate(zip(meta.used, meta.bin)) if u and bb == b]
        if not idx:
            continue
        arr = np.stack([stack[i] for i in idx])
        n = np.isfinite(arr).sum(0)
        m = np.where(n >= 3, np.nanmean(arr, 0), np.nan)
        means[b] = m
        with rasterio.open(OUT / f"rel_mean_{b}.tif", "w", **p) as dst:
            dst.write(np.where(np.isfinite(m) & city, m, -9999.0).astype("float32"), 1)
            dst.set_band_description(1, f"ECOSTRESS mean relative LST, {b} (C), Jun-Aug 2018-2025, n={len(idx)}")

    # points: widths from the Landsat deep-dive input
    d = BD.prep(pd.read_csv(ROOT / "data/processed/streams/buffer_points_v2.csv"))
    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    open_ = cc[cc.cnctR < 0.5]
    lines = shapely.union_all(open_.geometry.values)
    H, W = shape
    r0, c0 = np.mgrid[0:H, 0:W]
    px, py = tr.c + (c0 + 0.5) * tr.a, tr.f + (r0 + 0.5) * tr.e
    # local tangent per point from its reach
    tang = []
    for rid, x, y in zip(d.reach, d.x, d.y):
        g = open_.loc[rid].geometry
        s_ = g.project(shapely.Point(x, y))
        a, c_ = g.interpolate(max(s_ - 5, 0)), g.interpolate(min(s_ + 5, g.length))
        v = np.array([c_.x - a.x, c_.y - a.y])
        tang.append(v / (np.linalg.norm(v) or 1))
    tang = np.array(tang)
    for b, m in means.items():
        corr, nb = [], []
        for (x, y), (tx, ty) in zip(zip(d.x, d.y), tang):
            cc_, rr_ = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
            w = 6
            sl = (slice(max(rr_ - w, 0), min(rr_ + w + 1, H)), slice(max(cc_ - w, 0), min(cc_ + w + 1, W)))
            gx, gy, gv = px[sl].ravel(), py[sl].ravel(), m[sl].ravel()
            fr = np.abs((gx - x) * tx + (gy - y) * ty) <= 150
            dch = shapely.distance(shapely.points(gx, gy), lines)
            c1 = fr & (dch <= 60)
            c2 = fr & (dch > 90) & (dch <= 210)
            corr.append(np.nanmean(gv[c1]) if c1.any() else np.nan)
            nb.append(np.nanmean(gv[c2]) if c2.sum() >= 2 else np.nan)
        d[f"eco_{b}_corr"], d[f"eco_{b}_nbhd"] = corr, nb
    res = []
    for b in means:
        for loc in ("corr", "nbhd"):
            r, _ = BD.fit(d, f"eco_{b}_{loc}", BD.CTRL2, label=f"{b}_{loc}")
            r["time_bin"], r["location"] = b, loc
            res.append(r)
    res = pd.concat(res)
    res.to_csv(OUT / "buffer_by_time.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 220)
    print(res.pivot_table(index=["location", "time_bin"], columns="class", values="coef_C", sort=False)
          .reindex(columns=BD.WLAB).round(2).to_string())
    key = res[res["class"].isin(["10-30", "30-50", "50-100"])][["time_bin", "location", "class", "coef_C", "ci_lo", "ci_hi", "p", "n"]]
    print(key.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    fig, ax = plt.subplots(1, 2, figsize=(18, 7), sharey=True)
    cols = {"night": "#313695", "morning": "#74add1", "midday": "#fdae61", "afternoon": "#d73027", "evening": "#762a83"}
    x = np.arange(len(BD.WLAB))
    for a, loc, title in ((ax[0], "corr", "In the corridor (0–60 m)"), (ax[1], "nbhd", "Neighbourhood (90–210 m)")):
        for k, (b, colr) in enumerate(cols.items()):
            t = res[(res.time_bin == b) & (res.location == loc)].set_index("class").reindex(BD.WLAB)
            if t.coef_C.isna().all():
                continue
            n_sc = int(meta[meta.used & (meta.bin == b)].shape[0])
            a.errorbar(x + (k - 2) * 0.13, t.coef_C, yerr=[t.coef_C - t.ci_lo, t.ci_hi - t.coef_C], fmt="o", ms=7, color=colr,
                       capsize=3, lw=1.3, label=f"{b} ({n_sc} scenes)")
        BD.style(a)
        a.set_xticks(x, [f"{l} m" for l in BD.WLAB], fontsize=15)
        a.set(xlabel="Forested buffer width, per side", title=title)
    ax[0].set_ylabel("Relative LST vs ≥ 200 m buffer (°C)")
    ax[0].legend(fontsize=13, frameon=False, loc="upper right")
    fig.suptitle("Riparian buffer width and LST by time of day (ECOSTRESS, Jun–Aug 2018–2025)", fontsize=22)
    fig.text(0.99, 0.01, f"OLS with rich controls; 95% CI clustered by 1 km tile. Local time EDT.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(FIG / "ecostress_time_of_day.png", dpi=150)


if __name__ == "__main__":
    main()
