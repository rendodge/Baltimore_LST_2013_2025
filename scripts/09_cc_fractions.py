"""Aggregate Chesapeake Conservancy 1 m LULC to surface-cover fractions on the Landsat 30 m grid.

For each CC period (2013/14, 2021/22) and each surface group, the percentage of every 30 m
Landsat cell (EPSG:32618, grid of the LST trend rasters) covered by that group is computed by
area-weighted averaging (GDAL 'average') of a 1 m binary mask, directly from the native 1 m
grid (ESRI:102039) - one resampling step. CC no-data (0, outside the city) is excluded; the
percentage of each cell covered by valid CC data is written as `valid_pct`.

Groups are top-of-surface (what the thermal sensor sees): tree canopy over roads, structures,
other impervious and turf counts as canopy.

Outputs: data/processed/cc_lulc/cc_frac_<group>_<year>_utm.tif (float32 %, nodata -9999).
Run: conda run -p .\\env python scripts\\09_cc_fractions.py
"""
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import Window, from_bounds

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/cc_lulc"
GRID = ROOT / "data/processed/lst_trend/B_rel_slope_ols.tif"
OUT = ROOT / "data/processed/cc_lulc"
YEARS = {2013: "balt_24510_lulc_2013_2024-Edition.tif", 2021: "balt_24510_lulc_2021_2024-Edition.tif"}
GROUPS = {
    "canopy": [23, 24, 25, 26, 40, 41, 53, 54, 55, 63, 64, 65, 73, 74, 75],
    "structures": [21],
    "roads": [20],
    "other_imperv": [22, 31, 32],
    "turf": [27],
    "bare": [15, 28, 30, 33, 36, 42, 45, 50, 60, 70, 80, 82, 85],
    "herb_shrub": [34, 35, 37, 38, 43, 44, 46, 51, 52, 61, 62, 71, 72, 81, 83, 84, 86],
    "water": [10, 11, 12, 13, 14],
}
TILE = 100  # destination pixels per tile side (3 km)
NODATA = -9999.0


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(GRID) as g:
        dprof, dtr, dcrs, (H, W) = g.profile.copy(), g.transform, g.crs, g.shape
    all_codes = sorted({c for v in GROUPS.values() for c in v})

    for year, fname in YEARS.items():
        out = {k: np.full((H, W), np.nan, "float32") for k in list(GROUPS) + ["valid"]}
        with rasterio.open(RAW / fname) as src:
            for r0 in range(0, H, TILE):
                for c0 in range(0, W, TILE):
                    h, w = min(TILE, H - r0), min(TILE, W - c0)
                    ttr = rasterio.windows.transform(Window(c0, r0, w, h), dtr)
                    b = rasterio.windows.bounds(Window(c0, r0, w, h), dtr)
                    sb = transform_bounds(dcrs, src.crs, *b, densify_pts=21)
                    sb = (sb[0] - 60, sb[1] - 60, sb[2] + 60, sb[3] + 60)
                    win = from_bounds(*sb, transform=src.transform).round_offsets().round_lengths()
                    try:
                        win = win.intersection(Window(0, 0, src.width, src.height))
                    except rasterio.errors.WindowError:  # tile entirely outside the CC raster
                        continue
                    codes = src.read(1, window=win)
                    if not (codes > 0).any():
                        continue
                    stx = src.window_transform(win)
                    unknown = set(np.unique(codes).tolist()) - set(all_codes) - {0}
                    assert not unknown, f"unmapped CC classes {unknown}"
                    valid = codes > 0
                    layers = {"valid": valid.astype("float32")}
                    for k, cl in GROUPS.items():
                        layers[k] = np.where(valid, np.isin(codes, cl), np.nan).astype("float32")
                    for k, arr in layers.items():
                        dst = np.full((h, w), np.nan, "float32")
                        reproject(arr, dst, src_transform=stx, src_crs=src.crs, dst_transform=ttr, dst_crs=dcrs,
                                  src_nodata=None if k == "valid" else np.nan, dst_nodata=np.nan,
                                  resampling=Resampling.average)
                        out[k][r0:r0 + h, c0:c0 + w] = dst * 100
        for k, arr in out.items():
            name = "valid_pct" if k == "valid" else k
            p = dprof.copy()
            p.update(driver="COG", dtype="float32", nodata=NODATA, count=1, compress="DEFLATE", predictor=3)
            for key in ("blockxsize", "blockysize", "tiled", "interleave"):
                p.pop(key, None)
            with rasterio.open(OUT / f"cc_frac_{name}_{year}_utm.tif", "w", **p) as d:
                d.write(np.where(np.isfinite(arr), arr, NODATA).astype("float32"), 1)
                d.set_band_description(1, f"CC LULC {name} {year} (% of 30 m cell)")
        tot = sum(out[k] for k in GROUPS)
        v = np.isfinite(tot) & (out["valid"] > 99)
        print(year, "group sum over fully covered cells: min %.2f max %.2f" % (np.nanmin(tot[v]), np.nanmax(tot[v])),
              "| city means:", {k: round(float(np.nanmean(out[k][v])), 1) for k in GROUPS})


if __name__ == "__main__":
    main()
