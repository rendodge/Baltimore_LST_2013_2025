"""Per-point riparian buffer attributes for the buffer-width deep dive (inputs to 30_buffer_analysis.py).

Sample points every 150 m along Chesapeake hyper-resolution reaches with an open channel
(cnctR < 0.5). Around each point, a local frame aligned with the reach (along-stream +-150 m,
across +-300 m) is split by bank (sign of the cross product with the local tangent).

From the CC 1 m LULC (2021/22 and 2013/14): canopy fraction in distance bands from the channel
(0-10 ... 200-300 m), per bank and pooled (water excluded); forest continuity = canopy share
within 50 m of the channel over +-500 m along the network.
From 30 m layers: canopy / impervious in rings 300-600 and 600-1000 m (CC 2021/22); terrain at the
point (3DEP via 20_stream_terrain_lst.terrain_blocks: elevation, slope, TPI300/1000, illumination);
reach Strahler order and channel width; distance to the harbour shoreline (NHD coastline);
NSA population density.
LST cross-stream profiles (mean of 30 m pixels in the local frame, by distance from the channel in
30 m bins to 600 m): Jul-Aug mean relative LST (Landsat 8), seasonal mean relative LST (DJF, MAM,
JJA, SON; all-month Landsat 8), summer relative trend, year-round de-seasonalized relative trend.

Output: data/processed/streams/buffer_points_v2.csv.
Run: conda run -p .\\env python scripts\\29_buffer_points.py
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
LULC = {2021: ROOT / "data/raw/cc_lulc/balt_24510_lulc_2021_2024-Edition.tif",
        2013: ROOT / "data/raw/cc_lulc/balt_24510_lulc_2013_2024-Edition.tif"}
OUT = ROOT / "data/processed/streams/buffer_points_v2.csv"
CANOPY = [23, 24, 25, 26, 40, 41, 53, 54, 55, 63, 64, 65, 73, 74, 75]
WATER = [10, 11, 12, 13, 14]
BANDS = [0, 10, 20, 30, 50, 75, 100, 150, 200, 300]
PROFILE = np.arange(0, 630, 30)
STEP, ALONG, ACROSS, CONT = 150, 150, 300, 500
LST_LAYERS = {"jja_julaug": "data/processed/lst_trend/B_mean_rel_lst_C.tif",
              "DJF": "data/processed/lst_allyear/rel_mean_DJF.tif", "MAM": "data/processed/lst_allyear/rel_mean_MAM.tif",
              "JJA": "data/processed/lst_allyear/rel_mean_JJA.tif", "SON": "data/processed/lst_allyear/rel_mean_SON.tif",
              "trend_summer": "data/processed/lst_trend/B_rel_slope_ols.tif",
              "trend_yr": "data/processed/lst_allyear/rel_harmonic_slope.tif"}
warnings.filterwarnings("ignore", "Mean of empty slice|invalid value", RuntimeWarning)


def read(p):
    with rasterio.open(ROOT / p) as s:
        a = s.read(1).astype(float)
        a[a == s.nodata] = np.nan
        return a, s.transform


def main():
    spec = importlib.util.spec_from_file_location("ter", ROOT / "scripts/20_stream_terrain_lst.py")
    T = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(T)
    ter, t30 = T.terrain_blocks()

    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    open_ = cc[cc.cnctR < 0.5].copy()
    with rasterio.open(LULC[2021]) as s:
        lcrs = s.crs
    open_lu = open_.to_crs(lcrs)
    net_lu = cc.to_crs(lcrs)  # whole network for continuity (open and hidden reaches)
    nhd = gpd.read_file(ROOT / "data/vector/streams_nhd_city.gpkg")
    shore = shapely.union_all(nhd[nhd.ftype.astype(int) == 566].geometry.values)
    nsa = gpd.read_file(ROOT / "data/vector/nsa_boundaries_32618.gpkg")
    nsa["dens"] = nsa.Population / (nsa.area / 1e6)
    lst = {k: read(v) for k, v in LST_LAYERS.items()}
    cov30 = {g: read(f"data/processed/cc_lulc/cc_frac_{g}_2021_utm.tif") for g in ("canopy", "structures", "roads", "other_imperv")}
    imp30 = (cov30["structures"][0] + cov30["roads"][0] + cov30["other_imperv"][0], cov30["canopy"][1])
    can30 = cov30["canopy"]

    pts = []
    for idx, g in zip(open_.index, open_.geometry):
        for d in np.arange(STEP / 2, g.length, STEP):
            p, q = g.interpolate(max(d - 5, 0)), g.interpolate(min(d + 5, g.length))
            tx, ty = q.x - p.x, q.y - p.y
            n_ = np.hypot(tx, ty) or 1
            pts.append((idx, g.interpolate(d), tx / n_, ty / n_, g.length))
    print(f"{len(open_)} open reaches, {len(pts)} points")
    srcs = {y: rasterio.open(p) for y, p in LULC.items()}
    rows = []
    for k_, (idx, p_utm, tx, ty, rlen) in enumerate(pts):
        p_lu = gpd.GeoSeries([p_utm], crs=open_.crs).to_crs(lcrs).iloc[0]
        rad = max(ACROSS, CONT) + 120
        b = (p_lu.x - rad, p_lu.y - rad, p_lu.x + rad, p_lu.y + rad)
        win = from_bounds(*b, transform=srcs[2021].transform).round_offsets().round_lengths()
        codes = {y: s.read(1, window=win, boundless=True, fill_value=0) for y, s in srcs.items()}
        wtr = srcs[2021].window_transform(win)
        if (codes[2021] == 0).mean() > 0.10:
            continue
        near_open = open_lu.geometry.iloc[open_lu.sindex.query(shapely.box(*b), predicate="intersects")]
        near_net = net_lu.geometry.iloc[net_lu.sindex.query(shapely.box(*b), predicate="intersects")]
        dist = distance_transform_edt(rasterize([(g, 1) for g in near_open], out_shape=codes[2021].shape,
                                                transform=wtr, fill=0, dtype="uint8") == 0)
        dnet = distance_transform_edt(rasterize([(g, 1) for g in near_net], out_shape=codes[2021].shape,
                                                transform=wtr, fill=0, dtype="uint8") == 0)
        ny, nx = codes[2021].shape
        yy, xx = np.mgrid[0:ny, 0:nx]
        vx, vy = wtr.c + (xx + 0.5) * wtr.a - p_lu.x, wtr.f + (yy + 0.5) * wtr.e - p_lu.y
        along = vx * tx + vy * ty  # tangent from UTM; CRS rotation between UTM and Albers here is < 2 deg
        side = np.sign(tx * vy - ty * vx)
        frame = (np.abs(along) <= ALONG) & (dist <= ACROSS)
        rec = {"reach": idx, "x": p_utm.x, "y": p_utm.y, "reach_len": rlen}
        for yr, cd in codes.items():
            land = (cd > 0) & ~np.isin(cd, WATER)
            can = np.isin(cd, CANOPY)
            for lo, hi in zip(BANDS[:-1], BANDS[1:]):
                band = frame & land & (dist >= lo) & (dist < hi)
                for sd, lab in ((None, "pool"), (1, "L"), (-1, "R")):
                    m = band if sd is None else band & (side == sd)
                    rec[f"can{yr}_{lab}_{lo}_{hi}"] = can[m].mean() if m.sum() > 30 else np.nan
        land21 = (codes[2021] > 0) & ~np.isin(codes[2021], WATER)
        cont = land21 & (dnet <= 50) & (np.hypot(vx, vy) <= CONT)
        rec["continuity_can"] = np.isin(codes[2021], CANOPY)[cont].mean() if cont.sum() > 100 else np.nan
        rows.append(rec)
        if k_ % 100 == 0:
            print(k_, flush=True)
    for s in srcs.values():
        s.close()
    d = pd.DataFrame(rows)

    # 30 m context, profiles, terrain, attributes
    A, tr = lst["jja_julaug"]
    H, W = A.shape
    r0, c0 = np.mgrid[0:H, 0:W]
    px, py = tr.c + (c0 + 0.5) * tr.a, tr.f + (r0 + 0.5) * tr.e
    lines = shapely.union_all(open_.geometry.values)
    tang = {i: (t_x, t_y) for i, (_, _, t_x, t_y, _) in enumerate(pts)}
    pt_lookup = pd.DataFrame([(i, p.x, p.y, t_x, t_y) for i, (_, p, t_x, t_y, _) in enumerate(pts)],
                             columns=["i", "x", "y", "tx", "ty"]).set_index(["x", "y"])
    prof = {k: [] for k in LST_LAYERS}
    ctx = {k: [] for k in ("can_300_600", "imp_300_600", "can_600_1000", "imp_600_1000")}
    for x, y in zip(d.x, d.y):
        t_x, t_y = pt_lookup.loc[(x, y), ["tx", "ty"]].values.ravel()[:2]
        c_, r_ = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
        w = 36
        sl = (slice(max(r_ - w, 0), min(r_ + w + 1, H)), slice(max(c_ - w, 0), min(c_ + w + 1, W)))
        gx, gy = px[sl].ravel(), py[sl].ravel()
        rr = np.hypot(gx - x, gy - y)
        al = np.abs((gx - x) * t_x + (gy - y) * t_y)
        dch = shapely.distance(shapely.points(gx, gy), lines)
        fr = al <= ALONG
        for k, (arr, _) in lst.items():
            v = arr[sl].ravel()
            prof[k].append([np.nanmean(v[fr & (dch >= a) & (dch < a + 30)]) if (fr & (dch >= a) & (dch < a + 30)).sum() >= 2 else np.nan
                            for a in PROFILE])
        for (lo, hi) in ((300, 600), (600, 1000)):
            m = (rr > lo) & (rr <= hi)
            ctx[f"can_{lo}_{hi}"].append(np.nanmean(can30[0][sl].ravel()[m]))
            ctx[f"imp_{lo}_{hi}"].append(np.nanmean(imp30[0][sl].ravel()[m]))
    for k, v in ctx.items():
        d[k] = v
    for k, v in prof.items():
        arr = np.array(v)
        for j, a in enumerate(PROFILE):
            d[f"{k}_p{a}"] = arr[:, j]
    br = np.clip(((t30.f - d.y) / 90).astype(int), 0, ter["elev"].shape[0] - 1)
    bc = np.clip(((d.x - t30.c) / 90).astype(int), 0, ter["elev"].shape[1] - 1)
    for k, a in ter.items():
        d[k] = a[br, bc]
    d["order"] = open_.loc[d.reach, "strOrder"].values
    d["chan_width"] = open_.loc[d.reach, "wdAvg"].values
    pts_g = gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d.x, d.y), crs=32618)
    d["dist_harbour"] = shapely.distance(pts_g.geometry.values, shore)
    j = gpd.sjoin(pts_g[["geometry"]], nsa[["Name", "dens", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    d["nsa"], d["pop_density"] = j.Name.values, j.dens.values
    d["tile"] = (d.x // 1000).astype(int) * 1000 + (d.y // 1000).astype(int)
    d["tile500"] = (d.x // 500).astype(int) * 1000 + (d.y // 500).astype(int)
    d.to_csv(OUT, index=False, float_format="%.4f")
    print(f"{len(d)} points written -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
