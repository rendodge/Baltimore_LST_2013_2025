"""NAIP aerial imagery around candidate redevelopment NSAs, for visual verification of LST steps.

Source: Microsoft Planetary Computer collection `naip` (USDA NAIP, 4-band RGB+NIR). Years over
Baltimore: 2013, 2015, 2017 (1 m), 2018 (0.6 m, November = leaf-off), 2021 (0.6 m), 2023 (0.3 m).
For each NSA below and each year, the tiles intersecting the NSA bounds + 150 m are mosaicked and
clipped. 2013-2021 are read at native resolution; 2023 is read at 0.6 m from the source COG's
internal overview to limit size (documented in the manifest). Values unchanged otherwise.
Outputs: data/raw/naip/<year>/naip_<year>_<nsa>.tif (+ manifest rows), and a per-NSA strip of
RGB thumbnails with the NSA outline in figures/naip/.

Run: conda run -p .\\env python scripts\\28_acquire_naip.py
"""
import csv
import hashlib
from datetime import date
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import planetary_computer as pc
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.plot import plotting_extent

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/naip"
FIG = ROOT / "figures/naip"
MANIFEST = ROOT / "data/raw/MANIFEST.csv"
NSA = ROOT / "data/vector/nsa_boundaries_32618.gpkg"
TARGETS = {"Perkins": 2023, "McElderry Park": 2016, "Biddle Street": 2016, "Broadway East": 2019,
           "Cherry Hill": 2021, "Middle Branch/Reedbird Parks": 2021, "Orchard Ridge": 2017}  # NSA: first year after step
YEARS = [2013, 2015, 2017, 2018, 2021, 2023]
RES = {2023: 0.6}
BUFFER_M = 150
slug = lambda s: s.lower().replace("/", "-").replace(" ", "_")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    nsa = gpd.read_file(NSA)
    cat = pystac_client.Client.open("https://planetarycomputer.microsoft.com/api/stac/v1")
    rows = []
    for name in TARGETS:
        poly = nsa[nsa.Name == name]
        assert len(poly) == 1, name
        for y in YEARS:
            dst = OUT / str(y) / f"naip_{y}_{slug(name)}.tif"
            bbox_ll = poly.buffer(BUFFER_M).to_crs(4326).total_bounds.tolist()
            items = [it for it in cat.search(collections=["naip"], bbox=bbox_ll, datetime=f"{y}-01-01/{y}-12-31").items()
                     if it.properties.get("naip:state") == "md"]
            if not items:
                print("no NAIP", name, y)
                continue
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                srcs = [rasterio.open(pc.sign(it).assets["image"].href) for it in items]
                crs = srcs[0].crs
                b = poly.buffer(BUFFER_M).to_crs(crs).total_bounds
                res = RES.get(y, srcs[0].res[0])
                arr, tr = merge(srcs, bounds=tuple(b), res=res, resampling=Resampling.average if y in RES else Resampling.nearest)
                prof = srcs[0].profile.copy()
                prof.update(driver="GTiff", height=arr.shape[1], width=arr.shape[2], transform=tr, count=arr.shape[0],
                            compress="deflate", tiled=True, blockxsize=512, blockysize=512, photometric="RGB" if arr.shape[0] == 3 else None)
                prof = {k: v for k, v in prof.items() if v is not None}
                with rasterio.open(dst, "w", **prof) as out:
                    out.write(arr)
                for s_ in srcs:
                    s_.close()
            rows.append({"path": dst.relative_to(ROOT).as_posix(), "source": "USDA NAIP via Microsoft Planetary Computer",
                         "dataset_id": "naip/" + ";".join(sorted(it.id for it in items)),
                         "url_or_query": f"STAC naip, bbox of NSA '{name}' + {BUFFER_M} m, {y}"
                                         + (f"; read at {RES[y]} m from COG overview" if y in RES else "; native resolution"),
                         "retrieved": date.today().isoformat(), "bytes": dst.stat().st_size, "sha256": sha256(dst),
                         "license": "USDA NAIP public domain", "storage": "local"})
            print(name, y, len(items), "tiles ->", dst.name, f"{dst.stat().st_size / 1e6:.1f} MB")

    with open(MANIFEST, newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        keep = [r for r in reader if not r["path"].startswith("data/raw/naip/")]
    with open(MANIFEST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(keep + rows)

    # thumbnail strips (true colour) with the NSA outline
    FIG.mkdir(parents=True, exist_ok=True)
    for name, step in TARGETS.items():
        fig, axs = plt.subplots(1, len(YEARS), figsize=(4.2 * len(YEARS), 4.8))
        for ax, y in zip(axs, YEARS):
            p = OUT / str(y) / f"naip_{y}_{slug(name)}.tif"
            ax.set_axis_off()
            if not p.exists():
                continue
            with rasterio.open(p) as s:
                f = max(1, int(max(s.width, s.height) / 1200))
                rgb = s.read([1, 2, 3], out_shape=(3, s.height // f, s.width // f)).astype(float)
                ext = plotting_extent(s)
                crs = s.crs
            lo, hi = np.percentile(rgb[rgb > 0], [2, 98])
            ax.imshow(np.clip((rgb - lo) / (hi - lo), 0, 1).transpose(1, 2, 0), extent=ext)
            nsa[nsa.Name == name].to_crs(crs).boundary.plot(ax=ax, color="yellow", lw=1.4)
            mark = " (before)" if y < step else " (after)"
            ax.set_title(f"{y}{mark}" + (" leaf-off" if y == 2018 else ""), fontsize=14)
        fig.suptitle(f"{name}: NAIP true colour; LST step detected starting {step}", fontsize=16)
        fig.tight_layout()
        fig.savefig(FIG / f"naip_strip_{slug(name)}.png", dpi=110)
        plt.close(fig)


if __name__ == "__main__":
    main()
