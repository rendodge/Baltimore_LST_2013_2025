"""Variant C: summer LST normalized to BWI air temperature at overpass time.

Uses the variant-B scene set (>= 50% of city clear). For each scene, air temperature at the
scene-centre time is interpolated from BWI METAR (ISD FM-15) observations. A citywide
sensitivity b (deg C LST per deg C air) is fitted on scene city-median LST with a year term,
so a genuine trend is not absorbed into b:  LST_med ~ a + b * T_air + c * year.

  C1 "sampling removed, climate kept":  LST - b * (T_air,scene - T_air,summer(year))
  C2 "surface only":                    LST - b * (T_air,scene - T_air,ref)
where T_air,summer(year) is the mean air temperature at the same UTC time over all Jul-Aug
days of that year, and T_air,ref is its 2013-2025 mean.

City decomposition (fixed common pixels): observed trend = climate + sampling + surface, with
  climate  = b * trend(T_air,summer),  sampling = b * (trend(T_air,overpass) - trend(T_air,summer)),
  surface  = trend(C2).
Outputs in data/processed/lst_trend/ (C_*.tif, C_scene_weather.csv, C_city_*.csv/json/png).
Run: conda run -p .\\env python scripts\\04_lst_bwi_normalized.py
"""
import importlib.util
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask
from scipy import stats
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lst", ROOT / "scripts/02_lst_trend.py")
lst_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lst_mod)
YEARS, MIN_CLEAR, OUT = lst_mod.YEARS, lst_mod.MIN_CLEAR, lst_mod.OUT
NOAA = ROOT / "data/raw/noaa"
GOOD_QC = set("01459")


def parse_isd():
    """BWI METAR (FM-15) air temperature (C) and wind speed (m/s), UTC-indexed."""
    frames = []
    for y in YEARS:
        d = pd.read_csv(NOAA / f"isd_72406093721_{y}.csv", usecols=["DATE", "REPORT_TYPE", "TMP", "WND"],
                        dtype=str)
        d = d[d.REPORT_TYPE.str.strip() == "FM-15"]
        t = d.TMP.str.split(",", expand=True)
        w = d.WND.str.split(",", expand=True)
        out = pd.DataFrame({"time": pd.to_datetime(d.DATE, utc=True),
                            "tair": pd.to_numeric(t[0], errors="coerce") / 10.0,
                            "wind": pd.to_numeric(w[3], errors="coerce") / 10.0})
        out.loc[(t[0] == "+9999") | ~t[1].isin(GOOD_QC), "tair"] = np.nan
        out.loc[(w[3] == "9999") | ~w[4].isin(GOOD_QC), "wind"] = np.nan
        frames.append(out)
    return pd.concat(frames).set_index("time").sort_index()


def interp_at(series, when, max_gap_h=1.5):
    """Linear interpolation of a time series at `when`, if bracketing obs are within max_gap_h."""
    s = series.dropna()
    i = s.index.searchsorted(when)
    if i == 0 or i == len(s):
        return np.nan
    t0, t1 = s.index[i - 1], s.index[i]
    if (when - t0).total_seconds() > max_gap_h * 3600 or (t1 - when).total_seconds() > max_gap_h * 3600:
        return np.nan
    f = (when - t0) / (t1 - t0)
    return s.iloc[i - 1] + f * (s.iloc[i] - s.iloc[i - 1])


def scene_time(sid):
    mtl = (lst_mod.RAW / sid / f"{sid}_MTL.txt").read_text()
    get = lambda k: mtl.split(f"{k} = ")[1].split("\n")[0].strip().strip('"')
    return pd.Timestamp(f"{get('DATE_ACQUIRED')}T{get('SCENE_CENTER_TIME')[:8]}", tz="UTC")


def main():
    with rasterio.open(next(lst_mod.RAW.glob("LC08_*/*_ST_B10_subset.tif"))) as s:
        tr, shape = s.transform, s.shape
    nsa = gpd.read_file(lst_mod.NSA).to_crs(32618)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
    scenes, lst, profile = lst_mod.load_scenes(city, lst_mod.SENSORS)
    scenes["used_B"] = scenes.clear_frac_city >= MIN_CLEAR

    # --- weather at overpass
    isd = parse_isd()
    prcp = pd.read_csv(NOAA / "ghcnd_USW00093721.csv", usecols=["DATE", "PRCP"], parse_dates=["DATE"],
                       low_memory=False).set_index("DATE").PRCP / 10.0  # tenths mm -> mm
    scenes["time_utc"] = [scene_time(s) for s in scenes.scene_id]
    scenes["tair_C"] = [interp_at(isd.tair, t) for t in scenes.time_utc]
    scenes["wind_ms"] = [interp_at(isd.wind, t) for t in scenes.time_utc]
    scenes["prcp_prev3d_mm"] = [prcp.reindex(pd.date_range(t.normalize().tz_localize(None) - pd.Timedelta(days=3),
                                                           periods=3)).sum(min_count=3) for t in scenes.time_utc]
    hhmm = scenes.time_utc.dt.hour.mean() + scenes.time_utc.dt.minute.mean() / 60  # mean overpass time
    h, m = int(hhmm), int(round((hhmm % 1) * 60))
    summer_days = [pd.Timestamp(f"{d:%Y-%m-%d}T{h:02d}:{m:02d}", tz="UTC")
                   for y in YEARS for d in pd.date_range(f"{y}-07-01", f"{y}-08-31")]
    summer = pd.DataFrame({"time": summer_days, "tair": [interp_at(isd.tair, t) for t in summer_days]})
    summer["year"] = summer.time.dt.year
    ta_summer = summer.groupby("year").tair.mean()
    ta_summer_n = summer.groupby("year").tair.count()
    ta_ref = ta_summer.mean()

    # --- sensitivity b on variant-B scenes
    sb = scenes[scenes.used_B & scenes.tair_C.notna()].copy()
    sensor_term = " + C(sensor)" if sb.sensor.nunique() > 1 else ""  # L8/L9 offset, if both present
    fit = smf.ols("lst_median ~ tair_C + year" + sensor_term, data=sb).fit()
    b = fit.params["tair_C"]
    fit_x = smf.ols("lst_median ~ tair_C + year + wind_ms + prcp_prev3d_mm" + sensor_term, data=sb).fit()
    print(fit.summary().tables[1])
    print("with wind/precip:\n", fit_x.summary().tables[1])

    scenes["tair_summer_C"] = scenes.year.map(ta_summer)
    scenes.drop(columns=["date"]).to_csv(OUT / "C_scene_weather.csv", index=False, float_format="%.3f")

    # --- normalized scene stacks (variant-B scenes with air temperature)
    use = (scenes.used_B & scenes.tair_C.notna()).values
    yrs = scenes.year.values[use]
    d1 = (scenes.tair_C - scenes.tair_summer_C).values[use].astype("float32")
    d2 = (scenes.tair_C - ta_ref).values[use].astype("float32")
    c1 = lst[use] - b * d1[:, None, None]
    c2 = lst[use] - b * d2[:, None, None]
    ann_obs = lst_mod.annual_mean(lst[use], yrs)
    ann1, ann2 = lst_mod.annual_mean(c1, yrs), lst_mod.annual_mean(c2, yrs)
    tr1, tr2 = lst_mod.trends(ann1), lst_mod.trends(ann2)

    w, yb = lst_mod.write, [str(y) for y in YEARS]
    w(OUT / "C1_annual_lst_C.tif", ann1, profile, city, yb)
    w(OUT / "C2_annual_lst_C.tif", ann2, profile, city, yb)
    for name, t in [("C1", tr1), ("C2", tr2)]:
        for k in ("slope_ols", "p_ols", "slope_sen", "p_mk", "n_years"):
            w(OUT / f"{name}_{k}.tif", t[k], profile, city, [f"{name} {k}"])

    # --- city decomposition on fixed common pixels
    yrB = [i for i, y in enumerate(YEARS) if np.isfinite(ann_obs[i][city]).any()]
    common = np.isfinite(ann_obs[yrB]).all(0) & city
    ts = pd.DataFrame({"year": YEARS})
    ts["n_scenes"] = [int((yrs == y).sum()) for y in YEARS]
    ts["obs_C"] = [np.nanmean(ann_obs[i][common]) if i in yrB else np.nan for i in range(len(YEARS))]
    ts["C1_C"] = [np.nanmean(ann1[i][common]) if i in yrB else np.nan for i in range(len(YEARS))]
    ts["C2_C"] = [np.nanmean(ann2[i][common]) if i in yrB else np.nan for i in range(len(YEARS))]
    ts["tair_overpass_C"] = [scenes.tair_C.values[use][yrs == y].mean() if (yrs == y).any() else np.nan
                             for y in YEARS]
    ts["tair_summer_C"] = ta_summer.reindex(YEARS).values
    ts["tair_summer_n_days"] = ta_summer_n.reindex(YEARS).values
    ts.to_csv(OUT / "C_city_timeseries.csv", index=False, float_format="%.3f")

    v = ts.dropna(subset=["obs_C"])
    lr = lambda col, d=v: stats.linregress(d.year, d[col])
    r_obs, r_c1, r_c2 = lr("obs_C"), lr("C1_C"), lr("C2_C")
    r_tov, r_tsu = lr("tair_overpass_C"), lr("tair_summer_C")
    r_tsu_all = lr("tair_summer_C", ts.dropna(subset=["tair_summer_C"]))
    dec = {
        "b_lst_per_C_air": b, "b_95ci": fit.conf_int().loc["tair_C"].tolist(), "b_fit_r2": fit.rsquared,
        "b_fit_n_scenes": int(fit.nobs), "year_coef_C_per_yr": fit.params["year"],
        "year_coef_p": fit.pvalues["year"], "overpass_utc": f"{h:02d}:{m:02d}", "tair_ref_C": ta_ref,
        "years_used": v.year.tolist(), "common_pixels": int(common.sum()),
        "trend_observed": [r_obs.slope, r_obs.pvalue],
        "trend_tair_overpass_days": [r_tov.slope, r_tov.pvalue],
        "trend_tair_all_summer_days_same_years": [r_tsu.slope, r_tsu.pvalue],
        "trend_tair_all_summer_days_2013_2025": [r_tsu_all.slope, r_tsu_all.pvalue],
        "component_climate": b * r_tsu.slope,
        "component_sampling": b * (r_tov.slope - r_tsu.slope),
        "component_surface_C2": [r_c2.slope, r_c2.pvalue, r_c2.stderr],
        "trend_C1_climate_plus_surface": [r_c1.slope, r_c1.pvalue, r_c1.stderr],
        "check_sum": b * r_tsu.slope + b * (r_tov.slope - r_tsu.slope) + r_c2.slope,
    }
    for name, t in [("C1", tr1), ("C2", tr2)]:
        s, p = t["slope_ols"][city], t["p_ols"][city]
        ok = np.isfinite(s)
        dec[f"pixels_{name}"] = {"median": float(np.nanmedian(s)),
                                 "p05_p95": [float(q) for q in np.nanpercentile(s, [5, 95])],
                                 "frac_p_lt_0.05_pos": float(((p[ok] < 0.05) & (s[ok] > 0)).mean()),
                                 "frac_p_lt_0.05_neg": float(((p[ok] < 0.05) & (s[ok] < 0)).mean())}
    (OUT / "C_city_decomposition.json").write_text(json.dumps(dec, indent=1, default=float))
    print(json.dumps(dec, indent=1, default=float))
    print(ts.to_string(index=False, float_format=lambda x: f"{x:.2f}"))

    # --- preview figure
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    sc = ax[0].scatter(sb.tair_C, sb.lst_median, c=sb.year, cmap="viridis")
    xx = np.linspace(sb.tair_C.min(), sb.tair_C.max(), 10)
    ax[0].plot(xx, fit.params["Intercept"] + b * xx + fit.params["year"] * sb.year.mean(), "k--", lw=1)
    ax[0].set(xlabel="BWI air temperature at overpass (°C)", ylabel="City median LST (°C)",
              title=f"Scene LST vs air temperature (b = {b:.2f}, n = {int(fit.nobs)})")
    fig.colorbar(sc, ax=ax[0], label="Year")
    for col, lab, c in [("obs_C", "Observed (absolute, B)", "#d73027"), ("C1_C", "C1: sampling removed", "#fc8d59"),
                        ("C2_C", "C2: surface only", "#4575b4")]:
        r = lr(col)
        ax[1].plot(v.year, v[col], "o-", color=c, label=f"{lab}: {r.slope:+.2f} °C/yr (p={r.pvalue:.2f})")
    ax[1].set(xlabel="Year", ylabel="Mean LST, common pixels (°C)", title="City mean July–August LST")
    ax[1].legend(fontsize=8, frameon=False)
    ax[1].set_xticks(YEARS[::2])
    comps = [("Climate", dec["component_climate"]), ("Sampling", dec["component_sampling"]),
             ("Surface", r_c2.slope), ("Observed", r_obs.slope)]
    ax[2].bar([c[0] for c in comps], [c[1] for c in comps], color=["#fc8d59", "#bdbdbd", "#4575b4", "#d73027"])
    ax[2].errorbar(["Surface", "Observed"], [r_c2.slope, r_obs.slope], yerr=[1.96 * r_c2.stderr, 1.96 * r_obs.stderr],
                   fmt="none", ecolor="k", capsize=4)
    ax[2].axhline(0, color="k", lw=0.6)
    ax[2].set(ylabel="Trend (°C/yr)", title="Decomposition of city LST trend")
    fig.text(0.99, 0.01, "Landsat imagery courtesy of the U.S. Geological Survey; air temperature: NOAA ISD (KBWI)",
             ha="right", fontsize=7, color="0.4")
    fig.tight_layout()
    fig.savefig(OUT / "C_city_decomposition_preview.png", dpi=150)


if __name__ == "__main__":
    main()
