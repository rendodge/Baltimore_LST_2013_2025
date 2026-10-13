"""Detect step changes in year-round relative LST for 90 m blocks (Landsat 8, 2013-2025).

Series: relative LST (pixel - scene city median) for the 101 all-month scenes >= 50% clear, averaged
to 90 m blocks (3x3, >= 7 valid pixels). For each block, the seasonal cycle is removed with a
harmonic fit (trend + annual + semi-annual terms; only the harmonic part is removed), and the
de-seasonalized values are averaged to one value per calendar year (>= 2 scenes; 13 years).

Step test per block (one break): for each candidate change year k in 2015-2023 (>= 2 years each
side), step model y = a + d * [year >= k] vs constant; sup-F over k. Critical value from 20,000
simulated white-noise series with the same years and missing pattern (5% level). A block is
called a STEP if sup-F exceeds the critical value AND the step model fits better (lower RSS)
than a linear trend; otherwise "trend-like" or "no change". ~5% of blocks are expected to pass by
chance. Same test on NSA-mean series for all NSAs; the 24 NSAs with significant year-round
relative trends (q < 0.10, strict annual test, from 24_allyear_trends.py) are summarized.

Outputs: data/processed/steps/ (block CSV, NSA CSV, 90 m rasters of step year and size),
figures/steps/*.png. Run after 24: conda run -p .\\env python scripts\\27_step_detection.py
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
from rasterio.features import geometry_mask, rasterize
from rasterio.transform import Affine

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


L = load_module("lst", ROOT / "scripts/02_lst_trend.py")
A = load_module("ally", ROOT / "scripts/24_allyear_trends.py")
OUT = ROOT / "data/processed/steps"
FIG = ROOT / "figures/steps"
YEARS = np.arange(2013, 2026)
CANDIDATES = np.arange(2015, 2024)
N_SIM, SEED = 20000, 42
CREDIT = "Landsat imagery courtesy of the U.S. Geological Survey"
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice|invalid value|divide by zero|Degrees of freedom", RuntimeWarning)
plt.rcParams.update({  # style of 07_scatter_impervious.py: defaults x2, Helvetica -> Arial
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 20, "axes.titlesize": 24, "axes.labelsize": 20, "xtick.labelsize": 20, "ytick.labelsize": 20,
})


def block_stack(stack, k=3):
    n, h, w = stack.shape
    h, w = (h // k) * k, (w // k) * k
    b = stack[:, :h, :w].reshape(n, h // k, k, w // k, k)
    return np.where(np.isfinite(b).sum((2, 4)) >= k * k - 2, np.nanmean(b, (2, 4)), np.nan)


def step_test(Y):
    """Y: years x series (NaN allowed). Returns sup-F, best year, step size, RSS step, RSS trend, n."""
    m = np.isfinite(Y)
    n = m.sum(0)
    y0 = np.where(m, Y, 0.0)
    mean = y0.sum(0) / np.maximum(n, 1)
    rss0 = (np.where(m, Y - mean, 0.0) ** 2).sum(0)
    best_f = np.full(Y.shape[1], -np.inf)
    best_k = np.full(Y.shape[1], np.nan)
    best_d = np.full(Y.shape[1], np.nan)
    best_rss = np.full(Y.shape[1], np.nan)
    for k in CANDIDATES:
        post = (YEARS >= k)[:, None] & m
        pre = (YEARS < k)[:, None] & m
        n1, n2 = pre.sum(0), post.sum(0)
        ok = (n1 >= 2) & (n2 >= 2)
        mu1 = np.where(pre, Y, 0).sum(0) / np.maximum(n1, 1)
        mu2 = np.where(post, Y, 0).sum(0) / np.maximum(n2, 1)
        rss1 = (np.where(pre, Y - mu1, 0) ** 2).sum(0) + (np.where(post, Y - mu2, 0) ** 2).sum(0)
        f = (rss0 - rss1) / (rss1 / np.maximum(n - 2, 1))
        better = ok & (f > best_f)
        best_f[better], best_k[better], best_d[better], best_rss[better] = f[better], k, (mu2 - mu1)[better], rss1[better]
    X = np.where(m, YEARS[:, None].astype(float), np.nan)
    xm = np.nanmean(X, 0)
    sxx = np.nansum((X - xm) ** 2, 0)
    b = np.nansum((X - xm) * (Y - mean), 0) / sxx
    rss_tr = np.nansum((np.where(m, Y - (mean + b * (X - xm)), np.nan)) ** 2, 0)
    return best_f, best_k, best_d, best_rss, rss_tr, n


def simulate_critical(miss_patterns, rng):
    """95th percentile of sup-F under white noise, for each distinct missing-year pattern."""
    crit = {}
    for pat in miss_patterns:
        Y = rng.standard_normal((len(YEARS), N_SIM))
        Y[~np.array(pat), :] = np.nan
        f = step_test(Y)[0]
        crit[pat] = np.nanpercentile(f[np.isfinite(f)], 95)
    return crit


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    with rasterio.open(L.OUT / "B_rel_slope_ols.tif") as s:
        tr, shape, crs = s.transform, s.shape, s.crs
    nsa = gpd.read_file(L.NSA).to_crs(32618)
    city = geometry_mask(nsa.geometry, out_shape=shape, transform=tr, invert=True)
    scenes, stack, _ = L.load_scenes(city, months=tuple(range(1, 13)))
    use = (scenes.clear_frac_city >= L.MIN_CLEAR).values
    sc = scenes[use].reset_index(drop=True)
    rel = np.where(city[None], stack[use] - sc.lst_median.values[:, None, None].astype("float32"), np.nan)
    del stack
    sc["date"] = pd.to_datetime(sc.scene_id.str[17:25])
    t = sc.year + (sc.date.dt.dayofyear - 0.5) / 365.25 - 2013
    X = A.design(t.values, sc.date.dt.dayofyear.values)
    yrs = sc.year.values

    B = block_stack(rel)                      # scenes x bh x bw
    nb, bh, bw = B.shape
    Yb = B.reshape(nb, -1)

    def annual_deseason(Ysc):
        """Remove the per-series harmonic part, then average per calendar year (>= 2 scenes)."""
        m = np.isfinite(Ysc)
        out = np.full((len(YEARS), Ysc.shape[1]), np.nan)
        for a in range(0, Ysc.shape[1], 20000):
            y = Ysc[:, a:a + 20000]
            mm = m[:, a:a + 20000]
            mf = mm.astype(float)
            k = X.shape[1]
            XtX = np.empty((y.shape[1], k, k))
            for i in range(k):
                for j in range(i, k):
                    XtX[:, i, j] = XtX[:, j, i] = mf.T @ (X[:, i] * X[:, j])
            Xty = np.where(mm, y, 0).T @ X
            ok = mf.sum(0) >= A.MIN_SCENES
            beta = np.full((y.shape[1], k), np.nan)
            beta[ok] = np.linalg.solve(XtX[ok], Xty[ok][..., None])[..., 0]
            ds = np.where(mm, y - X[:, 2:] @ beta[:, 2:].T, np.nan)
            for i, yy in enumerate(YEARS):
                sel = yrs == yy
                cnt = np.isfinite(ds[sel]).sum(0)
                out[i, a:a + 20000] = np.where(cnt >= 2, np.nanmean(ds[sel], 0), np.nan)
        return out

    Ann = annual_deseason(Yb)
    Ann[:, np.isfinite(Ann).sum(0) < 11] = np.nan  # need >= 11 of 13 years
    f, k, dlt, rss_s, rss_t, n = step_test(Ann)
    pats = [tuple(np.isfinite(Ann[:, j])) for j in range(Ann.shape[1])]
    valid = np.isfinite(f) & (n >= 11)
    rng = np.random.default_rng(SEED)
    uniq = sorted({p for p, v in zip(pats, valid) if v}, key=lambda p: -sum(p))
    crit = simulate_critical(uniq, rng)
    cv = np.array([crit.get(p, np.nan) if v else np.nan for p, v in zip(pats, valid)])
    sig = valid & (f > cv)
    step = sig & (rss_s < rss_t)
    cls = np.where(~valid, "no data", np.where(step, "step", np.where(sig, "trend-like", "no change")))
    print(f"blocks with data: {valid.sum()}; sup-F 5% critical (full series): {crit[uniq[0]]:.2f}")
    print("classes:", pd.Series(cls[valid]).value_counts().to_dict(),
          f"| step share {100 * step[valid].mean():.1f}% (5% expected by chance before the trend filter)")

    # block table with NSA membership (block centre)
    ids = rasterize(zip(nsa.geometry, np.arange(1, len(nsa) + 1)), out_shape=shape, transform=tr, fill=0, dtype="int32")
    bid = ids[1::3, 1::3][:bh, :bw].ravel()
    names = dict(zip(np.arange(1, len(nsa) + 1), nsa.Name))
    blk = pd.DataFrame({"block": np.arange(bh * bw), "nsa": pd.Series(bid).map(names), "class": cls,
                        "step_year": k, "step_C": dlt, "supF": f, "crit": cv,
                        "mean_rel": np.nanmean(Ann, 0)})
    blk = blk[blk["class"] != "no data"]
    blk.to_csv(OUT / "block_steps.csv", index=False, float_format="%.4f")

    # 90 m rasters
    t90 = tr * Affine.scale(3)
    prof = {"driver": "COG", "dtype": "float32", "nodata": -9999.0, "count": 1, "height": bh, "width": bw,
            "crs": crs, "transform": t90, "compress": "DEFLATE"}
    for name, arr in (("step_year", np.where(step, k, np.nan)), ("step_C", np.where(step, dlt, np.nan))):
        with rasterio.open(OUT / f"{name}_90m.tif", "w", **prof) as dst:
            dst.write(np.where(np.isfinite(arr), arr, -9999.0).reshape(bh, bw).astype("float32"), 1)

    # NSA-mean series
    yrnsa = pd.read_csv(ROOT / "data/processed/lst_allyear/nsa_lst_allyear_lc08.csv")
    sig24 = yrnsa[(yrnsa.pixels >= 100) & (yrnsa.rel_q_annual < 0.10)][["Name", "rel_trend"]]
    nsa_ids = ids.copy()
    cols = []
    for i, name in enumerate(nsa.Name, start=1):
        msk = nsa_ids == i
        if msk.sum() < 100:
            continue
        v = rel[:, msk]
        cov = np.isfinite(v).mean(1)
        cols.append((name, np.where(cov >= 0.5, np.nanmean(v, 1), np.nan)))
    Nsc = np.column_stack([c[1] for c in cols])
    Nann = annual_deseason(Nsc)
    fN, kN, dN, rsN, rtN, nN = step_test(Nann)
    patsN = [tuple(np.isfinite(Nann[:, j])) for j in range(Nann.shape[1])]
    critN = simulate_critical(sorted(set(patsN)), rng)
    cvN = np.array([critN[p] for p in patsN])
    nsa_tab = pd.DataFrame({"Name": [c[0] for c in cols], "supF": fN, "crit": cvN, "step_year": kN, "step_C": dN,
                            "step_better_than_trend": rsN < rtN})
    nsa_tab["nsa_step"] = (nsa_tab.supF > nsa_tab.crit) & nsa_tab.step_better_than_trend
    bsum = blk.groupby("nsa").agg(blocks=("class", "size"), step_share=("class", lambda s: 100 * (s == "step").mean()),
                                  step_year_median=("step_year", lambda s: np.nan), )
    st = blk[blk["class"] == "step"].groupby("nsa").agg(step_blocks=("step_C", "size"),
                                                         step_year_median=("step_year", "median"),
                                                         step_C_median=("step_C", "median"),
                                                         cooling_steps=("step_C", lambda s: int((s < 0).sum())),
                                                         warming_steps=("step_C", lambda s: int((s > 0).sum())))
    bsum = bsum.drop(columns="step_year_median").join(st)
    nsa_tab = nsa_tab.merge(bsum, left_on="Name", right_index=True, how="left").merge(
        yrnsa[["Name", "rel_trend", "rel_q_annual"]], on="Name", how="left")
    nsa_tab["significant_trend"] = nsa_tab.Name.isin(sig24.Name)
    for c_ in range(len(YEARS)):
        nsa_tab[f"y{YEARS[c_]}"] = Nann[c_]
    nsa_tab.to_csv(OUT / "nsa_steps.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 230)
    show = ["Name", "rel_trend", "nsa_step", "step_year", "step_C", "blocks", "step_share", "cooling_steps", "warming_steps",
            "step_year_median"]
    s24 = nsa_tab[nsa_tab.significant_trend].sort_values("rel_trend")
    print("\n24 NSAs with significant year-round relative trends:\n", s24[show].to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    others = nsa_tab[~nsa_tab.significant_trend]
    print(f"\nblock step share: 24 NSAs median {s24.step_share.median():.1f}% vs other NSAs {others.step_share.median():.1f}%; "
          f"NSA-level steps: {int(s24.nsa_step.sum())}/24 vs {int(others.nsa_step.sum())}/{len(others)}")
    yr_counts = blk[(blk["class"] == "step") & blk.nsa.isin(s24.Name)].groupby(["step_year"]).step_C.agg(
        cooling=lambda s: int((s < 0).sum()), warming=lambda s: int((s > 0).sum()))
    print("\nstep years (blocks in the 24 NSAs):\n", yr_counts.to_string())

    # --- figures: small multiples of NSA annual series with fitted step
    s24 = s24.reset_index(drop=True)
    ncol = 6
    nrow = int(np.ceil(len(s24) / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(26, 4.2 * nrow), sharex=True)
    for ax, (_, r) in zip(axs.ravel(), s24.iterrows()):
        yv = np.array([r[f"y{yy}"] for yy in YEARS])
        colr = "#2166ac" if r.rel_trend < 0 else "#b2182b"
        ax.plot(YEARS, yv, "o-", color=colr, lw=1.6, ms=5)
        if r.nsa_step:
            k0 = int(r.step_year)
            pre, post = np.nanmean(yv[YEARS < k0]), np.nanmean(yv[YEARS >= k0])
            ax.hlines([pre, post], [2013, k0], [k0 - 0.5, 2025], colors="0.2", lw=2)
            ax.axvline(k0 - 0.5, color="0.5", lw=1, ls=":")
        ax.set_title(f"{r.Name[:24]}\n{r.rel_trend:+.3f} °C/yr" + (f"; step {int(r.step_year)}" if r.nsa_step else ""), fontsize=14)
        ax.tick_params(labelsize=12)
        ax.grid(color="0.92", lw=0.8)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    for ax in axs.ravel()[len(s24):]:
        ax.axis("off")
    fig.suptitle("De-seasonalized annual relative LST, 24 NSAs with significant year-round trends (blue = cooling, red = warming)", fontsize=20)
    fig.text(0.99, 0.005, f"Landsat 8 all months, 2013–2025; black lines = before/after means where a single step beats both no change "
             f"(simulated sup-F, 5%) and a linear trend. {CREDIT}", ha="right", va="bottom", fontsize=12, color="0.45")
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    fig.savefig(FIG / "nsa24_step_series.png", dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 7))
    yc = yr_counts.reindex(CANDIDATES, fill_value=0)
    ax.bar(yc.index - 0.2, yc.cooling, width=0.4, color="#2166ac", label="Cooling step")
    ax.bar(yc.index + 0.2, yc.warming, width=0.4, color="#b2182b", label="Warming step")
    ax.set(xlabel="First year after the step", ylabel="Blocks (90 m)", title="When did blocks in the 24 NSAs shift?")
    ax.set_xticks(CANDIDATES)
    ax.grid(axis="y", color="0.9", lw=0.8)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(fontsize=15, frameon=False)
    fig.text(0.99, 0.01, f"Blocks classed as a step (simulated sup-F 5% and better than a linear trend). {CREDIT}",
             ha="right", va="bottom", fontsize=11, color="0.45")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "nsa24_step_years.png", dpi=150)


if __name__ == "__main__":
    main()
