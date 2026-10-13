"""Buffer-width deep dive: robustness, mechanism, threshold, and planning translation.

Input: data/processed/streams/buffer_points_v2.csv (29_buffer_points.py).
Width = distance from the channel to the outer edge of the last band such that every band from
the channel outward has >= THR canopy (default 50%); "pool" pools both banks (a per-side distance),
L / R are the two banks; "narrow" / "wide" bank = min / max of L, R.
Outcomes: corridor = mean relative LST 0-60 m from the channel; neighbourhood = 90-210 m;
background = 480-630 m. Reference width class: >= 200 m per side.

Models (OLS, SEs clustered by 1 km tile):
  M1  width class + impervious 300-600 m
  M2  M1 + canopy 300-600, canopy/impervious 600-1000, terrain (elev, slope, TPI300/1000,
      illumination), stream order, log channel width, log distance to harbour
  M3  M2 + 1 km tile fixed effects (within-neighbourhood comparison); M3b 500 m tiles
  M4  M2 + forest continuity (+-500 m along the network)
Also: per-bank (narrow + wide bank classes); seasonal falsification (DJF/MAM/JJA/SON mean relative
LST); spline and hinge with tile-bootstrap CI; canopy threshold 40/60/70%; 300 m spacing;
cooling-distance profiles and residents within the cooled zone; canopy change 2013/14-2021/22 in the
buffer vs relative LST trends; priority reaches.

Outputs: data/processed/streams/deepdive_*.csv, deepdive_priority_points.gpkg,
figures/buffer_deepdive/*.png. Run: conda run -p .\\env python scripts\\30_buffer_analysis.py
"""
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data/processed/streams/buffer_points_v2.csv"
OUT = ROOT / "data/processed/streams"
FIG = ROOT / "figures/buffer_deepdive"
BANDS = [0, 10, 20, 30, 50, 75, 100, 150, 200, 300]
PROFILE = np.arange(0, 630, 30)
WBINS = [-1, 9, 29, 49, 99, 199, 1000]
WLAB = ["<10", "10-30", "30-50", "50-100", "100-200", "≥200"]
REF = "≥200"
CTRL2 = ("imp_300_600 + can_300_600 + imp_600_1000 + can_600_1000 + elev + slope + tpi300 + tpi1000 + illum"
         " + C(order_cls) + np.log1p(chan_width) + np.log1p(dist_harbour)")
N_BOOT, SEED = 500, 42
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey; land cover and streams: Chesapeake Conservancy / UMBC; USGS 3DEP"
warnings.filterwarnings("ignore")
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def width(d, yr, lab, thr):
    w = np.zeros(len(d))
    ok = np.ones(len(d), bool)
    for lo, hi in zip(BANDS[:-1], BANDS[1:]):
        f = d[f"can{yr}_{lab}_{lo}_{hi}"].values
        good = ok & np.isfinite(f) & (f >= thr)
        w = np.where(good, hi, w)
        ok = good
    return w


def prep(d, thr=0.5):
    d = d.copy()
    for lab in ("pool", "L", "R"):
        d[f"w_{lab}"] = width(d, 2021, lab, thr)
    d["w_narrow"], d["w_wide"] = d[["w_L", "w_R"]].min(axis=1), d[["w_L", "w_R"]].max(axis=1)
    for k in ("pool", "narrow", "wide"):
        d[f"cls_{k}"] = pd.cut(d[f"w_{k}"], WBINS, labels=WLAB).astype(str)
    d["order_cls"] = pd.cut(d.order, [0, 1, 2, 3, 10], labels=["1", "2", "3", "4+"]).astype(str)
    for k in ("jja_julaug", "DJF", "MAM", "JJA", "SON", "trend_summer", "trend_yr"):
        d[f"{k}_corr"] = d[[f"{k}_p0", f"{k}_p30"]].mean(axis=1)
        d[f"{k}_nbhd"] = d[[f"{k}_p{a}" for a in (90, 120, 150, 180)]].mean(axis=1)
        d[f"{k}_bg"] = d[[f"{k}_p{a}" for a in (480, 510, 540, 570, 600)]].mean(axis=1)
    return d


def fit(d, y, rhs, cls="cls_pool", label=""):
    dd = d.dropna(subset=[y]).copy()
    f = smf.ols(f"{y} ~ C({cls}, Treatment('{REF}')) + {rhs}" if rhs else f"{y} ~ C({cls}, Treatment('{REF}'))",
                data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.tile})
    rows = []
    for lab in WLAB:
        t = f"C({cls}, Treatment('{REF}'))[T.{lab}]"
        if t in f.params:
            ci = f.conf_int().loc[t]
            rows.append({"model": label, "outcome": y, "class": lab, "n": int((dd[cls] == lab).sum()),
                         "coef_C": f.params[t], "ci_lo": ci[0], "ci_hi": ci[1], "p": f.pvalues[t]})
    rows.append({"model": label, "outcome": y, "class": REF, "n": int((dd[cls] == REF).sum()),
                 "coef_C": 0.0, "ci_lo": 0.0, "ci_hi": 0.0, "p": np.nan})
    return pd.DataFrame(rows), f


def style(ax):
    ax.grid(axis="y", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.axhline(0, color="0.45", lw=1.2, ls="--")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(IN)
    d = prep(raw)
    print(f"points {len(d)}; per-side width classes (pooled):", d.cls_pool.value_counts().reindex(WLAB).to_dict())
    pts_per_reach = d.groupby("reach").size()
    print(f"reaches {len(pts_per_reach)}, with >= 2 points: {(pts_per_reach >= 2).sum()} ({pts_per_reach[pts_per_reach >= 2].sum()} points)")

    # --- A. robustness of the main effect (corridor, Jul-Aug)
    y = "jja_julaug_corr"
    res = []
    specs = [("M1 context impervious", "imp_300_600"), ("M2 rich controls", CTRL2),
             ("M3 + 1 km tile FE", CTRL2 + " + C(tile)"), ("M3b + 500 m tile FE", CTRL2 + " + C(tile500)"),
             ("M4 + continuity", CTRL2 + " + continuity_can")]
    for lab, rhs in specs:
        r, f = fit(d, y, rhs, label=lab)
        res.append(r)
        if lab.startswith("M4"):
            cont = (f.params["continuity_can"] * 0.1, f.pvalues["continuity_can"])
    multi = d[d.reach.isin(pts_per_reach[pts_per_reach >= 2].index)]
    r, _ = fit(multi, y, CTRL2 + " + C(reach)", label="M5 within-reach FE")
    res.append(r)
    for nb, lab in (("neighbourhood", "nbhd"),):
        r, _ = fit(d, f"jja_julaug_{lab}", CTRL2, label="M2 neighbourhood 90-210 m")
        res.append(r)
    # per-bank
    dd = d.dropna(subset=[y])
    fb = smf.ols(f"{y} ~ C(cls_narrow, Treatment('{REF}')) + C(cls_wide, Treatment('{REF}')) + {CTRL2}", data=dd).fit(
        cov_type="cluster", cov_kwds={"groups": dd.tile})
    bank = []
    for side in ("narrow", "wide"):
        for lab in WLAB[:-1]:
            t = f"C(cls_{side}, Treatment('{REF}'))[T.{lab}]"
            if t in fb.params:
                bank.append({"bank": side, "class": lab, "n": int((dd[f"cls_{side}"] == lab).sum()), "coef_C": fb.params[t],
                             "ci_lo": fb.conf_int().loc[t, 0], "ci_hi": fb.conf_int().loc[t, 1], "p": fb.pvalues[t]})
    bank = pd.DataFrame(bank)
    # sensitivity: threshold and spacing
    for thr in (0.4, 0.6, 0.7):
        r, _ = fit(prep(raw, thr), y, CTRL2, label=f"M2 canopy threshold {int(thr * 100)}%")
        res.append(r)
    d["k"] = d.groupby("reach").cumcount()
    r, _ = fit(d[d.k % 2 == 0], y, CTRL2, label="M2 300 m spacing")
    res.append(r)
    rob = pd.concat(res)
    rob.to_csv(OUT / "deepdive_robustness.csv", index=False, float_format="%.4f")
    bank.to_csv(OUT / "deepdive_per_bank.csv", index=False, float_format="%.4f")

    # --- B. seasonal falsification
    seas = pd.concat([fit(d, f"{s}_corr", CTRL2, label=s)[0] for s in ("DJF", "MAM", "JJA", "SON")])
    seas.to_csv(OUT / "deepdive_seasonal.csv", index=False, float_format="%.4f")

    # --- C. continuous: spline with CI and hinge with tile-bootstrap CI
    dd = d.dropna(subset=[y] + [c.strip() for c in ["imp_300_600", "can_300_600", "imp_600_1000", "can_600_1000", "elev", "slope",
                                                       "tpi300", "tpi1000", "illum", "chan_width", "dist_harbour"]]).copy()
    sp = smf.ols(f"{y} ~ cr(w_pool, df=4) + {CTRL2}", data=dd).fit(cov_type="cluster", cov_kwds={"groups": dd.tile})
    grid = pd.DataFrame({"w_pool": np.arange(0, 301, 5)})
    for c in dd.columns:
        if c not in grid and c != y and pd.api.types.is_numeric_dtype(dd[c]):
            grid[c] = dd[c].median()
    grid["order_cls"] = dd.order_cls.mode()[0]
    pr = sp.get_prediction(grid).summary_frame()
    base = pr["mean"].iloc[-1]
    curve = pd.DataFrame({"w": grid.w_pool, "fit": pr["mean"] - base, "lo": pr["mean_ci_lower"] - base, "hi": pr["mean_ci_upper"] - base})
    curve.to_csv(OUT / "deepdive_spline.csv", index=False, float_format="%.4f")

    def hinge(df):
        best = None
        for h in range(10, 210, 10):
            df = df.assign(w1=df.w_pool.clip(upper=h), w2=(df.w_pool - h).clip(lower=0))
            m = smf.ols(f"{y} ~ w1 + w2 + {CTRL2}", data=df).fit()
            if best is None or m.ssr < best[1]:
                best = (h, m.ssr, m.params.w1 * 10, m.params.w2 * 10)
        return best
    h0 = hinge(dd)
    rng = np.random.default_rng(SEED)
    tiles = dd.tile.unique()
    byt = {t: np.flatnonzero(dd.tile.values == t) for t in tiles}
    boots = []
    for _ in range(N_BOOT):
        idx = np.concatenate([byt[t] for t in rng.choice(tiles, len(tiles), replace=True)])
        try:
            boots.append(hinge(dd.iloc[idx].reset_index(drop=True))[::2])
        except Exception:
            continue
    boots = pd.DataFrame(boots, columns=["hinge_m", "slope_below_per10m"])
    hinge_tab = pd.Series({"hinge_m": h0[0], "slope_below_per10m": h0[2], "slope_above_per10m": h0[3],
                           "hinge_ci_lo": boots.hinge_m.quantile(0.025), "hinge_ci_hi": boots.hinge_m.quantile(0.975),
                           "slope_ci_lo": boots.slope_below_per10m.quantile(0.025), "slope_ci_hi": boots.slope_below_per10m.quantile(0.975),
                           "n_boot": len(boots)})
    hinge_tab.to_csv(OUT / "deepdive_hinge.csv")

    # --- E1. cooling-distance profiles and residents in the cooled zone
    cols = [f"jja_julaug_p{a}" for a in PROFILE]
    exc = d[cols].values - d[[f"jja_julaug_p{a}" for a in (480, 510, 540, 570, 600)]].mean(axis=1).values[:, None]
    prof_rows, extent = [], {}
    for lab in WLAB:
        m = (d.cls_pool == lab).values
        med = np.nanmedian(exc[m], 0)
        for a, v in zip(PROFILE, med):
            prof_rows.append({"class": lab, "dist_m": a + 15, "excess_C": v})
        within = np.flatnonzero(med >= -0.5)
        ext = PROFILE[within[0]] if len(within) else np.nan
        extent[lab] = ext
    prof = pd.DataFrame(prof_rows)
    prof.to_csv(OUT / "deepdive_cooling_profiles.csv", index=False, float_format="%.4f")
    pop = []
    for lab in WLAB:
        m = d.cls_pool == lab
        e = extent[lab] if np.isfinite(extent[lab]) else 0
        # each point represents 150 m of channel; cooled zone = both sides from the channel out to the extent
        area_km2 = 2 * e * 150 / 1e6
        people = (d.loc[m, "pop_density"].fillna(0) * area_km2).sum()
        pop.append({"class": lab, "points": int(m.sum()), "channel_km": m.sum() * 0.15, "cooling_extent_m": e,
                    "residents_in_cooled_zone": people, "residents_per_km": people / max(m.sum() * 0.15, 1e-9),
                    "median_pop_density": d.loc[m, "pop_density"].median()})
    pop = pd.DataFrame(pop)
    pop.to_csv(OUT / "deepdive_cooling_population.csv", index=False, float_format="%.2f")

    # --- E2. canopy change in the buffer vs relative LST trends
    for lab in ("0_50", "0_100"):
        hi = int(lab.split("_")[1])
        bands = [(lo, h) for lo, h in zip(BANDS[:-1], BANDS[1:]) if h <= hi]
        wts = np.array([h - lo for lo, h in bands], float)
        for yr in (2013, 2021):
            v = np.column_stack([d[f"can{yr}_pool_{lo}_{h}"] for lo, h in bands])
            d[f"bufcan{yr}_{lab}"] = np.nansum(v * wts, 1) / np.nansum(np.isfinite(v) * wts, 1)
        d[f"dbufcan_{lab}"] = 100 * (d[f"bufcan2021_{lab}"] - d[f"bufcan2013_{lab}"])
    chg = []
    for yv in ("trend_summer_corr", "trend_yr_corr"):
        for lab in ("0_50", "0_100"):
            for rhs, mlab in ((CTRL2, "M2"), (CTRL2 + " + C(tile)", "M3 tile FE")):
                dd2 = d.dropna(subset=[yv, f"dbufcan_{lab}"])
                m = smf.ols(f"{yv} ~ I(dbufcan_{lab} / 10) + {rhs}", data=dd2).fit(cov_type="cluster", cov_kwds={"groups": dd2.tile})
                t = f"I(dbufcan_{lab} / 10)"
                chg.append({"trend": yv, "buffer": lab, "model": mlab, "coef_C_per_yr_per_10pp": m.params[t],
                            "ci_lo": m.conf_int().loc[t, 0], "ci_hi": m.conf_int().loc[t, 1], "p": m.pvalues[t], "n": int(m.nobs),
                            "sd_change_pp": dd2[f"dbufcan_{lab}"].std()})
    chg = pd.DataFrame(chg)
    chg.to_csv(OUT / "deepdive_canopy_change.csv", index=False, float_format="%.4f")

    # --- E3. priority reaches: narrow buffers (< 50 m per side) with hot surroundings and residents nearby
    gain = rob[(rob.model == "M2 rich controls")].set_index("class").coef_C
    d["expected_cooling_C"] = (gain.reindex(d.cls_pool).values - gain.get("50-100", np.nan)).clip(min=0)
    d["priority"] = (d.w_pool < 50) & (d.jja_julaug_bg > d.jja_julaug_bg.median())
    d["priority_score"] = np.where(d.priority, d.expected_cooling_C * d.pop_density.fillna(0) / 1000, np.nan)
    gp = gpd.GeoDataFrame(d[["reach", "nsa", "w_pool", "w_narrow", "w_wide", "cls_pool", "jja_julaug_corr", "jja_julaug_bg",
                             "pop_density", "expected_cooling_C", "priority", "priority_score"]],
                          geometry=gpd.points_from_xy(d.x, d.y), crs=32618)
    gp.to_file(OUT / "deepdive_priority_points.gpkg", layer="buffer_points", driver="GPKG")
    top = gp[gp.priority].groupby("nsa").agg(points=("reach", "size"), channel_km=("reach", lambda s: len(s) * 0.15),
                                             median_width=("w_pool", "median"), expected_cooling=("expected_cooling_C", "median"),
                                             density=("pop_density", "median"), score=("priority_score", "sum")).sort_values("score", ascending=False)
    top.to_csv(OUT / "deepdive_priority_nsas.csv", float_format="%.2f")

    # --- print
    pd.set_option("display.width", 230)
    fmt = lambda v: f"{v:.3f}"
    print("\nROBUSTNESS (corridor Jul-Aug LST vs >= 200 m per side):\n",
          rob.pivot_table(index="model", columns="class", values="coef_C", sort=False).reindex(columns=WLAB).round(2).to_string())
    key = rob[rob["class"].isin(["10-30", "30-50", "50-100"])][["model", "class", "coef_C", "ci_lo", "ci_hi", "p", "n"]]
    print(key.to_string(index=False, float_format=fmt))
    print(f"continuity: {cont[0]:+.3f} C per +10 pp along-stream canopy (p {cont[1]:.3f})")
    print("\nPER BANK:\n", bank.to_string(index=False, float_format=fmt))
    print("\nSEASONAL (corridor seasonal mean relative LST):\n",
          seas.pivot_table(index="model", columns="class", values="coef_C", sort=False).reindex(columns=WLAB).round(2).to_string())
    print("\nHINGE:\n", hinge_tab.round(3).to_string())
    print("\nCOOLING EXTENT AND RESIDENTS:\n", pop.to_string(index=False, float_format=lambda v: f"{v:.1f}"))
    print("\nCANOPY CHANGE vs TRENDS:\n", chg.to_string(index=False, float_format=fmt))
    print("\nPRIORITY NSAs (top 12):\n", top.head(12).to_string(float_format=lambda v: f"{v:.2f}"))

    # --- figures
    fig, ax = plt.subplots(1, 2, figsize=(18, 7))
    ax[0].fill_between(curve.w, curve.lo, curve.hi, color="#3a6ea5", alpha=0.2, lw=0)
    ax[0].plot(curve.w, curve.fit, color="#1d3f6e", lw=2.5)
    ax[0].axvline(hinge_tab.hinge_m, color="#b2182b", lw=1.5, ls="--")
    ax[0].axvspan(hinge_tab.hinge_ci_lo, hinge_tab.hinge_ci_hi, color="#b2182b", alpha=0.08)
    style(ax[0])
    ax[0].set(xlabel="Forested buffer width, per side (m)", ylabel="Corridor LST vs 300 m buffer (°C)",
              title="Smooth fit with 95% CI; hinge (red) with bootstrap CI")
    ax[0].set_xlim(0, 300)
    sea_cols = {"DJF": "#4575b4", "MAM": "#91bfdb", "JJA": "#d73027", "SON": "#fc8d59"}
    x = np.arange(len(WLAB))
    for k, (s_, colr) in enumerate(sea_cols.items()):
        t = seas[seas.model == s_].set_index("class").reindex(WLAB)
        ax[1].errorbar(x + (k - 1.5) * 0.15, t.coef_C, yerr=[t.coef_C - t.ci_lo, t.ci_hi - t.coef_C], fmt="o", ms=8,
                       color=colr, capsize=3, lw=1.4, label=s_)
    style(ax[1])
    ax[1].set_xticks(x, [f"{l} m" for l in WLAB], fontsize=15)
    ax[1].set(xlabel="Forested buffer width, per side", ylabel="Corridor LST vs ≥ 200 m (°C)", title="Seasonal falsification test")
    ax[1].legend(fontsize=14, frameon=False, ncol=4, loc="lower left")
    fig.text(0.99, 0.01, f"{len(d):,} points on open channels; OLS with rich controls; 95% CI clustered by 1 km tile. Landsat 8 relative LST.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "threshold_and_seasons.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 8))
    order = [m for m in rob.model.unique() if "neighbourhood" not in m]
    for k, mlab in enumerate(order):
        t = rob[(rob.model == mlab) & (rob["class"].isin(["30-50", "50-100"]))].set_index("class")
        for j, (cl, mk, colr) in enumerate((("30-50", "o", "#8c8c8c"), ("50-100", "s", "#1d3f6e"))):
            if cl in t.index:
                r_ = t.loc[cl]
                ax.errorbar(r_.coef_C, k + (j - 0.5) * 0.25, xerr=[[r_.coef_C - r_.ci_lo], [r_.ci_hi - r_.coef_C]], fmt=mk,
                            color=colr, ms=8, capsize=3, label=f"{cl} m per side" if k == 0 else None)
    ax.set_yticks(range(len(order)), order, fontsize=14)
    ax.invert_yaxis()
    ax.axvline(0, color="0.45", lw=1.2, ls="--")
    ax.set(xlabel="Corridor LST vs ≥ 200 m per side (°C)", title="Robustness of the narrow-buffer penalty")
    ax.grid(axis="x", color="0.9", lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(fontsize=14, frameon=False, loc="lower right")
    fig.text(0.99, 0.01, f"Positive = warmer than wide (≥ 200 m) buffers. 95% CI clustered by 1 km tile.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "robustness.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 7.5))
    cmap = plt.get_cmap("viridis")
    for k, lab in enumerate(WLAB):
        t = prof[prof["class"] == lab]
        ax.plot(t.dist_m, t.excess_C, "o-", color=cmap(k / (len(WLAB) - 1)), lw=2, ms=5,
                label=f"{lab} m (extent {extent[lab]:.0f} m)" if np.isfinite(extent[lab]) else f"{lab} m")
    ax.axhline(-0.5, color="0.6", lw=1, ls=":")
    style(ax)
    ax.set(xlabel="Distance from channel (m)", ylabel="LST minus background 480–630 m (°C)",
           title="How far does stream-corridor cooling reach?")
    ax.legend(title="Buffer per side", fontsize=13, title_fontsize=14, frameon=False, loc="lower right")
    fig.text(0.99, 0.01, f"Median cross-stream profiles of Jul–Aug mean relative LST; extent = first distance within 0.5 °C of background.\n{CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45", linespacing=1.3)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "cooling_distance.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
