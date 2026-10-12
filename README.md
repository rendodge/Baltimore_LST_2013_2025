# Baltimore Summer Land Surface Temperature, 2013–2025

Explores how summer (July–August) land surface temperature (LST) in Baltimore City, MD,
changed from 2013 to 2025, using Landsat 8 thermal imagery (acquired at 100 m), and
investigates how those changes relate to land-cover change from the USGS Annual NLCD. A
neighborhood breakdown and a downloadable PDF report are on the way.

> **Status: exploratory.** The LST trend, weather-normalization, and land-cover analyses run
> end to end; results are preliminary.
>
> **On the way:**
> - Neighborhood breakdown: trends, impervious change, and current heat summarized for each
>   of Baltimore's 279 Neighborhood Statistical Areas (NSAs).
> - A downloadable PDF report with maps, figures, and methods.

## Approach

- **LST:** USGS Landsat Collection 2 Level-2 surface temperature (`ST_B10`), WRS-2 path 15 /
  row 33, Tier 1, July–August 2013–2025, cloud-masked with `QA_PIXEL`. Accessed through the
  Microsoft Planetary Computer STAC catalog.
- **Trends:** one summer-mean composite per year, then per-pixel OLS (with p-values),
  Theil–Sen, and Mann–Kendall, in °C/year.
  - **A — absolute (replicates the original GEE script):** mean of every clear pixel.
  - **B — relative (primary):** only scenes ≥ 50% clear over the city; each scene expressed
    as pixel minus the city median, which removes most of the acquisition-day weather and
    shows where the city changed relative to itself.
  - **C — normalized to BWI air temperature:** removes the luck of which days were clear
    (C1, keeps summer warming) or also the summer air-temperature trend (C2, surface-driven
    change only).
- **Land cover:** USGS Annual NLCD Collection 1.2 land cover and fractional impervious
  surface, 2013 vs 2025, compared with the LST trends by change class and at 90 m blocks.
- **CRS:** EPSG:32618 (WGS 84 / UTM 18N) for all analysis.

Full study design, every consequential decision (with alternatives and reasons), and a dated
process log are in [METHODS.md](METHODS.md).

## Preliminary findings

These are exploratory results and may change.

- With only 1–3 clear Landsat 8 days per summer, the raw city-mean trend
  (+0.25 °C/yr) is driven mostly by which days happened to be clear. Splitting it using BWI
  air temperature gives roughly: summer warming +0.08, sampling luck +0.13, and
  surface-driven change +0.06 °C/yr (not statistically distinguishable from zero).
- Relative LST shows little citywide change but distinct local hotspots. Areas that gained
  ≥ 20 percentage points of impervious surface warmed relative to the city by a median
  +0.20 °C/yr; areas that lost impervious surface show little cooling so far.
- LST is not air temperature, and associations with land cover are not proof of cause.

## Pipeline

Run the scripts in order from the repository root:

| Script | Does |
|---|---|
| `scripts/00_prepare_nsa.py` | Reprojects the NSA boundaries to EPSG:32618 |
| `scripts/01_acquire_landsat.py` | Downloads Landsat 8 ST, QA_PIXEL, ST_QA subsets + MTL/STAC metadata |
| `scripts/02_lst_trend.py` | Annual composites and per-pixel trends (variants A and B) |
| `scripts/03_acquire_bwi.py` | Downloads BWI hourly (ISD) and daily (GHCN-D) weather |
| `scripts/04_lst_bwi_normalized.py` | Air-temperature normalization (variant C) and city trend decomposition |
| `scripts/05_acquire_nlcd.py` | Downloads Annual NLCD land cover and impervious subsets |
| `scripts/06_landcover_lst.py` | Land-cover change vs LST trends |

Outputs go to `data/processed/` and are opened in the QGIS project
`project/baltimore_lst.qgz` (relative paths; styles in `styles/`).

## Setup

Requires [Miniforge](https://github.com/conda-forge/miniforge) (or any conda) and, for maps,
QGIS 3.44 LTR.

```bash
conda env create -p ./env -f environment.yml
```

```bash
conda run -p ./env python scripts/01_acquire_landsat.py
```

Use `conda run` (or activate the env) rather than calling `env/python` directly, so
`GDAL_DATA` is set.

## Data

Large raw files (Landsat subsets, NLCD subsets, NOAA CSVs) are not in git. They are rebuilt
by the acquisition scripts, and every file used is listed in
[data/raw/MANIFEST.csv](data/raw/MANIFEST.csv) with its source, query, retrieval date, size,
and SHA-256. Small provenance files (Landsat MTL/STAC metadata, NLCD metadata) and the NSA
boundaries are committed.

```text
data/raw/        original downloads (never modified) + MANIFEST.csv
data/processed/  derived rasters and tables (not in git; rebuilt by scripts)
data/vector/     NSA boundaries
scripts/         analysis scripts
styles/          QGIS styles
project/         QGIS project
METHODS.md       study design, decisions, process log
```

## Sources and credits

- Landsat imagery courtesy of the U.S. Geological Survey (Landsat Collection 2 Level-2),
  accessed via Microsoft Planetary Computer.
- U.S. Geological Survey, Annual NLCD Collection 1 Science Products,
  [doi:10.5066/P94UXNTS](https://doi.org/10.5066/P94UXNTS) (Collection 1.2).
- NOAA NCEI Global Hourly (ISD) station 72406093721 and GHCN-Daily USW00093721
  (Baltimore–Washington International Airport).
- Neighborhood Statistical Area boundaries: Baltimore City Open GIS Data.
