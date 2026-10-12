"""Download the Chesapeake Conservancy 1 m Land Use/Land Cover (2024 Edition) for Baltimore City.

Source: ScienceBase item 68011bd8d4be0263cab0ff37, "Land Use/Land Cover (LULC) Rasters:
Maryland - Baltimore City (24510)" - three city-clipped GeoTIFFs (2013/14, 2017/18, 2021/22)
and the product XML. Files are stored unmodified in data/raw/cc_lulc/ and added to
data/raw/MANIFEST.csv.

Run: conda run -p .\\env python scripts\\08_acquire_cc_lulc.py
"""
import csv
import hashlib
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/cc_lulc"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
ITEM = "68011bd8d4be0263cab0ff37"
URL = "https://www.sciencebase.gov/catalog/file/get/{item}?name={name}"
FILES = ["balt_24510_lulc_2013_2024-Edition.tif", "balt_24510_lulc_2018_2024-Edition.tif",
         "balt_24510_lulc_2021_2024-Edition.tif", "lulc_2024-Edition.xml"]
LICENSE = "Chesapeake Conservancy / USGS; see product XML for use constraints"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in FILES:
        dst, url = OUT / name, URL.format(item=ITEM, name=name)
        if not dst.exists():
            part = dst.with_suffix(dst.suffix + ".part")
            with requests.get(url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in r.iter_content(1 << 22):
                        f.write(chunk)
            part.replace(dst)
        size = dst.stat().st_size
        rows.append({"path": dst.relative_to(ROOT).as_posix(), "source": "Chesapeake Conservancy via ScienceBase",
                     "dataset_id": f"Chesapeake Bay LULC 2024 Edition, Baltimore City 24510 (sciencebase {ITEM})",
                     "url_or_query": url, "retrieved": date.today().isoformat(), "bytes": size,
                     "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "license": LICENSE,
                     "storage": "git" if size <= 25e6 else "local"})
        print(name, size)
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/cc_lulc/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)


if __name__ == "__main__":
    main()
