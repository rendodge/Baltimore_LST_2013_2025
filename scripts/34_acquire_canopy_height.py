"""Acquire the Meta / WRI 1 m global canopy height map (Tolan et al. 2024, v1 'alsgedi_global_v6_float')
over Baltimore City.

The map is a model estimate of canopy height (m, uint8) from leaf-on Maxar imagery (mostly 2018-2020),
trained on aerial lidar and GEDI. Tiles are level-9 Web Mercator quadkeys on the public AWS Open Data
bucket; the city lies on the corner of four tiles. For each tile the window covering the NSAs + 1 km is
read over HTTP range requests (native EPSG:3857 grid, values unchanged) and saved to
data/raw/canopy_height/; rows are added to data/raw/MANIFEST.csv.

(The 3DEP 2014 lidar DSM/DTM rasters on Planetary Computer were tested first and rejected: IDW of all
returns in a leaf-off flight gives 99th-percentile heights of 9-13 m in mature forest.)

Run: conda run -p .\\env python scripts\\34_acquire_canopy_height.py
"""
import csv
import hashlib
import math
import os
from datetime import date
from pathlib import Path

import geopandas as gpd
import rasterio
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/canopy_height"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
BASE = "https://dataforgood-fb-data.s3.amazonaws.com/forests/v1/alsgedi_global_v6_float/chm"
BUFFER_M = 1000
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES",
                  CPL_VSIL_CURL_CHUNK_SIZE="10485760", GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="3")


def quadkey(lon, lat, z=9):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return "".join(str(((x >> i) & 1) + 2 * ((y >> i) & 1)) for i in range(z - 1, -1, -1))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    b = gpd.read_file(ROOT / "data/vector/nsa_boundaries_32618.gpkg").total_bounds
    b = (b[0] - BUFFER_M, b[1] - BUFFER_M, b[2] + BUFFER_M, b[3] + BUFFER_M)
    ll = transform_bounds("EPSG:32618", "EPSG:4326", *b)
    merc = transform_bounds("EPSG:32618", "EPSG:3857", *b)
    keys = sorted({quadkey(lo, la) for lo in (ll[0], ll[2]) for la in (ll[1], ll[3])})
    rows = []
    for k in keys:
        url = f"{BASE}/{k}.tif"
        dst = OUT / f"meta_chm_{k}_baltimore_subset.tif"
        if not dst.exists():
            with rasterio.open(f"/vsicurl/{url}") as src:
                tb = src.bounds
                w_b = (max(merc[0], tb.left), max(merc[1], tb.bottom), min(merc[2], tb.right), min(merc[3], tb.top))
                win = from_bounds(*w_b, transform=src.transform).round_offsets().round_lengths()
                data = src.read(1, window=win)
                prof = src.profile.copy()
                prof.update(driver="GTiff", width=win.width, height=win.height, transform=src.window_transform(win),
                            compress="deflate", predictor=2, tiled=True, blockxsize=512, blockysize=512)
                with rasterio.open(dst, "w", **prof) as o:
                    o.write(data, 1)
                    o.update_tags(source=url, units="m", product="Meta/WRI global canopy height v1 (Tolan et al. 2024)")
            print(k, data.shape, "max", int(data.max()), flush=True)
        rows.append({"path": dst.relative_to(ROOT).as_posix(), "source": "Meta / World Resources Institute (AWS Open Data)",
                     "dataset_id": "Global canopy height 1 m v1 (alsgedi_global_v6_float), tile " + k,
                     "url_or_query": f"{url} (native-grid window, NSAs + {BUFFER_M} m)", "retrieved": date.today().isoformat(),
                     "bytes": dst.stat().st_size, "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
                     "license": "CC BY 4.0", "storage": "local"})
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/canopy_height/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)
    print(f"{len(rows)} tiles -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
