"""Summarize summer LST and LST trends by Neighborhood Statistical Area (NSA).

Inputs: trend products for the active sensor set (env LST_SENSORS, default Landsat 8; the
primary set is LC08,LC09), Chesapeake Conservancy cover fractions (09), NLCD impervious change
(06), NSA boundaries with 2020 Census counts.

Per NSA (30 m pixels whose centres fall in the NSA; pixels >= 50% water in CC 2021/22 excluded):
  - mean summer LST and mean relative LST (variant B);
  - trends fitted to the NSA-mean annual series (relative LST, B; weather-normalized absolute
    LST with climate kept, C1): OLS slope, 95% CI, p, and Benjamini-Hochberg q across NSAs.
    A year counts only if >= 50% of the NSA's pixels are valid that year.
  - share of pixels with a significant (p < 0.05) per-pixel relative trend, by sign;
  - cover context: canopy and impervious (structures + roads + other) % in 2021/22,
    change 2013/14 -> 2021/22 (CC), NLCD impervious change 2013 -> 2025;
  - population (2020) and density. NSAs with < 100 pixels (< 0.09 km2) are flagged.
Neighbouring NSAs share weather and are spatially correlated; q-values assume independence.

Outputs: data/processed/nsa/nsa_lst_<sensors>.gpkg and .csv.
Run: LST_SENSORS=LC08,LC09 conda run -p .\\env python scripts\\13_nsa_summary.py
"""
import importlib.util
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lst", ROOT / "scripts/02_lst_trend.py")
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
LST, YEARS = L.OUT, L.YEARS
CC = ROOT / "data/processed/cc_lulc"
LC = ROOT / "data/processed/landcover"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
OUT = ROOT / "data/processed/nsa"
MIN_YEAR_COVER = 0.5
SMALL_PIXELS = 100
warnings.filterwarnings("ignore", "Mean of empty slice|All-NaN slice", RuntimeWarning)


def read(p, band=None):
    with rasterio.open(p) as s:
        a = (s.read() if band is None else s.read(band)).astype("float64")
        return np.where(a == s.nodata, np.nan, a)


def bh_q(p):
    """Benjamini-Hochberg adjusted p-values (NaN-aware)."""
    p = np.asarray(p, float)
    q = np.full_like(p, np.nan)
    ok = np.isfinite(p)
    ps = p[ok]
    order = np.argsort(ps)
    ranked = ps[order] * len(ps) / (np.arange(len(ps)) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty_like(ps)
    out[order] = np.minimum(ranked, 1)
    q[ok] = out
    return q


def series_trend(ann, ids, nid, n_px):
    """OLS trend of the NSA-mean annual series; years need >= MIN_YEAR_COVER valid pixels."""
    m = ids == nid
    vals = ann[:, m]
    cover = np.isfinite(vals).sum(1) / n_px
    y = np.where(cover >= MIN_YEAR_COVER, np.nanmean(vals, 1), np.nan)
    ok = np.isfinite(y)
    if ok.sum() < 8:
        return dict(slope=np.nan, ci95=np.nan, p=np.nan, years=int(ok.sum()))
    r = stats.linregress(YEARS[ok], y[ok])
    return dict(slope=r.slope, ci95=stats.t.ppf(0.975, ok.sum() - 2) * r.stderr, p=r.pvalue, years=int(ok.sum()))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "_".join(L.SENSORS).lower()
    with rasterio.open(LST / "B_rel_slope_ols.tif") as s:
        tr, shape = s.transform, s.shape
    nsa = gpd.read_file(NSA)
    nsa["nsa_id"] = np.arange(1, len(nsa) + 1)
    ids = rasterize(zip(nsa.geometry, nsa.nsa_id), out_shape=shape, transform=tr, fill=0, dtype="int32")
    water = read(CC / "cc_frac_water_2021_utm.tif", 1)
    ids = np.where(np.nan_to_num(water) >= 50, 0, ids)

    lay = {k: read(LST / f, 1) for k, f in [("mean_lst", "B_mean_lst_C.tif"), ("mean_rel", "B_mean_rel_lst_C.tif"),
                                            ("px_slope", "B_rel_slope_ols.tif"), ("px_p", "B_rel_p_ols.tif")]}
    for k, f in [("canopy21", "cc_frac_canopy_2021_utm.tif"), ("canopy13", "cc_frac_canopy_2013_utm.tif")]:
        lay[k] = read(CC / f, 1)
    for y in (2013, 2021):
        lay[f"imperv{y % 100}"] = sum(read(CC / f"cc_frac_{g}_{y}_utm.tif", 1) for g in ("structures", "roads", "other_imperv"))
    lay["nlcd_dimp"] = read(LC / "nlcd_dimp_2013_2025_pp.tif", 1)
    ann_rel = read(LST / "B_annual_rel_lst_C.tif")
    ann_c1 = read(LST / "C1_annual_lst_C.tif")

    rows = []
    for nid in nsa.nsa_id:
        m = ids == nid
        n_px = int(m.sum())
        r = {"nsa_id": nid, "pixels": n_px}
        if n_px == 0:
            rows.append(r)
            continue
        for k, a in lay.items():
            if k not in ("px_slope", "px_p"):
                r[k] = np.nanmean(a[m])
        s, p = lay["px_slope"][m], lay["px_p"][m]
        v = np.isfinite(s) & np.isfinite(p)
        r["px_sig_warm_pct"] = 100 * ((p < 0.05) & (s > 0) & v).sum() / max(v.sum(), 1)
        r["px_sig_cool_pct"] = 100 * ((p < 0.05) & (s < 0) & v).sum() / max(v.sum(), 1)
        for name, ann in (("rel", ann_rel), ("c1", ann_c1)):
            t = series_trend(ann, ids, nid, n_px)
            r.update({f"{name}_trend": t["slope"], f"{name}_ci95": t["ci95"], f"{name}_p": t["p"], f"{name}_years": t["years"]})
        rows.append(r)
    df = pd.DataFrame(rows)
    df["rel_q"], df["c1_q"] = bh_q(df.rel_p), bh_q(df.c1_p)
    df["d_canopy"] = df.canopy21 - df.canopy13
    df["d_imperv"] = df.imperv21 - df.imperv13
    df["rel_change_12yr"] = df.rel_trend * (YEARS[-1] - YEARS[0])  # slope-implied, not an endpoint difference
    df["c1_change_12yr"] = df.c1_trend * (YEARS[-1] - YEARS[0])
    df["small_nsa"] = df.pixels < SMALL_PIXELS
    out = nsa[["nsa_id", "Name", "Population", "geometry"]].merge(df, on="nsa_id")
    out["area_km2"] = out.geometry.area / 1e6
    out["pop_per_km2"] = out.Population / out.area_km2
    out = out.drop(columns=["canopy13", "imperv13"])
    out.to_file(OUT / f"nsa_lst_{tag}.gpkg", layer="nsa_lst", driver="GPKG")
    out.drop(columns="geometry").to_csv(OUT / f"nsa_lst_{tag}.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 250)
    v = out[~out.small_nsa & out.rel_trend.notna()]
    cols = ["Name", "Population", "mean_lst", "mean_rel", "rel_trend", "rel_ci95", "rel_p", "rel_q", "c1_trend",
            "canopy21", "imperv21", "d_imperv", "nlcd_dimp"]
    fmt = lambda x: f"{x:.3f}"
    print(f"{len(out)} NSAs; {int(out.small_nsa.sum())} small; {int(out.rel_trend.isna().sum())} without a trend")
    print("relative trend: p<0.05", int((v.rel_p < 0.05).sum()), "| q<0.10", int((v.rel_q < 0.10).sum()),
          "(warming", int(((v.rel_q < 0.10) & (v.rel_trend > 0)).sum()), ", cooling", int(((v.rel_q < 0.10) & (v.rel_trend < 0)).sum()), ")")
    print("C1 trend: median", fmt(v.c1_trend.median()), "| p<0.05", int((v.c1_p < 0.05).sum()), "| q<0.10", int((v.c1_q < 0.10).sum()))
    print("\nTop 12 relative warming:\n", v.sort_values("rel_trend", ascending=False)[cols].head(12).to_string(index=False, float_format=fmt))
    print("\nTop 12 relative cooling:\n", v.sort_values("rel_trend")[cols].head(12).to_string(index=False, float_format=fmt))
    print("\nHottest 10 (mean relative LST):\n", v.sort_values("mean_rel", ascending=False)[cols].head(10).to_string(index=False, float_format=fmt))
    sp = lambda a, b: stats.spearmanr(v[a], v[b], nan_policy="omit").statistic
    print("\nSpearman across NSAs: rel_trend vs mean_rel %.2f | canopy21 %.2f | imperv21 %.2f | d_imperv %.2f | nlcd_dimp %.2f | pop density %.2f"
          % (sp("rel_trend", "mean_rel"), sp("rel_trend", "canopy21"), sp("rel_trend", "imperv21"),
             sp("rel_trend", "d_imperv"), sp("rel_trend", "nlcd_dimp"), sp("rel_trend", "pop_per_km2")))


if __name__ == "__main__":
    main()
