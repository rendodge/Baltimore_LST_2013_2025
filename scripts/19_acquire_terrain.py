"""Acquire terrain data for Baltimore City.

1. USGS 3DEP seamless DEM, 1/3 arc-second (~10 m), tile n40w077 (Microsoft Planetary Computer
   collection `3dep-seamless`): the native-grid window covering the NSAs + 1.5 km (room for the
   1 km topographic-position window) is copied unchanged to data/raw/terrain/.
2. Chesapeake Hyper-Resolution Hydrography 10 m geomorphon raster for HUC8 02060003 (ScienceBase
   679cfd13d34e89501cd2d6ed), stored as downloaded.
Both are listed in data/raw/MANIFEST.csv.

Run: conda run -p .\\env python scripts\\19_acquire_terrain.py
"""
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

import geopandas as gpd
import planetary_computer as pc
import pystac_client
import rasterio
import requests
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/terrain"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
GEOMORPHON = ("huc_02060003_geomorphon10m.tif",
              "https://prod-is-usgs-sb-prod-publish.s3.amazonaws.com/679cfd13d34e89501cd2d6ed/huc_02060003_geomorphon10m.tif")
BUFFER_M = 1500


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    city = gpd.read_file(NSA)
    rows = []

    # 1. 3DEP 1/3 arc-second window
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    items = [it for it in cat.search(collections=["3dep-seamless"], bbox=city.to_crs(4326).total_bounds.tolist()).items()
             if it.properties.get("gsd") == 10]
    assert len(items) == 1, [it.id for it in items]
    it = pc.sign(items[0])
    dem = OUT / f"3dep_{it.id}_baltimore_subset.tif"
    href = it.assets["data"].href
    if not dem.exists():
        with rasterio.open(href) as src:
            b = city.buffer(BUFFER_M).total_bounds
            win = from_bounds(*transform_bounds("EPSG:32618", src.crs, *b), transform=src.transform)
            win = win.round_offsets().round_lengths()
            prof = src.profile.copy()
            prof.update(driver="GTiff", width=win.width, height=win.height, transform=src.window_transform(win),
                        compress="deflate", predictor=3, tiled=True, blockxsize=256, blockysize=256)
            with rasterio.open(dem, "w", **prof) as out:
                out.write(src.read(1, window=win), 1)
        item = it.to_dict()
        for a in item["assets"].values():
            a["href"] = a["href"].split("?")[0]
        (OUT / f"3dep_{it.id}_stac.json").write_text(json.dumps(item, indent=1))
    base = href.split("?")[0]
    rows += [(dem, "USGS 3DEP via Microsoft Planetary Computer", f"3dep-seamless/{it.id} (1/3 arc-second)",
              f"{base} (native-grid window, NSAs + {BUFFER_M} m)"),
             (OUT / f"3dep_{it.id}_stac.json", "USGS 3DEP via Microsoft Planetary Computer", f"3dep-seamless/{it.id}",
              "STAC item")]

    # 2. CC geomorphon 10 m
    gpath = OUT / GEOMORPHON[0]
    if not gpath.exists():
        with requests.get(GEOMORPHON[1], stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(gpath, "wb") as f:
                for chunk in r.iter_content(1 << 22):
                    f.write(chunk)
    rows.append((gpath, "Chesapeake Conservancy / UMBC via ScienceBase",
                 "Chesapeake Bay Hyper-Resolution Hydrography, HUC8 02060003 geomorphon 10 m", GEOMORPHON[1]))

    out = []
    for p, source, dsid, url in rows:
        size = p.stat().st_size
        out.append({"path": p.relative_to(ROOT).as_posix(), "source": source, "dataset_id": dsid, "url_or_query": url,
                    "retrieved": date.today().isoformat(), "bytes": size, "sha256": sha256(p),
                    "license": "public domain (USGS); CC/UMBC open data", "storage": "git" if size <= 25e6 else "local"})
        print(p.name, size)
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/terrain/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + out)


if __name__ == "__main__":
    main()
