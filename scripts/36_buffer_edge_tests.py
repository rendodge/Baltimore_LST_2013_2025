"""Two follow-up tests of the buffer-width result, prompted by Kail et al. (2021, Hydrol. Process. 35:e14008).

TEST 1 - does a wider buffer cool land *beyond* itself, or is the corridor effect just the forest inside the
0-60 m window? For each point (29_buffer_points.py frame: +-150 m along the reach, distance from the open
channel in 30 m bins), Jul-Aug relative LST and the 2021/22 CC cover fractions at 30 m (canopy, impervious =
structures + roads + other impervious, turf, water) are averaged per distance bin. Models (OLS, CTRL2,
SEs clustered by 1 km tile):
  1a neighbourhood band 90-210 m: LST ~ width class + band composition
  1b edge band, 90-210 m beyond each point's forest edge (w_pool): LST ~ width class + band composition
     + band distance from channel; 90 m clearance keeps Landsat blur leakage small (simulated)
  1c fixed outer band 150-300 m for points with w_pool <= 50 m (>= 100 m beyond the edge):
     LST ~ w_pool (per 10 m) + band composition
  1d the corridor itself (0-60 m): LST ~ width class + corridor composition, i.e. what the forest beyond the
     measurement window adds once the window's own cover is held fixed
(1b turned out not to be identifiable: the edge band's distance from the channel is almost determined by
width, so width and distance effects cannot be separated; reported but not interpreted.)
Blur check: 1-D Landsat model of 33_detection_limit.py (100 m box + Gaussian sigma 25 m, 30 m grid);
expected blur-only anomaly in the edge band as a fraction of the forest's own anomaly.

TEST 2 - upstream vs downstream canopy. Network topology from CC linkNum/dlinkNum (lines oriented by
topology; DEM confirms 91.5% are digitized downhill). For each point, the stream network 150-500 m
upstream (all tributaries) and 150-500 m downstream (path distance; local +-150 m frame excluded) is
buffered by 50 m and the CC 2021/22 1 m canopy share of land computed; piped share (cnctR >= 0.5) of each
path recorded. Model: LST ~ width class + can_up + can_down + piped_up + piped_down + CTRL2.
Water carries heat downstream, so a water-driven effect predicts can_up > can_down; a land-surface
effect predicts symmetry.

Outputs: data/processed/streams/edge_tests_points.csv, edge_tests_models.csv,
figures/buffer_deepdive/edge_tests.png.
Run after 29, 30: conda run -p .\\env python scripts\\36_buffer_edge_tests.py
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
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy.ndimage import gaussian_filter1d, uniform_filter1d
from shapely.ops import substring

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/buffer_deepdive"
LULC = ROOT / "data/raw/cc_lulc/balt_24510_lulc_2021_2024-Edition.tif"
LST = ROOT / "data/processed/lst_trend/B_mean_rel_lst_C.tif"
FRAC = {g: ROOT / f"data/processed/cc_lulc/cc_frac_{g}_2021_utm.tif"
        for g in ("canopy", "structures", "roads", "other_imperv", "turf", "water")}
CANOPY = [23, 24, 25, 26, 40, 41, 53, 54, 55, 63, 64, 65, 73, 74, 75]
WATER = [10, 11, 12, 13, 14]
PROFILE = np.arange(0, 630, 30)
ALONG, L0, L1, NET_BUF = 150, 150, 500, 50
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; land cover and streams: Chesapeake Conservancy / UMBC"
warnings.filterwarnings("ignore")
spec = importlib.util.spec_from_file_location("bd", ROOT / "scripts/30_buffer_analysis.py")
BD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BD)


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype(float)
        if s.nodata is not None:
            a[a == s.nodata] = np.nan
        return a, s.transform


def merged(g):
    g = shapely.line_merge(g)
    if g.geom_type == "MultiLineString":  # unmerged parts: keep the longest
        g = max(g.geoms, key=lambda x: x.length)
    return g


# ------------------------------------------------------------------ test 1 inputs
def band_profiles(d, open_):
    lst, tr = read(LST)
    fr = {}
    for k, p in FRAC.items():
        a, t2 = read(p)
        assert t2 == tr and a.shape == lst.shape, f"{k} grid differs from LST grid"
        fr[k] = a
    fr["imperv"] = fr.pop("structures") + fr.pop("roads") + fr.pop("other_imperv")
    H, W = lst.shape
    r0, c0 = np.mgrid[0:H, 0:W]
    px, py = tr.c + (c0 + 0.5) * tr.a, tr.f + (r0 + 0.5) * tr.e
    lines = shapely.union_all(open_.geometry.values)
    out = {f"{k}_b{a}": [] for k in ("lst", *fr) for a in PROFILE}
    for rid, x, y in zip(d.reach, d.x, d.y):
        g = merged(open_.loc[rid].geometry)
        s_ = g.project(shapely.Point(x, y))
        a_, b_ = g.interpolate(max(s_ - 5, 0)), g.interpolate(min(s_ + 5, g.length))
        t = np.array([b_.x - a_.x, b_.y - a_.y])
        tx, ty = t / (np.linalg.norm(t) or 1)
        c_, r_ = int((x - tr.c) / tr.a), int((y - tr.f) / tr.e)
        w = 36
        sl = (slice(max(r_ - w, 0), min(r_ + w + 1, H)), slice(max(c_ - w, 0), min(c_ + w + 1, W)))
        gx, gy = px[sl].ravel(), py[sl].ravel()
        inframe = np.abs((gx - x) * tx + (gy - y) * ty) <= ALONG
        dch = shapely.distance(shapely.points(gx, gy), lines)
        arrs = {"lst": lst[sl].ravel(), **{k: v[sl].ravel() for k, v in fr.items()}}
        for a in PROFILE:
            m = inframe & (dch >= a) & (dch < a + 30)
            for k, v in arrs.items():
                out[f"{k}_b{a}"].append(np.nanmean(v[m]) if m.sum() >= 2 else np.nan)
    return pd.DataFrame(out, index=d.index)


def band_mean(d, prefix, lo, hi):
    """Mean over 30 m bins whose start lies in [lo, hi); lo/hi may vary per point."""
    lo, hi = np.broadcast_to(lo, len(d)), np.broadcast_to(hi, len(d))
    cols = [f"{prefix}_b{a}" for a in PROFILE]
    v = d[cols].values
    m = (PROFILE[None, :] >= lo[:, None]) & (PROFILE[None, :] < hi[:, None])
    v = np.where(m, v, np.nan)
    n_ok = np.isfinite(v).sum(1)
    return np.where(n_ok >= 2, np.nanmean(v, 1), np.nan)


def blur_leak(w, gap_lo=90, gap_hi=210, footprint=100, grid=30, half=1500):
    """Landsat blur model: blurred anomaly in [w+gap_lo, w+gap_hi] as a fraction of the forest anomaly."""
    x = np.arange(-half, half + 1)
    true = np.where(np.abs(x) <= w, -1.0, 0.0)
    obs = gaussian_filter1d(uniform_filter1d(true, footprint, mode="nearest"), 0.25 * footprint)
    vals = []
    for phase in range(0, grid, 5):
        centres = np.arange(-half + phase, half, grid)
        samp = np.interp(x, centres, np.interp(centres, x, obs))
        sel = (np.abs(x) >= w + gap_lo) & (np.abs(x) < w + gap_hi)
        vals.append(samp[sel].mean())
    return -np.mean(vals)


# ------------------------------------------------------------------ test 2 inputs
def network(cc, dem_path):
    g = {i: merged(geom) for i, geom in zip(cc.index, cc.geometry)}
    link = dict(zip(cc.linkNum, cc.index))
    down = {i: link.get(dl) for i, dl in zip(cc.index, cc.dlinkNum)}
    ups = {i: [] for i in cc.index}
    for i, dn in down.items():
        if dn is not None and dn != i:
            ups[dn].append(i)
    with rasterio.open(dem_path) as s:
        def elev(p):
            q = gpd.GeoSeries([shapely.Point(p)], crs=cc.crs).to_crs(s.crs).iloc[0]
            return next(s.sample([(q.x, q.y)]))[0]
        n_flip, n_dem = 0, 0
        for i, line in g.items():
            a, b = shapely.Point(line.coords[0]), shapely.Point(line.coords[-1])
            if down[i] is not None:  # downstream end touches the downstream reach
                dg = g[down[i]]
                flip = a.distance(dg) < b.distance(dg)
            elif ups[i]:  # upstream end touches the tributaries
                flip = min(b.distance(g[u]) for u in ups[i]) < min(a.distance(g[u]) for u in ups[i])
            else:
                n_dem += 1
                flip = elev(line.coords[0]) < elev(line.coords[-1])
            if flip:
                g[i] = shapely.LineString(line.coords[::-1])
                n_flip += 1
    print(f"network: {len(g)} reaches, {n_flip} flipped to downstream orientation, {n_dem} oriented by DEM only")
    return g, down, ups


def path_up(g, ups, rid, a, b, out, depth=0):
    """Network upstream of reach rid's downstream end, between path distances a and b (all tributaries)."""
    L = g[rid].length
    if a < L:
        out.append((rid, substring(g[rid], max(L - b, 0), L - a)))
    if b > L and depth < 50:
        for u in ups[rid]:
            path_up(g, ups, u, max(a - L, 0), b - L, out, depth + 1)


def path_down(g, down, rid, a, b, out, depth=0):
    """Network downstream of reach rid's upstream start, between path distances a and b."""
    L = g[rid].length
    if a < L:
        out.append((rid, substring(g[rid], a, min(b, L))))
    if b > L and down[rid] is not None and depth < 50:
        path_down(g, down, down[rid], max(a - L, 0), b - L, out, depth + 1)


def directional(d, cc):
    import glob
    dem = sorted(glob.glob(str(ROOT / "data/raw/terrain/3dep_*_subset.tif")))[0]
    g, down, ups = network(cc, dem)
    piped = (cc.cnctR >= 0.5).to_dict()
    lu = rasterio.open(LULC)
    rows = []
    for rid, x, y in zip(d.reach, d.x, d.y):
        line = g[rid]
        s_ = line.project(shapely.Point(x, y))
        L = line.length
        rec = {}
        for lab, pieces in (("up", []), ("down", [])):
            if lab == "up":
                path_up(g, ups, rid, (L - s_) + L0, (L - s_) + L1, pieces)
            else:
                path_down(g, down, rid, s_ + L0, s_ + L1, pieces)
            pieces = [(r, p) for r, p in pieces if p.length > 1]
            plen = sum(p.length for _, p in pieces)
            rec[f"len_{lab}"] = plen
            rec[f"piped_{lab}"] = sum(p.length for r, p in pieces if piped[r]) / plen if plen else np.nan
            if plen < 50:
                rec[f"can_{lab}"] = np.nan
                continue
            poly = gpd.GeoSeries([shapely.union_all([p for _, p in pieces]).buffer(NET_BUF)], crs=cc.crs).to_crs(lu.crs).iloc[0]
            win = from_bounds(*poly.bounds, transform=lu.transform).round_offsets().round_lengths()
            codes = lu.read(1, window=win, boundless=True, fill_value=0)
            m = rasterize([(poly, 1)], out_shape=codes.shape, transform=lu.window_transform(win), fill=0, dtype="uint8") == 1
            land = m & (codes > 0) & ~np.isin(codes, WATER)
            rec[f"can_{lab}"] = np.isin(codes, CANOPY)[land].mean() if land.sum() > 500 else np.nan
        rows.append(rec)
    lu.close()
    return pd.DataFrame(rows, index=d.index)


def ols(dd, f):
    return smf.ols(f, data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.tile})


def row(test, model, f, term, n, extra=None):
    ci = f.conf_int().loc[term]
    return {"test": test, "model": model, "term": term, "coef": f.params[term], "ci_lo": ci[0], "ci_hi": ci[1],
            "p": f.pvalues[term], "n": n, **(extra or {})}


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    d = BD.prep(pd.read_csv(OUT / "buffer_points_v2.csv"))
    cc = gpd.read_file(ROOT / "data/vector/streams_cc_city.gpkg")
    open_ = cc[cc.cnctR < 0.5]
    cache = OUT / "edge_tests_points.csv"
    if cache.exists():
        extra = pd.read_csv(cache, index_col=0)
    else:
        extra = pd.concat([band_profiles(d, open_), directional(d, cc)], axis=1)
        extra.to_csv(cache, float_format="%.4f")
    d = d.join(extra)
    cls = f"C(cls_pool, Treatment('{BD.REF}'))"
    comp = "can_band + imp_band + turf_band + wat_band"
    res = []

    # check: the profile LST reproduces 29's profiles (same grid and frame)
    chk = np.corrcoef(d.lst_b0.dropna(), d.loc[d.lst_b0.notna(), "jja_julaug_p0"])[0, 1]
    print(f"check: bin-0 LST vs 29 profile r = {chk:.3f}")

    def add_band(lo, hi):
        dd = d.copy()
        dd["y"] = band_mean(dd, "lst", lo, hi)
        for k, c in (("canopy", "can_band"), ("imperv", "imp_band"), ("turf", "turf_band"), ("water", "wat_band")):
            dd[c] = band_mean(dd, k, lo, hi) * 10  # per 10 pp
        dd["band_dist"] = (np.broadcast_to(lo, len(dd)) + np.broadcast_to(hi, len(dd))) / 2
        return dd.dropna(subset=["y", "can_band", "imp_band"])

    def class_rows(test, model, f, dd):
        for lab in BD.WLAB[:-1]:
            t = f"{cls}[T.{lab}]"
            if t in f.params:
                res.append(row(test, model, f, t, int((dd.cls_pool == lab).sum()), {"class": lab}))

    # 1a: neighbourhood 90-210 m, with and without its own composition
    dd = add_band(90, 210)
    for lab, rhs in (("M2", BD.CTRL2), ("M2 + band composition", f"{comp} + {BD.CTRL2}")):
        class_rows("1a nbhd 90-210 m", lab, ols(dd, f"y ~ {cls} + {rhs}"), dd)
    # 1b: edge band 90-210 m beyond each point's forest edge
    w = d.w_pool.values
    dd = add_band(w + 90, w + 210)
    print(f"1b edge band: n = {len(dd)}; by class", dd.cls_pool.value_counts().reindex(BD.WLAB).to_dict())
    for lab, rhs in (("M2 + band distance", f"band_dist + {BD.CTRL2}"),
                     ("M2 + band distance + band composition", f"band_dist + {comp} + {BD.CTRL2}")):
        class_rows("1b edge+90-210 m", lab, ols(dd, f"y ~ {cls} + {rhs}"), dd)
    # 1c: narrow buffers only, fixed outer band 150-300 m
    dd = add_band(150, 300)
    dd = dd[dd.w_pool <= 50].copy()
    dd["w10"] = dd.w_pool / 10
    for lab, rhs in (("M2", BD.CTRL2), ("M2 + band composition", f"{comp} + {BD.CTRL2}")):
        f = ols(dd, f"y ~ w10 + {rhs}")
        res.append(row("1c band 150-300 m, w <= 50", lab, f, "w10", len(dd), {"class": "per +10 m width"}))
    # 1d: the corridor itself (0-60 m), holding the corridor's own cover fixed -> what the wider forest adds
    dd = add_band(0, 60)
    for lab, rhs in (("M2", BD.CTRL2), ("M2 + corridor composition", f"{comp} + {BD.CTRL2}")):
        class_rows("1d corridor 0-60 m", lab, ols(dd, f"y ~ {cls} + {rhs}"), dd)
    leak = {wv: blur_leak(wv) for wv in (10, 30, 50, 100, 200, 300)}
    print("blur leakage into edge+90-210 m band (fraction of forest anomaly):", {k: round(v, 3) for k, v in leak.items()})

    # TEST 2: directional continuity
    dd = d.dropna(subset=["can_up", "can_down", "jja_julaug_corr"]).copy()
    dd = dd[(dd.len_up >= 175) & (dd.len_down >= 175)].copy()
    dd["can_up10"], dd["can_down10"] = dd.can_up * 10, dd.can_down * 10
    print(f"test 2: n = {len(dd)} points with >= 175 m of network both ways; "
          f"corr(can_up, can_down) = {dd[['can_up', 'can_down']].corr().iloc[0, 1]:.2f}")
    for y in ("jja_julaug_corr", "jja_julaug_nbhd", "DJF_corr"):
        f = ols(dd, f"{y} ~ {cls} + can_up10 + can_down10 + piped_up + piped_down + {BD.CTRL2}")
        wt = f.t_test("can_up10 - can_down10")
        for t in ("can_up10", "can_down10"):
            res.append(row("2 directional", y, f, t, len(dd),
                           {"class": "per +10 pp canopy", "diff_up_minus_down": float(wt.effect.ravel()[0]),
                            "diff_p": float(wt.pvalue)}))
    res = pd.DataFrame(res)
    res.to_csv(OUT / "edge_tests_models.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 240)
    show = res.copy()
    show["term"] = show["class"]
    print(show.drop(columns=["class"]).to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    # figure
    fig, ax = plt.subplots(1, 2, figsize=(18, 7.5), gridspec_kw={"width_ratios": [1.4, 1]})
    sets = [("1d corridor 0-60 m", "M2", "Corridor 0–60 m (as reported)", "#fdae6b", -0.27),
            ("1d corridor 0-60 m", "M2 + corridor composition", "… holding the corridor's own cover fixed", "#e6550d", -0.09),
            ("1a nbhd 90-210 m", "M2", "Neighbourhood 90–210 m", "#9ecae1", 0.09),
            ("1a nbhd 90-210 m", "M2 + band composition", "… holding its own cover fixed", "#3182bd", 0.27)]
    x = np.arange(len(BD.WLAB) - 1)
    for test, model, lab, colr, off in sets:
        t = res[(res.test == test) & (res.model == model)].set_index("class").reindex(BD.WLAB[:-1])
        ax[0].errorbar(x + off, t.coef, yerr=[t.coef - t.ci_lo, t.ci_hi - t.coef], fmt="o", ms=7, color=colr,
                       capsize=3, lw=1.4, label=lab)
    BD.style(ax[0])
    ax[0].set_xticks(x, [f"{l} m" for l in BD.WLAB[:-1]], fontsize=15)
    ax[0].set(xlabel="Forested buffer width, per side", ylabel="Relative LST vs ≥ 200 m buffer (°C)",
              title="Test 1: cooling beyond the buffer")
    ax[0].legend(fontsize=12, frameon=False, loc="upper right")
    t2 = res[(res.test == "2 directional")]
    ys = ["jja_julaug_corr", "jja_julaug_nbhd", "DJF_corr"]
    ylab = {"jja_julaug_corr": "Corridor\nJul–Aug", "jja_julaug_nbhd": "90–210 m\nJul–Aug", "DJF_corr": "Corridor\nwinter"}
    for k, (term, colr, lab) in enumerate((("can_up10", "#2166ac", "upstream 150–500 m"), ("can_down10", "#b2182b", "downstream 150–500 m"))):
        s = t2[t2.term == term].set_index("model").reindex(ys)
        xx = np.arange(len(ys)) + (k - 0.5) * 0.3
        ax[1].bar(xx, s.coef, width=0.3, color=colr, label=lab)
        ax[1].errorbar(xx, s.coef, yerr=[s.coef - s.ci_lo, s.ci_hi - s.coef], fmt="none", color="0.2", capsize=4, lw=1.3)
    BD.style(ax[1])
    ax[1].set_xticks(np.arange(len(ys)), [ylab[y] for y in ys], fontsize=15)
    ax[1].set(ylabel="°C per +10 pp canopy along the network", title="Test 2: upstream vs downstream canopy")
    ax[1].legend(fontsize=12, frameon=False, loc="lower left")
    fig.suptitle("Is the buffer effect more than the forest itself, and does it follow the water?", fontsize=22)
    fig.text(0.99, 0.01, "OLS with rich controls; 95% CI clustered by 1 km tile. Band composition = canopy, impervious, turf and water "
             "fractions of the band (CC 2021/22, 30 m).\n" + CREDIT, ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.07, 1, 0.95))
    fig.savefig(FIG / "edge_tests.png", dpi=150)


if __name__ == "__main__":
    main()
