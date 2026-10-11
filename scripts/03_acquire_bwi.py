"""Download BWI airport weather observations (unmodified) into data/raw/noaa/.

- NOAA Global Hourly / ISD, station 72406093721 (KBWI), one CSV per year 2013-2025
  (NOAA open data on AWS, bucket noaa-global-hourly-pds).
- NOAA GHCN-Daily, station USW00093721 (BWI), full-record CSV.
Each file is appended to data/raw/MANIFEST.csv (rows for these paths are replaced).

Run: conda run -p .\\env python scripts\\03_acquire_bwi.py
"""
import csv
import hashlib
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/noaa"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
ISD = "https://noaa-global-hourly-pds.s3.amazonaws.com/{y}/72406093721.csv"
GHCND = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/USW00093721.csv"
LICENSE = "NOAA public domain"


def fetch(url, dst):
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    dst.write_bytes(r.content)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(ISD.format(y=y), OUT / f"isd_72406093721_{y}.csv", "NOAA Global Hourly (ISD) 72406093721")
            for y in range(2013, 2026)]
    jobs.append((GHCND, OUT / "ghcnd_USW00093721.csv", "NOAA GHCN-Daily USW00093721"))
    rows = []
    for url, dst, dsid in jobs:
        if not dst.exists():
            fetch(url, dst)
        rows.append({"path": dst.relative_to(ROOT).as_posix(), "source": "NOAA NCEI", "dataset_id": dsid,
                     "url_or_query": url, "retrieved": date.today().isoformat(), "bytes": dst.stat().st_size,
                     "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "license": LICENSE,
                     "storage": "local"})
        print(dst.name, dst.stat().st_size)
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/noaa/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)


if __name__ == "__main__":
    main()
