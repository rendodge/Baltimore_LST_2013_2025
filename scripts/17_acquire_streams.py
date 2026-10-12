"""Download stream networks for the Gunpowder-Patapsco HUC8 (02060003) and clip them to Baltimore City.

1. Chesapeake Bay Hyper-Resolution Hydrography (Chesapeake Conservancy / UMBC; ScienceBase
   679cfd13d34e89501cd2d6ed): streamLine.zip and the product metadata XML.
2. USGS NHD High Resolution (published 2023-12-15), HU8 shapefile bundle (NHDFlowline used).
Raw zips are stored unmodified in data/raw/streams/ and listed in data/raw/MANIFEST.csv.
Flowlines are clipped to the NSA union (Baltimore City) and written, in EPSG:32618, to
data/vector/streams_cc_city.gpkg and data/vector/streams_nhd_city.gpkg.

Run: conda run -p .\\env python scripts\\17_acquire_streams.py
"""
import csv
import hashlib
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/streams"
VEC = ROOT / "data/vector"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
NSA = VEC / "nsa_boundaries_32618.gpkg"
SB = "https://www.sciencebase.gov/catalog/file/get/679cfd13d34e89501cd2d6ed?name={}"
SOURCES = [
    ("huc_02060003_streamLine.zip", SB.format("huc_02060003_streamLine.zip"),
     "Chesapeake Conservancy / UMBC via ScienceBase", "Chesapeake Bay Hyper-Resolution Hydrography, HUC8 02060003 streamLine"),
    ("metadata_02060003.xml", SB.format("metadata_02060003.xml"),
     "Chesapeake Conservancy / UMBC via ScienceBase", "Chesapeake Bay Hyper-Resolution Hydrography, HUC8 02060003 metadata"),
    ("NHD_H_02060003_HU8_Shape.zip",
     "https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU8/Shape/NHD_H_02060003_HU8_Shape.zip",
     "USGS The National Map", "NHD High Resolution HU8 02060003 (published 2023-12-15), shapefile"),
]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dst):
    part = dst.with_suffix(dst.suffix + ".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    part.replace(dst)


def find_member(zpath, suffix):
    with zipfile.ZipFile(zpath) as z:
        hits = [m for m in z.namelist() if m.lower().endswith(suffix.lower())]
    assert len(hits) == 1, (zpath.name, suffix, hits)
    return hits[0]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, url, source, dsid in SOURCES:
        dst = RAW / name
        if not dst.exists():
            download(url, dst)
        size = dst.stat().st_size
        rows.append({"path": dst.relative_to(ROOT).as_posix(), "source": source, "dataset_id": dsid, "url_or_query": url,
                     "retrieved": date.today().isoformat(), "bytes": size, "sha256": sha256(dst),
                     "license": "public domain (USGS/EPA-funded); see product metadata",
                     "storage": "git" if size <= 25e6 else "local"})
        print(name, size)

    city = gpd.read_file(NSA).dissolve()[["geometry"]]
    cc_zip = RAW / "huc_02060003_streamLine.zip"
    member = next(m for m in zipfile.ZipFile(cc_zip).namelist() if m.lower().endswith((".shp", ".gpkg")))
    cc = gpd.read_file(f"zip://{cc_zip.as_posix()}!{member}")
    nhd_zip = RAW / "NHD_H_02060003_HU8_Shape.zip"
    nhd = gpd.read_file(f"zip://{nhd_zip.as_posix()}!{find_member(nhd_zip, 'NHDFlowline.shp')}")
    for gdf, label, out in [(cc, "CC hyper-resolution", "streams_cc_city.gpkg"), (nhd, "NHD HR", "streams_nhd_city.gpkg")]:
        print(f"{label}: {len(gdf)} features, CRS {gdf.crs}, fields {list(gdf.columns)[:20]}")
        clipped = gpd.clip(gdf.to_crs(32618), city)
        clipped = clipped[~clipped.geometry.is_empty & clipped.geometry.notna()]
        clipped["length_m"] = clipped.geometry.length
        clipped.to_file(VEC / out, layer="streams", driver="GPKG")
        print(f"  -> {out}: {len(clipped)} features, {clipped.length_m.sum() / 1000:.1f} km in the city")

    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/streams/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)


if __name__ == "__main__":
    main()
