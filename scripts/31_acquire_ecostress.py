"""Acquire ECOSTRESS tiled LST (ECO_L2T_LSTE v002, 70 m, MGRS tile 18SUJ) over Baltimore, June-August.

Granules from NASA CMR (bounding box of the city, 2018-07 to 2025-08, months 6-8, all hours). For each
granule the LST, cloud and QC GeoTIFFs are downloaded from LP DAAC with an Earthdata Login bearer
token read from %USERPROFILE%\\.edl_token (created by the user; never printed or stored elsewhere),
clipped to the NSA bounds + 1 km on the native 70 m grid (EPSG:32618, values unchanged), and the full
tile is discarded. Subsets go to data/raw/ecostress/<granule>/ and are listed in data/raw/MANIFEST.csv.

Run: conda run -p .\\env python scripts\\31_acquire_ecostress.py
"""
import csv
import hashlib
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import geopandas as gpd
import pandas as pd
import rasterio
import requests
from rasterio.io import MemoryFile
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/ecostress"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
LAYERS = ("LST", "cloud", "QC")
BUFFER_M = 1000
WORKERS = 4


def granules():
    rows, page = [], 1
    while True:
        r = requests.get(CMR, params={"short_name": "ECO_L2T_LSTE", "version": "002",
                                      "bounding_box": "-76.71,39.20,-76.53,39.37",
                                      "temporal": "2018-07-01T00:00:00Z,2025-08-31T23:59:59Z",
                                      "page_size": 2000, "page_num": page}, timeout=120).json()
        items = r.get("items", [])
        for it in items:
            u = it["umm"]
            t = pd.Timestamp(u["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"])
            if t.month in (6, 7, 8):
                urls = {x["URL"].split("_")[-1].replace(".tif", ""): x["URL"] for x in u["RelatedUrls"]
                        if x.get("Type") == "GET DATA" and x["URL"].endswith(".tif")}
                rows.append({"granule": u["GranuleUR"], "time_utc": t, **{k: urls.get(k) for k in LAYERS}})
        if len(items) < 2000:
            break
        page += 1
    return pd.DataFrame(rows)


def fetch(session, g, bounds):
    d = OUT / g.granule
    out = []
    for k in LAYERS:
        dst = d / f"{g.granule}_{k}_subset.tif"
        if not dst.exists():
            r = session.get(getattr(g, k), timeout=300)
            r.raise_for_status()
            with MemoryFile(r.content) as mf, mf.open() as src:
                win = from_bounds(*bounds, transform=src.transform).round_offsets().round_lengths()
                prof = src.profile.copy()
                prof.update(driver="GTiff", width=win.width, height=win.height, transform=src.window_transform(win),
                            compress="deflate", tiled=False)
                prof.pop("blockxsize", None)
                prof.pop("blockysize", None)
                data = src.read(window=win, boundless=True)
                d.mkdir(parents=True, exist_ok=True)
                with rasterio.open(dst, "w", **prof) as o:
                    o.write(data)
        out.append((dst, getattr(g, k)))
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    nsa = gpd.read_file(NSA)
    b = nsa.total_bounds
    bounds = (b[0] - BUFFER_M, b[1] - BUFFER_M, b[2] + BUFFER_M, b[3] + BUFFER_M)
    gs = granules()
    gs.to_csv(OUT / "granules_jja.csv", index=False)
    print(f"{len(gs)} June-August granules")
    token = (Path.home() / ".edl_token").read_text().strip()
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token}"  # requests drops it on cross-host redirects
    files, failed = [], []
    with ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(fetch, session, g, bounds): g.granule for g in gs.itertuples(index=False)}
        for i, f in enumerate(as_completed(futs)):
            try:
                files += f.result()
            except Exception as e:  # keep going; report at the end
                failed.append((futs[f], str(e)[:120]))
            if i % 50 == 0:
                print(i, "granules done", flush=True)
    rows = [{"path": p.relative_to(ROOT).as_posix(), "source": "NASA LP DAAC (ECOSTRESS)",
             "dataset_id": "ECO_L2T_LSTE v002 tile 18SUJ", "url_or_query": f"{u} (native-grid subset, NSAs + {BUFFER_M} m)",
             "retrieved": date.today().isoformat(), "bytes": p.stat().st_size,
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "license": "NASA open data", "storage": "local"}
            for p, u in files]
    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/ecostress/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)
    print(f"{len(files)} files written; {len(failed)} granules failed")
    for g, e in failed[:10]:
        print("  failed:", g, e)


if __name__ == "__main__":
    main()
