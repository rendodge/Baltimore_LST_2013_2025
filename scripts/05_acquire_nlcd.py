"""Acquire USGS Annual NLCD Collection 1.2 (CONUS) Land Cover and Fractional Impervious Surface
for Baltimore City.

Source: ScienceBase (Annual NLCD C1.2), one CONUS zip per product per year (~1-1.5 GB; the
server does not support range requests). Each zip is streamed to a temporary file, its
SHA-256 recorded, and the native-grid window (CONUS Albers on WGS 84, 30 m) covering the NSAs + 600 m is
copied unchanged (Albers/WGS 84 as distributed; values, dtype, no-data, colour table). The product XML metadata is kept.
The zip is then deleted; its URL, size and hash go in the manifest.

Run: conda run -p .\\env python scripts\\05_acquire_nlcd.py [years...]   (default 2013 2025)
"""
import csv
import hashlib
import sys
import zipfile
from datetime import date
from pathlib import Path

import geopandas as gpd
import rasterio
import requests
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/nlcd"
TMP = OUT / "_tmp"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
SB = "https://www.sciencebase.gov/catalog/file/get/{item}?name={name}"
PRODUCTS = {"LndCov": "697b9279b66b0197c3043cc3", "FctImp": "697b907eb66b0197c3043c9f"}
BUFFER_M = 600
LICENSE = "USGS public domain"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url, dst):
    part = dst.with_suffix(".part")
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 22):
                f.write(chunk)
    part.replace(dst)


def main(years):
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(exist_ok=True)
    nsa = gpd.read_file(NSA)
    snap = lambda v, up: (((v - 15) // 30) + up) * 30 + 15  # NLCD pixel edges at 15 m mod 30 m

    def window_bounds(crs):
        # Annual NLCD is Albers on WGS 84 (not NAD83 EPSG:5070); use the file's own CRS.
        x0, y0, x1, y1 = nsa.to_crs(crs).total_bounds
        return (snap(x0 - BUFFER_M, 0), snap(y0 - BUFFER_M, 0), snap(x1 + BUFFER_M, 1), snap(y1 + BUFFER_M, 1))

    rows = []
    for prod, item in PRODUCTS.items():
        for y in years:
            name = f"Annual_NLCD_{prod}_{y}_CU_C1V2"
            dst = OUT / f"{name}_baltimore_subset.tif"
            xml = OUT / f"{name}.xml"
            url = SB.format(item=item, name=f"{name}.zip")
            zpath = TMP / f"{name}.zip"
            if not dst.exists():
                if not zpath.exists():  # a zip left by an interrupted run is reused
                    download(url, zpath)
                zbytes, zsha = zpath.stat().st_size, sha256(zpath)
                with zipfile.ZipFile(zpath) as z:
                    members = z.namelist()
                    tif = [m for m in members if m.lower().endswith(".tif") and ".aux" not in m.lower()]
                    assert len(tif) == 1, members
                    xmls = [m for m in members if m.lower().endswith(".xml") and ".aux" not in m.lower()]
                    if xmls:
                        xml.write_bytes(z.read(xmls[0]))
                with rasterio.open(f"/vsizip/{zpath.as_posix()}/{tif[0]}") as src:
                    bounds = window_bounds(src.crs)
                    win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
                    prof = src.profile.copy()
                    prof.update(driver="GTiff", width=win.width, height=win.height,
                                transform=src.window_transform(win), compress="deflate",
                                tiled=True, blockxsize=256, blockysize=256)
                    data = src.read(1, window=win)
                    try:
                        cmap = src.colormap(1)
                    except ValueError:
                        cmap = None
                    with rasterio.open(dst, "w", **prof) as out:
                        out.write(data, 1)
                        if cmap:
                            out.write_colormap(1, cmap)
                (OUT / f"{name}_source_zip.txt").write_text(
                    f"url={url}\nbytes={zbytes}\nsha256={zsha}\nmember={tif[0]}\nwindow_bounds_native_crs={bounds}\n")
                zpath.unlink()
                print(name, "zip", zbytes, "->", dst.name)
            src_info = dict(l.split("=", 1) for l in (OUT / f"{name}_source_zip.txt").read_text().splitlines())
            note = f"{url} (native-grid subset {src_info['window_bounds_native_crs']} of {src_info['member']}; zip {src_info['bytes']} B sha256 {src_info['sha256']})"
            for p, q in [(dst, note), (xml, f"{url} (product XML from zip)"),
                         (OUT / f"{name}_source_zip.txt", "provenance of source zip")]:
                if p.exists():
                    rows.append({"path": p.relative_to(ROOT).as_posix(), "source": "USGS EROS via ScienceBase",
                                 "dataset_id": f"Annual NLCD C1.2 {prod} {y} (doi:10.5066/P94UXNTS)",
                                 "url_or_query": q, "retrieved": date.today().isoformat(),
                                 "bytes": p.stat().st_size, "sha256": sha256(p), "license": LICENSE,
                                 "storage": "local"})
    TMP.rmdir()

    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not any(r["path"] == x["path"] for x in rows)]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)
    print(f"manifest: {len(rows)} nlcd rows")


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2013, 2025])
