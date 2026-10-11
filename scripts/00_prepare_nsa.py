"""Reproject the NSA boundaries to the analysis CRS (EPSG:32618) once.

Datum step: NAD83 -> WGS 84 (24) (EPSG:1515 area: Delaware, DC, Maryland; 2 m accuracy),
which is what pyproj selects by default for this area. Writing the reprojected copy means
QGIS needs no on-the-fly datum transformation.

Run: conda run -p .\\env python scripts\\00_prepare_nsa.py
"""
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/vector/Neighborhood_Statistical_Area_(NSA)_Boundaries/Neighborhood_Statistical_Area_(NSA)_Boundaries.shp"
DST = ROOT / "data/vector/nsa_boundaries_32618.gpkg"

nsa = gpd.read_file(SRC)
assert nsa.crs.to_epsg() == 2248, nsa.crs
nsa.to_crs(32618).to_file(DST, layer="nsa", driver="GPKG")
print(f"{len(nsa)} NSAs -> {DST.relative_to(ROOT)}")
