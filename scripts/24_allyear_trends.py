"""Year-round LST trends, Landsat 8, 2013-2025 (all months; scenes >= 50% of the city clear).

Versions (per scene):
  relative  = LST - scene city median                       (spatial patterns)
  C1        = LST - b_season * (T_air - T_air[season, season-year])   sampling luck removed, climate kept
  C2        = LST - b_season * (T_air - T_air[season, 2013-2025])     also removes the climate trend
T_air = BWI METAR air temperature interpolated to the scene-centre time; references are means over
all days of that season at 15:46 UTC. b_season is fitted per season on scene city medians
(LST_med ~ T_air + year), since the LST-air relation differs between leaf-on and leaf-off seasons.
Seasons: DJF (December counted with the following year), MAM, JJA, SON.

1. Per pixel: harmonic regression on all scenes, y = a + b*t + annual + semi-annual harmonics
   (t in years) -> de-seasonalized trend (deg C/yr), SE, p. Needs >= 40 scenes over >= 8 years.
   Per season: one mean per season-year, OLS trend (>= 7 season-years).
2. City: scene city medians -> the same harmonic model (year-round) and season-only trends, SEs
   clustered by season-year; observed / C1 / C2 and leave-one-year-out range for C1.
3. Season comparison: hot-cool contrast, cross-sectional cover effects (90 m blocks; CC 2021/22
   fractions, turf reference), and between-season correlation of mean relative LST and trends.
4. NSA: NSA-mean series per scene (>= 50% of pixels valid) -> harmonic trend (relative, C1),
   year-clustered 95% CI, Benjamini-Hochberg q.
5. Paving / cover change: relative trend (year-round and by season) vs NLCD impervious gain
   (>= 5 pp blocks) and by CC replacement cover where impervious was lost (>= 5 pp).

Outputs: data/processed/lst_allyear/, figures/allyear/.
Run after 01 --all-months, 03, 06, 09: conda run -p .\\env python scripts\\24_allyear_trends.py
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
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask, rasterize
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load_module("lst", ROOT / "scripts/02_lst_trend.py")
W = load_module("bwi", ROOT / "scripts/04_lst_bwi_normalized.py")
N = load_module("nsa", ROOT / "scripts/13_nsa_summary.py")
OUT = ROOT / "data/processed/lst_allyear"
FIG = ROOT / "figures/allyear"
CC = ROOT / "data/processed/cc_lulc"
SEASONS = ["DJF", "MAM", "JJA", "SON"]
SEASON_OF = {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA",
             9: "SON", 10: "SON", 11: "SON"}
SEASON_LABEL = {"DJF": "Winter (DJF)", "MAM": "Spring (MAM)", "JJA": "Summer (JJA)", "SON": "Fall (SON)", "ALL": "Year-round"}
MIN_SCENES, MIN_YEARS, MIN_SEASON_YEARS = 40, 8, 7
COVER = "canopy + structures + roads + other_imperv + bare + herb_shrub"
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; air temperature: NOAA ISD (KBWI)"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|invalid value|divide by zero|Degrees of freedom", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def read(p):
    with rasterio.open(p) as s:
        a = s.read(1).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def block(a, k=3):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((1, 3)) >= k * k - 2, np.nanmean(b, (1, 3)), np.nan)


def design(t, doy):
    w = 2 * np.pi * doy / 365.25
    return np.column_stack([np.ones_like(t), t, np.cos(w), np.sin(w), np.cos(2 * w), np.sin(2 * w)])


def harmonic_pixels(stack, X, years, chunk=40000):
    """Per-pixel weighted least squares with NaN masking. Returns slope, se, p, n, level at mid-period."""
    n_sc, H, Wd = stack.shape
    Y = stack.reshape(n_sc, -1)
    P = Y.shape[1]
    out = {k: np.full(P, np.nan) for k in ("slope", "se", "p", "n", "level", "slope_annual", "p_annual")}
    uy = np.unique(years)
    yr_onehot = (years[:, None] == np.unique(years)[None, :]).astype(float)
    tmid = X[:, 1].mean()
    for a in range(0, P, chunk):
        y = Y[:, a:a + chunk].astype("float64")
        m = np.isfinite(y)
        y0 = np.where(m, y, 0.0)
        mf = m.astype(float)
        k = X.shape[1]
        XtX = np.empty((y.shape[1], k, k))
        for i in range(k):
            for j in range(i, k):
                XtX[:, i, j] = XtX[:, j, i] = mf.T @ (X[:, i] * X[:, j])
        Xty = y0.T @ X
        n = mf.sum(0)
        nyr = ((mf.T @ yr_onehot) > 0).sum(1)
        ok = (n >= MIN_SCENES) & (nyr >= MIN_YEARS)
        if not ok.any():
            continue
        beta = np.full((y.shape[1], k), np.nan)
        beta[ok] = np.linalg.solve(XtX[ok], Xty[ok][..., None])[..., 0]
        resid = np.where(m, y - X @ beta.T, 0.0)
        rss = (resid ** 2).sum(0)
        inv11 = np.full(y.shape[1], np.nan)
        inv11[ok] = np.linalg.inv(XtX[ok])[:, 1, 1]
        se = np.sqrt(rss / np.maximum(n - k, 1) * inv11)
        sl = slice(a, a + chunk)
        out["slope"][sl] = beta[:, 1]
        out["se"][sl] = se
        out["p"][sl] = 2 * stats.t.sf(np.abs(beta[:, 1] / se), np.maximum(n - k, 1))
        out["n"][sl] = n
        out["level"][sl] = beta[:, 0] + beta[:, 1] * tmid
        # stricter test: remove the fitted seasonal cycle, average to one value per season-year, OLS
        ds = np.where(m, y - X[:, 2:] @ beta[:, 2:].T, np.nan)
        ann = np.stack([np.nanmean(ds[years == u], 0) for u in uy])
        sa, pa = annual_ols(ann, uy.astype(float))
        out["slope_annual"][sl], out["p_annual"][sl] = sa, pa
    return {k: v.reshape(H, Wd) for k, v in out.items()}


def annual_ols(ann, x, min_years=MIN_YEARS):
    """Vectorized OLS of annual values (years x pixels, NaN allowed) on x; returns slope, p."""
    m = np.isfinite(ann)
    n = m.sum(0)
    X = np.where(m, x[:, None], np.nan)
    xm, ym = np.nanmean(X, 0), np.nanmean(ann, 0)
    sxx = np.nansum((X - xm) ** 2, 0)
    b = np.nansum((X - xm) * (ann - ym), 0) / sxx
    rss = np.nansum((ann - (ym + b * (X - xm))) ** 2, 0)
    se = np.sqrt(rss / np.maximum(n - 2, 1) / sxx)
    p = 2 * stats.t.sf(np.abs(b / se), np.maximum(n - 2, 1))
    ok = n >= min_years
    return np.where(ok, b, np.nan), np.where(ok, p, np.nan)


def scene_trend(df, y, seasonal=True):
    """Scene-level trend with harmonics (or none), SE clustered by season-year."""
    f = f"{y} ~ t" + (" + c1 + s1 + c2 + s2" if seasonal else "")
    d = df.dropna(subset=[y])
    m = smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d.season_year})
    ci = m.conf_int().loc["t"]
    return {"slope": m.params.t, "ci_lo": ci[0], "ci_hi": ci[1], "p": m.pvalues.t, "n_scenes": int(m.nobs),
            "n_years": int(d.season_year.nunique())}


def style(ax, zero=True):
    ax.grid(axis="y", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("0.6")
    ax.tick_params(colors="0.35")
    if zero:
        ax.axhline(0, color="0.45", lw=1.2, ls="--", zorder=1)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    with rasterio.open(L.OUT / "B_rel_slope_ols.tif") as s:
        tr, shape, prof = s.transform, s.shape, s.profile.copy()
    nsa = gpd.read_file(N.NSA)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
    scenes, stack, _ = L.load_scenes(city, months=tuple(range(1, 13)))
    use = (scenes.clear_frac_city >= L.MIN_CLEAR).values
    sc = scenes[use].reset_index(drop=True)
    st = stack[use]
    del stack
    sc["date"] = pd.to_datetime(sc.scene_id.str[17:25])
    sc["month"], sc["doy"] = sc.date.dt.month, sc.date.dt.dayofyear
    sc["season"] = sc.month.map(SEASON_OF)
    sc["season_year"] = sc.year + (sc.month == 12)
    sc["t"] = sc.year + (sc.doy - 0.5) / 365.25 - 2013
    X = design(sc.t.values, sc.doy.values)
    sc["c1"], sc["s1"], sc["c2"], sc["s2"] = X[:, 2], X[:, 3], X[:, 4], X[:, 5]
    print(f"scenes: {len(scenes)} on disk, {len(sc)} >= 50% clear; by season:", sc.season.value_counts().to_dict())

    # --- weather and adjustments
    isd = W.parse_isd()
    sc["tair_C"] = [W.interp_at(isd.tair, W.scene_time(s)) for s in sc.scene_id]
    days = pd.date_range("2012-12-01", "2025-12-31")
    clim = pd.DataFrame({"date": days, "tair": [W.interp_at(isd.tair, pd.Timestamp(f"{d:%Y-%m-%d}T15:46", tz="UTC")) for d in days]})
    clim["season"] = clim.date.dt.month.map(SEASON_OF)
    clim["season_year"] = clim.date.dt.year + (clim.date.dt.month == 12)
    clim = clim[(clim.season_year >= 2013) & (clim.season_year <= 2025)]
    t_sy = clim.groupby(["season_year", "season"]).tair.mean()
    t_s = clim.groupby("season").tair.mean()
    b = {}
    for s_ in SEASONS:
        d = sc[(sc.season == s_) & sc.tair_C.notna()]
        b[s_] = smf.ols("lst_median ~ tair_C + year", data=d).fit().params.tair_C if len(d) >= 8 else np.nan
    sc["b"] = sc.season.map(b)
    sc["tair_ref_sy"] = [t_sy.get((y, s_), np.nan) for y, s_ in zip(sc.season_year, sc.season)]
    sc["tair_ref_s"] = sc.season.map(t_s)
    ok_w = sc.tair_C.notna().values & np.isfinite(sc.tair_ref_sy.values)
    adj1 = (sc.b * (sc.tair_C - sc.tair_ref_sy)).values
    adj2 = (sc.b * (sc.tair_C - sc.tair_ref_s)).values
    print("b by season:", {k: round(v, 3) for k, v in b.items()})
    versions = {
        "rel": st - sc.lst_median.values[:, None, None].astype("float32"),
        "C1": np.where(ok_w[:, None, None], st - adj1[:, None, None], np.nan).astype("float32"),
        "C2": np.where(ok_w[:, None, None], st - adj2[:, None, None], np.nan).astype("float32"),
    }

    # --- 1. per-pixel harmonic trends and seasonal trends
    pix = {}
    for v, stk in versions.items():
        h = harmonic_pixels(stk, X, sc.season_year.values)
        pix[v] = h
        L.write(OUT / f"{v}_harmonic_slope.tif", h["slope"], prof, city, [f"{v} de-seasonalized trend (C/yr)"])
        L.write(OUT / f"{v}_harmonic_p.tif", h["p"], prof, city, [f"{v} trend p"])
        if v == "rel":
            L.write(OUT / "rel_mean_yearround.tif", h["level"], prof, city, ["year-round mean relative LST (C)"])
    L.MIN_YEARS = MIN_SEASON_YEARS
    seas_maps = {}
    for s_ in SEASONS:
        sel = (sc.season == s_).values
        for v in ("rel", "C1"):
            ann = np.full((len(L.YEARS),) + shape, np.nan, "float32")
            for i, y in enumerate(L.YEARS):
                m = sel & (sc.season_year.values == y)
                if m.any():
                    ann[i] = np.nanmean(versions[v][m], 0)
            t = L.trends(ann)
            seas_maps[(s_, v)] = t["slope_ols"]
            L.write(OUT / f"{v}_{s_}_slope.tif", t["slope_ols"], prof, city, [f"{v} {s_} trend (C/yr)"])
            if v == "rel":
                mean_s = np.nanmean(versions["rel"][sel], 0)
                seas_maps[(s_, "mean")] = mean_s
                L.write(OUT / f"rel_mean_{s_}.tif", mean_s, prof, city, [f"mean relative LST {s_} (C)"])

    # --- 2. city trends
    sc["city_obs"] = sc.lst_median
    sc["city_C1"] = sc.lst_median - adj1
    sc["city_C2"] = sc.lst_median - adj2
    rows = []
    for v in ("city_obs", "city_C1", "city_C2"):
        rows.append({"version": v, "season": "ALL", **scene_trend(sc, v, True)})
        for s_ in SEASONS:
            d = sc[sc.season == s_]
            if d.season_year.nunique() >= MIN_SEASON_YEARS:
                rows.append({"version": v, "season": s_, **scene_trend(d, v, False)})
    city_tr = pd.DataFrame(rows)
    loyo = [scene_trend(sc[sc.season_year != y], "city_C1", True)["slope"] for y in sorted(sc.season_year.unique())]
    city_tr.to_csv(OUT / "city_trends.csv", index=False, float_format="%.4f")
    sc.drop(columns=["date"]).to_csv(OUT / "scenes_allyear.csv", index=False, float_format="%.3f")

    # --- 3. season comparison
    f = lambda g, y: read(CC / f"cc_frac_{g}_{y}_utm.tif")
    imp21 = f("structures", 2021) + f("roads", 2021) + f("other_imperv", 2021)
    hot, cool = city & (imp21 >= 80), city & (f("canopy", 2021) >= 70)
    sc["contrast"] = [np.nanmedian(st[i][hot]) - np.nanmedian(st[i][cool]) for i in range(len(sc))]
    groups = ["canopy", "structures", "roads", "other_imperv", "turf", "bare", "herb_shrub", "water"]
    bl = pd.DataFrame({g: block(f(g, 2021)).ravel() for g in groups})
    bh, bw = block(f("canopy", 2021)).shape
    r, c = np.divmod(np.arange(bh * bw), bw)
    bl["tile"] = (r // 11) * 1000 + (c // 11)
    comp = []
    for s_ in SEASONS + ["ALL"]:
        mean_map = pix["rel"]["level"] if s_ == "ALL" else seas_maps[(s_, "mean")]
        bl["y"] = block(np.where(city, mean_map, np.nan)).ravel()
        d = bl[(bl.water < 10)].dropna(subset=["y", "canopy"])
        fit = smf.ols(f"y ~ {COVER}", data=d).fit()
        row = {"season": s_, "contrast_C": sc.contrast.mean() if s_ == "ALL" else sc.loc[sc.season == s_, "contrast"].mean(),
               "r2_cover": fit.rsquared}
        for g in ("canopy", "structures", "roads", "other_imperv"):
            row[f"{g}_per10pp"] = fit.params[g] * 10
        comp.append(row)
    comp = pd.DataFrame(comp)
    comp.to_csv(OUT / "season_comparison.csv", index=False, float_format="%.4f")
    corr_mean = pd.DataFrame({s_: block(np.where(city, seas_maps[(s_, "mean")], np.nan)).ravel() for s_ in SEASONS}).corr()
    corr_trend = pd.DataFrame({s_: block(np.where(city, seas_maps[(s_, "rel")], np.nan)).ravel() for s_ in SEASONS}
                              | {"ALL": block(np.where(city, pix["rel"]["slope"], np.nan)).ravel(),
                                 "JJA_julaug_L8": block(read(L.OUT / "B_rel_slope_ols.tif")).ravel()}).corr()

    # --- 4. NSA harmonic trends
    nsa["nsa_id"] = np.arange(1, len(nsa) + 1)
    ids = rasterize(zip(nsa.geometry, nsa.nsa_id), out_shape=shape, transform=tr, fill=0, dtype="int32")
    ids = np.where(np.nan_to_num(read(CC / "cc_frac_water_2021_utm.tif")) >= 50, 0, ids)
    nrows = []
    for nid, name in zip(nsa.nsa_id, nsa.Name):
        m = ids == nid
        npx = int(m.sum())
        if npx == 0:
            continue
        rec = {"Name": name, "pixels": npx, "mean_rel_yr": np.nanmean(pix["rel"]["level"][m])}
        for v in ("rel", "C1"):
            vals = versions[v][:, m]
            cover = np.isfinite(vals).mean(1)
            d = sc[["t", "c1", "s1", "c2", "s2", "season_year"]].copy()
            d["y"] = np.where(cover >= 0.5, np.nanmean(vals, 1), np.nan)
            if d.y.notna().sum() >= MIN_SCENES:
                tr_ = scene_trend(d, "y", True)
                rec.update({f"{v}_trend": tr_["slope"], f"{v}_ci_lo": tr_["ci_lo"], f"{v}_ci_hi": tr_["ci_hi"], f"{v}_p": tr_["p"]})
                # stricter: de-seasonalized annual means (one value per season-year), OLS
                dd = d.dropna(subset=["y"])
                hm = smf.ols("y ~ t + c1 + s1 + c2 + s2", data=dd).fit().params
                dd = dd.assign(ds=dd.y - (dd[["c1", "s1", "c2", "s2"]] * hm[["c1", "s1", "c2", "s2"]].values).sum(axis=1))
                a_ = dd.groupby("season_year").ds.mean()
                ra = stats.linregress(a_.index.values.astype(float), a_.values)
                rec.update({f"{v}_trend_annual": ra.slope, f"{v}_p_annual": ra.pvalue})
        nrows.append(rec)
    nt = pd.DataFrame(nrows)
    for v in ("rel", "C1"):
        nt[f"{v}_q"] = N.bh_q(nt[f"{v}_p"])
        nt[f"{v}_q_annual"] = N.bh_q(nt[f"{v}_p_annual"])
    summer = pd.read_csv(ROOT / "data/processed/nsa/nsa_lst_lc08.csv")[["Name", "rel_trend", "c1_trend", "mean_rel"]]
    nt = nt.merge(summer.rename(columns={"rel_trend": "rel_trend_julaug", "c1_trend": "c1_trend_julaug", "mean_rel": "mean_rel_julaug"}),
                  on="Name", how="left")
    gnt = nsa[["Name", "Population", "geometry"]].merge(nt, on="Name")
    gnt.to_file(OUT / "nsa_lst_allyear_lc08.gpkg", layer="nsa_allyear", driver="GPKG")
    nt.to_csv(OUT / "nsa_lst_allyear_lc08.csv", index=False, float_format="%.4f")

    # --- 5. paving / cover change by season
    dimp = block(np.where(city, read(ROOT / "data/processed/landcover/nlcd_dimp_2013_2025_pp.tif"), np.nan)).ravel()
    ch = {g: block(f(g, 2021) - f(g, 2013)).ravel() for g in ("canopy", "turf", "bare", "herb_shrub")}
    d_imp_cc = block(imp21 - (f("structures", 2013) + f("roads", 2013) + f("other_imperv", 2013))).ravel()
    chdf = pd.DataFrame(ch)
    repl = chdf.fillna(-np.inf).idxmax(axis=1).where(chdf.notna().all(axis=1) & (d_imp_cc <= -5))
    pv = []
    trend_maps = {"ALL": pix["rel"]["slope"]} | {s_: seas_maps[(s_, "rel")] for s_ in SEASONS}
    for s_, mp in trend_maps.items():
        bt = block(np.where(city, mp, np.nan)).ravel()
        g = np.isfinite(bt) & np.isfinite(dimp) & (dimp >= 5)
        dd = pd.DataFrame({"y": bt[g], "x": dimp[g], "tile": bl.tile.values[g]})
        m = smf.ols("y ~ x", data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.tile})
        row = {"season": s_, "gain_effect_per10pp": m.params.x * 10, "ci_lo": m.conf_int().loc["x", 0] * 10,
               "ci_hi": m.conf_int().loc["x", 1] * 10, "p": m.pvalues.x, "blocks": int(m.nobs)}
        stable = np.isfinite(bt) & np.isfinite(d_imp_cc) & (np.abs(d_imp_cc) < 2)
        row["stable_median"] = np.nanmedian(bt[stable])
        for k in ("canopy", "turf", "bare", "herb_shrub"):
            sel = (repl == k).values & np.isfinite(bt)
            row[f"loss_to_{k}_median"] = np.nanmedian(bt[sel]) if sel.sum() >= 10 else np.nan
            row[f"loss_to_{k}_n"] = int(sel.sum())
        pv.append(row)
    pv = pd.DataFrame(pv)
    pv.to_csv(OUT / "paving_by_season.csv", index=False, float_format="%.4f")

    # --- print
    pd.set_option("display.width", 230)
    fmt = lambda x: f"{x:.3f}"
    print("\nCITY TRENDS (scene-level; year-clustered 95% CI):\n", city_tr.to_string(index=False, float_format=fmt))
    print(f"C1 year-round leave-one-year-out range: {min(loyo):+.3f} to {max(loyo):+.3f}")
    for v in ("rel", "C1", "C2"):
        s_, p_ = pix[v]["slope"][city], pix[v]["p"][city]
        ok = np.isfinite(s_) & np.isfinite(p_)
        print(f"pixels {v}: valid {ok.sum()}, median trend {np.nanmedian(s_):+.4f}, p<0.05 {100 * (p_[ok] < 0.05).mean():.1f}% "
              f"(warm {100 * ((p_[ok] < 0.05) & (s_[ok] > 0)).mean():.1f}%, cool {100 * ((p_[ok] < 0.05) & (s_[ok] < 0)).mean():.1f}%)")
    for v in ("rel", "C1", "C2"):
        pa_, sa_ = pix[v]["p_annual"][city], pix[v]["slope_annual"][city]
        ok = np.isfinite(pa_)
        print(f"pixels {v} (annual-mean test): p<0.05 {100 * (pa_[ok] < 0.05).mean():.1f}% "
              f"(warm {100 * ((pa_[ok] < 0.05) & (sa_[ok] > 0)).mean():.1f}%, cool {100 * ((pa_[ok] < 0.05) & (sa_[ok] < 0)).mean():.1f}%)")
    print("\nSEASON COMPARISON:\n", comp.to_string(index=False, float_format=fmt))
    print("\ncorrelation of mean relative LST maps (90 m):\n", corr_mean.round(2).to_string())
    print("\ncorrelation of relative trend maps (90 m):\n", corr_trend.round(2).to_string())
    v = nt[nt.pixels >= 100]
    print(f"\nNSA year-round: rel p<0.05 {int((v.rel_p < 0.05).sum())}, q<0.10 {int((v.rel_q < 0.10).sum())}; "
          f"C1 median {v.C1_trend.median():+.3f}, p<0.05 {int((v.C1_p < 0.05).sum())}, q<0.10 {int((v.C1_q < 0.10).sum())}; "
          f"Spearman year-round vs Jul-Aug: rel {stats.spearmanr(v.rel_trend, v.rel_trend_julaug, nan_policy='omit').statistic:+.2f}, "
          f"C1 {stats.spearmanr(v.C1_trend, v.c1_trend_julaug, nan_policy='omit').statistic:+.2f}, "
          f"mean {stats.spearmanr(v.mean_rel_yr, v.mean_rel_julaug, nan_policy='omit').statistic:+.2f}")
    print(f"NSA annual-mean test: rel p<0.05 {int((v.rel_p_annual < 0.05).sum())}, q<0.10 {int((v.rel_q_annual < 0.10).sum())}; "
          f"C1 p<0.05 {int((v.C1_p_annual < 0.05).sum())}, q<0.10 {int((v.C1_q_annual < 0.10).sum())}")
    print(v.sort_values("rel_trend")[["Name", "rel_trend", "rel_p", "rel_q", "rel_p_annual", "rel_q_annual", "C1_trend"]].head(6).to_string(index=False, float_format=fmt))
    print(v.sort_values("rel_trend")[["Name", "rel_trend", "rel_p", "rel_q", "rel_p_annual", "rel_q_annual", "C1_trend"]].tail(6).to_string(index=False, float_format=fmt))
    print("\nPAVING BY SEASON:\n", pv.to_string(index=False, float_format=fmt))

    # --- figures
    labs = ["ALL"] + SEASONS
    fig, ax = plt.subplots(figsize=(12, 7.5))
    for k, (v, colr, mk, lab) in enumerate([("city_obs", "#d73027", "o", "Observed"), ("city_C1", "#fc8d59", "s", "C1: sampling removed"),
                                            ("city_C2", "#4575b4", "D", "C2: surface only")]):
        dd = city_tr[city_tr.version == v].set_index("season").reindex(labs)
        xs = np.arange(len(labs)) + (k - 1) * 0.22
        ax.errorbar(xs, dd.slope, yerr=[dd.slope - dd.ci_lo, dd.ci_hi - dd.slope], fmt=mk, ms=9, color=colr, capsize=4, lw=1.6, label=lab)
    style(ax)
    ax.set_xticks(range(len(labs)), [f"{SEASON_LABEL[l]}\n({city_tr[(city_tr.version == 'city_C1') & (city_tr.season == l)].n_scenes.iloc[0] if l in city_tr.season.values else 0} scenes)" for l in labs], fontsize=15)
    ax.set(ylabel="City LST trend (°C/yr)", title="Citywide LST trend by season, 2013–2025")
    ax.legend(fontsize=14, frameon=False, loc="upper left")
    fig.text(0.99, 0.01, f"Landsat 8, scenes ≥ 50% clear; scene city medians; 95% CI clustered by season-year. Year-round: de-seasonalized (harmonic) trend.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "city_trend_by_season.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(17, 7))
    xs = np.arange(len(labs))
    cc_ = comp.set_index("season").reindex(labs)
    for k, (g, colr, lab) in enumerate([("structures", "#b2182b", "Roofs"), ("roads", "#4d4d4d", "Roads"),
                                        ("other_imperv", "#9a9a9a", "Other pavement"), ("canopy", "#1b7837", "Tree canopy")]):
        ax[0].bar(xs + (k - 1.5) * 0.2, cc_[f"{g}_per10pp"], width=0.19, color=colr, label=lab)
    style(ax[0])
    ax[0].set_xticks(xs, [SEASON_LABEL[l].split(" ")[0] if l != "ALL" else "Year" for l in labs], fontsize=16)
    ax[0].set(ylabel="Relative LST per 10 pp replacing turf (°C)", title="What drives the heat pattern")
    ax[0].legend(fontsize=13, frameon=False, ncol=2, loc="lower left")
    pvv = pv.set_index("season").reindex(labs)
    ax[1].errorbar(xs, pvv.gain_effect_per10pp, yerr=[pvv.gain_effect_per10pp - pvv.ci_lo, pvv.ci_hi - pvv.gain_effect_per10pp],
                   fmt="o", ms=10, color="#b2182b", capsize=5, lw=1.8)
    style(ax[1])
    ax[1].set_xticks(xs, [SEASON_LABEL[l].split(" ")[0] if l != "ALL" else "Year" for l in labs], fontsize=16)
    ax[1].set(ylabel="Relative trend per 10 pp impervious gained (°C/yr)", title="Paving effect by season")
    fig.text(0.99, 0.01, f"Left: OLS on 90 m blocks of mean relative LST vs CC 2021/22 cover. Right: blocks with NLCD impervious gain ≥ 5 pp; 95% CI clustered by 1 km tile.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "season_drivers_and_paving.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
