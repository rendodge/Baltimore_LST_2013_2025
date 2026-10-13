"""Sensitivity of the main results to hazy / low-contrast scenes (Landsat 8, variant-B scenes).

1. Flag scenes: per scene, thermal contrast (median LST of >= 80% impervious minus >= 70% canopy
   30 m pixels, CC 2021/22) and NDVI contrast (stable >= 90% canopy minus stable >= 95% impervious).
   Both depend on day of year, so each is regressed on day of year and a scene is flagged when
   either standardized residual is <= -2.
2. Recompute, with identical code for all scenes ("base") and without flagged scenes ("excl"):
   city trends (observed, C1, C2 on fixed common pixels; b refitted), per-pixel relative trend
   map, NSA series trends (relative, C1), upper-Gwynns cluster, population-weighted race
   exposure difference, cover-type medians on stable blocks (roof vs turf), NLCD impervious-gain
   effect, and forest NDVI trend.

3. With --jackknife: leave-one-scene-out (each of the 20 scenes dropped in turn) to show how
   much each result depends on any single scene.

Outputs: data/processed/haze/scene_contrast.csv, sensitivity.csv, jackknife.csv.
Run: conda run -p .\\env python scripts\\23_haze_sensitivity.py
"""
import importlib.util
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask, rasterize
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/haze"
CC = ROOT / "data/processed/cc_lulc"
UPPER_GWYNNS = ["Dickeyville", "Franklintown", "Wakefield", "Hunting Ridge", "Gwynns Falls/Leakin Park"]
Z_FLAG = -2.0
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|invalid value|divide by zero", RuntimeWarning)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load_module("lst", ROOT / "scripts/02_lst_trend.py")
N = load_module("nsa", ROOT / "scripts/13_nsa_summary.py")
Q2 = load_module("q2", ROOT / "scripts/11_q2_cover_state_trend.py")
V = load_module("ndvi", ROOT / "scripts/22_ndvi_trend.py")
YEARS = L.YEARS


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(L.OUT / "B_rel_slope_ols.tif") as s:
        tr, shape = s.transform, s.shape
    nsa = gpd.read_file(N.NSA)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
    scenes, lst, _ = L.load_scenes(city)
    use = (scenes.clear_frac_city >= L.MIN_CLEAR).values
    sc = scenes[use].reset_index(drop=True)
    st = lst[use]
    nd = V.ndvi_stack(sc.scene_id)
    wx = pd.read_csv(L.OUT / "C_scene_weather.csv")[["scene_id", "tair_C", "tair_summer_C"]]
    sc = sc.merge(wx, on="scene_id", how="left")
    sc["doy"] = pd.to_datetime(sc.scene_id.str[17:25]).dt.dayofyear

    # --- 1. contrast metrics and flags
    f = lambda g, y: read(CC / f"cc_frac_{g}_{y}_utm.tif")
    imp = {y: f("structures", y) + f("roads", y) + f("other_imperv", y) for y in (2013, 2021)}
    can = {y: f("canopy", y) for y in (2013, 2021)}
    hot, cool = city & (imp[2021] >= 80), city & (can[2021] >= 70)
    forest = city & (can[2013] >= 90) & (can[2021] >= 90)
    paved = city & (imp[2013] >= 95) & (imp[2021] >= 95)
    sc["thermal_contrast"] = [np.nanmedian(st[i][hot]) - np.nanmedian(st[i][cool]) for i in range(len(sc))]
    sc["ndvi_contrast"] = [np.nanmedian(nd[i][forest]) - np.nanmedian(nd[i][paved]) for i in range(len(sc))]
    for k in ("thermal_contrast", "ndvi_contrast"):
        m = smf.ols(f"{k} ~ doy", data=sc).fit()
        res = sc[k] - m.predict(sc)
        sc[f"{k}_z"] = res / res.std()
    sc["flag"] = (sc.thermal_contrast_z <= Z_FLAG) | (sc.ndvi_contrast_z <= Z_FLAG)
    sc.drop(columns=["date"]).to_csv(OUT / "scene_contrast.csv", index=False, float_format="%.3f")
    pd.set_option("display.width", 220)
    print(sc[["scene_id", "doy", "tair_C", "thermal_contrast", "thermal_contrast_z", "ndvi_contrast", "ndvi_contrast_z", "flag"]]
          .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    print("flagged:", list(sc.scene_id[sc.flag]))

    # shared inputs
    nsa["nsa_id"] = np.arange(1, len(nsa) + 1)
    ids = rasterize(zip(nsa.geometry, nsa.nsa_id), out_shape=shape, transform=tr, fill=0, dtype="int32")
    ids = np.where(np.nan_to_num(read(CC / "cc_frac_water_2021_utm.tif")) >= 50, 0, ids)
    census = nsa.drop(columns="geometry")
    nsa_px = {nid: int((ids == nid).sum()) for nid in nsa.nsa_id}
    groups = ["canopy", "structures", "roads", "other_imperv", "turf", "bare", "herb_shrub", "water"]
    fr = {y: {g: block(read(CC / f"cc_frac_{g}_{y}_utm.tif")).ravel() for g in groups} for y in (2013, 2021)}
    va = {y: block(read(CC / f"cc_frac_valid_pct_{y}_utm.tif")).ravel() for y in (2013, 2021)}
    blk = pd.DataFrame({g: fr[2013][g] for g in groups})
    blk["paved"] = blk.roads + blk.other_imperv
    stable = np.logical_and.reduce([np.abs(fr[2021][g] - fr[2013][g]) < 2 for g in groups if g != "water"])
    blk_keep = stable & (va[2013] >= 99) & (va[2021] >= 99) & (blk.water < 10).values
    blk["type"] = Q2.cover_type(blk)
    dimp = block(np.where(city, read(ROOT / "data/processed/landcover/nlcd_dimp_2013_2025_pp.tif"), np.nan)).ravel()

    def run(sel):
        s, x, n = sc[sel].reset_index(drop=True), st[sel], nd[sel]
        yrs = s.year.values
        out = {"scenes": int(sel.sum()), "years": int(len(np.unique(yrs)))}
        # city trends
        b = smf.ols("lst_median ~ tair_C + year", data=s).fit().params.tair_C
        ann_obs = L.annual_mean(x, yrs)
        ann_c1 = L.annual_mean(x - (b * (s.tair_C - s.tair_summer_C)).values[:, None, None], yrs)
        ta_ref = s.groupby("year").tair_summer_C.first().mean()
        ann_c2 = L.annual_mean(x - (b * (s.tair_C - ta_ref)).values[:, None, None], yrs)
        yv = [i for i in range(len(YEARS)) if np.isfinite(ann_obs[i][city]).any()]
        common = np.isfinite(ann_obs[yv]).all(0) & city
        for k, a in (("city_obs", ann_obs), ("city_C1", ann_c1), ("city_C2", ann_c2)):
            r = stats.linregress(YEARS[yv], [np.nanmean(a[i][common]) for i in yv])
            out[k] = r.slope
            out[k + "_p"] = r.pvalue
        out["b"] = b
        # relative trend map
        rel = x - s.lst_median.values[:, None, None].astype("float32")
        ann_rel = L.annual_mean(rel, yrs)
        t = L.trends(ann_rel)
        out["_rel_map"] = t["slope_ols"]
        v = np.isfinite(t["p_ols"][city])
        out["px_sig_pct"] = 100 * (t["p_ols"][city][v] < 0.05).mean()
        # NSA series trends
        rows = []
        for nid in nsa.nsa_id:
            if nsa_px[nid] == 0:
                continue
            a1 = N.series_trend(ann_rel, ids, nid, nsa_px[nid])
            a2 = N.series_trend(ann_c1, ids, nid, nsa_px[nid])
            rows.append({"nsa_id": nid, "rel": a1["slope"], "rel_p": a1["p"], "c1": a2["slope"], "c1_p": a2["p"],
                         "mean_rel": np.nanmean(np.nanmean(ann_rel, 0)[ids == nid])})
        t_n = pd.DataFrame(rows).merge(census[["nsa_id", "Name", "Population", "Blk_AfAm", "White"]], on="nsa_id")
        out["_nsa"] = t_n
        out["nsa_p05"] = int((t_n.rel_p < 0.05).sum())
        out["nsa_q10"] = int((N.bh_q(t_n.rel_p) < 0.10).sum())
        out["nsa_rho_trend_vs_heat"] = stats.spearmanr(t_n.rel, t_n.mean_rel, nan_policy="omit").statistic
        ug, other = t_n[t_n.Name.isin(UPPER_GWYNNS)], t_n[~t_n.Name.isin(UPPER_GWYNNS)]
        out["upperGwynns_c1"], out["other_c1_median"] = ug.c1.mean(), other.c1.median()
        out["upperGwynns_rel"], out["other_rel_median"] = ug.rel.mean(), other.rel.median()
        p = t_n[t_n.Population >= 100]
        for k in ("c1", "rel"):
            out[f"race_diff_{k}"] = (np.nansum(p.Blk_AfAm * p[k]) / p.Blk_AfAm.sum()) - (np.nansum(p.White * p[k]) / p.White.sum())
        # stable blocks by cover type
        bt = block(t["slope_ols"]).ravel()
        tb = pd.Series(bt[blk_keep]).groupby(blk.type.values[blk_keep]).median()
        out["roof_median"], out["turf_median"] = tb.get("Roof-dominated"), tb.get("Turf-dominated")
        out["roof_minus_turf"] = out["roof_median"] - out["turf_median"]
        # impervious-gain effect
        g = np.isfinite(bt) & np.isfinite(dimp) & (dimp >= 5)
        lr = stats.linregress(dimp[g], bt[g])
        out["gain_effect_per10pp"], out["gain_effect_p"] = lr.slope * 10, lr.pvalue
        # forest NDVI trend (scene medians)
        fm = [np.nanmedian(n[i][forest]) for i in range(len(s))]
        r = stats.linregress(s.year, fm)
        out["forest_ndvi_trend"], out["forest_ndvi_p"] = r.slope, r.pvalue
        return out

    base, excl = run(np.ones(len(sc), bool)), run(~sc.flag.values)
    keys = [k for k in base if not k.startswith("_")]
    tab = pd.DataFrame({"metric": keys, "all_scenes": [base[k] for k in keys], "without_flagged": [excl[k] for k in keys]})
    m = np.isfinite(base["_rel_map"]) & np.isfinite(excl["_rel_map"]) & city
    extra = [("rel_map_corr_base_vs_excl", 1.0, float(np.corrcoef(base["_rel_map"][m], excl["_rel_map"][m])[0, 1]))]
    j = base["_nsa"].merge(excl["_nsa"], on="nsa_id", suffixes=("_b", "_e"))
    extra.append(("nsa_rel_rank_corr", 1.0, stats.spearmanr(j.rel_b, j.rel_e, nan_policy="omit").statistic))
    tab = pd.concat([tab, pd.DataFrame(extra, columns=tab.columns)])
    tab.to_csv(OUT / "sensitivity.csv", index=False, float_format="%.5f")
    print(tab.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    if "--jackknife" in sys.argv:
        jk = []
        for i in range(len(sc)):
            sel = np.ones(len(sc), bool)
            sel[i] = False
            o = run(sel)
            jk.append({"dropped": sc.scene_id[i], **{k: o[k] for k in keys}})
            print("dropped", sc.scene_id[i][17:25], "done", flush=True)
        jk = pd.DataFrame(jk)
        jk.to_csv(OUT / "jackknife.csv", index=False, float_format="%.5f")
        summ = pd.DataFrame({"all_scenes": [base[k] for k in keys], "jk_min": jk[keys].min().values,
                             "jk_median": jk[keys].median().values, "jk_max": jk[keys].max().values,
                             "min_at": [jk.dropped[jk[k].idxmin()][17:25] for k in keys],
                             "max_at": [jk.dropped[jk[k].idxmax()][17:25] for k in keys]}, index=keys)
        summ.to_csv(OUT / "jackknife_summary.csv", float_format="%.5f")
        print(summ.to_string(float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
