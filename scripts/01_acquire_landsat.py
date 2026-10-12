"""Acquire Landsat C2 L2 surface-temperature subsets over Baltimore City.

Source: Microsoft Planetary Computer STAC, collection `landsat-c2-l2` (USGS Collection 2
Level-2, mirrored unmodified). Filter: Landsat 8 (default) or Landsat 9, WRS-2 path 15 /
row 33, Tier 1, L2SP, July-August, 2013-2025 (Landsat 9 data begin late 2021).

For each scene, the native-grid window covering the NSA boundaries (+450 m) is copied from
the source COGs with values, dtype, no-data, and grid unchanged (no resampling):
ST_B10 (`lwir11`), QA_PIXEL, ST_QA (`qa`). The full MTL.txt and the STAC item JSON are
also saved. Every file is appended to data/raw/MANIFEST.csv.

Run: conda run -p .\\env python scripts\\01_acquire_landsat.py [landsat-8|landsat-9]
Manifest rows and skipped-scene entries for the other platform are kept.
"""
import csv
import hashlib
import json
import shutil
import sys
import time
from datetime import date
from pathlib import Path

import geopandas as gpd
import planetary_computer as pc
import pystac_client
import rasterio
import requests
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
NSA = ROOT / "data/vector/Neighborhood_Statistical_Area_(NSA)_Boundaries/Neighborhood_Statistical_Area_(NSA)_Boundaries.shp"
OUT = ROOT / "data/raw/landsat"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
BANDS = {"lwir11": "ST_B10", "qa_pixel": "QA_PIXEL", "qa": "ST_QA"}
BUFFER_M = 450
LICENSE = "USGS public domain"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_window(href, dst, bounds):
    """Copy the native-grid window covering `bounds`; values and grid unchanged."""
    tmp = dst.with_suffix(".part.tif")
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"), rasterio.open(href) as src:
        win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
        prof = src.profile.copy()
        prof.update(driver="GTiff", width=win.width, height=win.height,
                    transform=src.window_transform(win), compress="deflate",
                    tiled=True, blockxsize=256, blockysize=256)
        prof.pop("photometric", None)
        data = src.read(1, window=win, boundless=True, fill_value=src.nodata or 0)
        with rasterio.open(tmp, "w", **prof) as out:
            out.write(data, 1)
    tmp.replace(dst)


def main(platform="landsat-8"):
    nsa = gpd.read_file(NSA).to_crs(32618)
    xmin, ymin, xmax, ymax = nsa.total_bounds
    # Snap outward to the Landsat grid (pixel edges at 15 m mod 30 m).
    snap = lambda v, up: (((v - 15) // 30) + up) * 30 + 15
    bounds = (snap(xmin - BUFFER_M, 0), snap(ymin - BUFFER_M, 0),
              snap(xmax + BUFFER_M, 1), snap(ymax + BUFFER_M, 1))
    bbox_ll = nsa.to_crs(4326).total_bounds.tolist()
    print("subset bounds (EPSG:32618):", bounds)

    cat = pystac_client.Client.open(STAC)  # sign per scene below; SAS tokens expire
    query = {"platform": {"eq": platform}, "landsat:wrs_path": {"eq": "015"},
             "landsat:wrs_row": {"eq": "033"}, "landsat:collection_category": {"eq": "T1"}}
    items = [it for it in cat.search(collections=["landsat-c2-l2"], bbox=bbox_ll,
                                     datetime="2013-07-01/2025-08-31", query=query).items()
             if it.datetime.month in (7, 8) and "_L2SP_" in it.id]
    items.sort(key=lambda it: it.datetime)
    print(f"{platform}: {len(items)} scenes")

    rows, skipped = [], []
    for it in items:
        d = OUT / it.id
        d.mkdir(parents=True, exist_ok=True)
        it = pc.sign(it)
        files, failed = [], None
        for key, name in BANDS.items():
            dst = d / f"{it.id}_{name}_subset.tif"
            href = it.assets[key].href.split("?")[0]
            if not dst.exists():
                for attempt in range(4):
                    try:
                        copy_window(pc.sign(href), dst, bounds)
                        break
                    except rasterio.errors.RasterioIOError as e:
                        if "not recognized" in str(e):  # source object is not a GeoTIFF; not transient
                            break
                        print(f"  retry {attempt + 1} {name}: {str(e)[:80]}")
                        time.sleep(15 * (attempt + 1))
            if not dst.exists():
                failed = (name, href)
                break
            files.append((dst, href, f"{name} native-grid subset {bounds}"))
        if failed:
            print(it.id, f"SKIPPED: unreadable {failed[0]} at source")
            skipped.append({"scene_id": it.id, "asset": failed[0], "href": failed[1],
                            "reason": "source object not a readable GeoTIFF", "checked": date.today().isoformat()})
            shutil.rmtree(d)
            continue
        mtl = d / f"{it.id}_MTL.txt"
        if not mtl.exists():
            r = requests.get(it.assets["mtl.txt"].href, timeout=60)
            r.raise_for_status()
            mtl.write_bytes(r.content)
        files.append((mtl, it.assets["mtl.txt"].href.split("?")[0], "full file"))
        sj = d / f"{it.id}_stac.json"
        item_dict = it.to_dict()
        for a in item_dict["assets"].values():  # strip expiring SAS tokens
            a["href"] = a["href"].split("?")[0]
        sj.write_text(json.dumps(item_dict, indent=1))
        files.append((sj, f"{STAC}/collections/landsat-c2-l2/items/{it.id}", "STAC item"))
        for p, url, note in files:
            rows.append({"path": p.relative_to(ROOT).as_posix(), "source": "USGS via Microsoft Planetary Computer",
                         "dataset_id": f"landsat-c2-l2/{it.id}", "url_or_query": f"{url} ({note})",
                         "retrieved": date.today().isoformat(), "bytes": p.stat().st_size,
                         "sha256": sha256(p), "license": LICENSE, "storage": "local"})
        print(it.id, f"cloud={it.properties['eo:cloud_cover']:.0f}%")

    # Rewrite manifest: keep non-landsat rows, replace landsat rows.
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        done = {r["path"] for r in rows}
        prefix = "data/raw/landsat/LC0" + platform[-1]
        keep = [r for r in reader if r["path"] not in done
                and not (r["path"].startswith(prefix) and r["path"].split("/")[3] in {s["scene_id"] for s in skipped})]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)
    print(f"manifest: {len(rows)} landsat rows")
    sk_path = OUT / "skipped_scenes.csv"
    old = list(csv.DictReader(open(sk_path, newline=""))) if sk_path.exists() else []
    ids = {s["scene_id"] for s in skipped}
    old = [r for r in old if r["scene_id"] not in ids and not r["scene_id"].startswith("LC0" + platform[-1])]
    with open(sk_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["scene_id", "asset", "href", "reason", "checked"])
        w.writeheader()
        w.writerows(old + skipped)
    print(f"skipped {len(skipped)} scenes")


if __name__ == "__main__":
    main(*sys.argv[1:2])
