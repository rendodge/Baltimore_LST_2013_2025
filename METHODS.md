# Methods & Process Record — Baltimore Urban Heat Research

The running scientific record of this investigation. **Study design** describes how the
analysis is set up *now* and is edited in place. **Decisions** and **Process log** are
append-only and dated, so the history stays readable. Newest entries go at the bottom.

---

## 1. Study design (current)

| Item | Current choice | Status |
|---|---|---|
| Study area | Baltimore City, MD; Neighborhood Statistical Areas (NSAs) as reporting units | Rural reference ring: **open** |
| Primary LST source | Landsat Collection 2 Level-2 surface temperature (`ST_B10` L8/9, `ST_B6` L5/7), WRS-2 path 15 / row 33 | Set |
| Season | July–August | Set (default) |
| Period of record | 2013–2025, Landsat 8 only (L9 from 2022 as a later sensitivity test) | Exploratory |
| Temporal aggregation | One summer-mean composite per year; per-pixel OLS slope (°C/yr) for trends | Set (default) |
| Land cover | USGS Annual NLCD Collection 1.2 (1985–2025 available); Land Cover + Fractional Impervious, 2013 vs 2025 | Set |
| Vegetation | NDVI from scaled surface reflectance, same season as LST | Set |
| Analysis CRS | EPSG:32618 (WGS 84 / UTM 18N) | Set |
| Cloud/quality masking | `QA_PIXEL` bits 0–5 (incl. cirrus, as in the original GEE script); water not masked; `ST_QA` reported, not thresholded | Threshold **open** |
| Scene filter (variant B) | Scene used only if ≥ 50% of city pixels are clear | Exploratory |
| Trend variable | **B (primary):** relative LST (pixel − scene city median), scenes ≥ 50% clear; A (GEE replication, absolute) kept for comparison only | Set |
| Weather normalization (variant C) | B scenes; LST − b·ΔT_air (BWI METAR at overpass, b fitted with year term). C1 keeps the summer air-temperature trend (removes sampling luck); C2 removes it (surface only) | Exploratory |
| Processing platforms | Planetary Computer STAC → conda env `.\env` scripts → QGIS 3.44 (MCP) | GEE not used (not set up) |

### Datasets

| Dataset | Source / ID | Version or dates | Location in repo |
|---|---|---|---|
| Landsat C2 L2 | USGS via Planetary Computer `landsat-c2-l2`; L8, p15/r33, T1, L2SP, Jul–Aug | 41 scenes 2013–2025 (1 skipped) | `data/raw/landsat/` |
| Annual NLCD | USGS EROS, Collection 1.2, via ScienceBase (doi:10.5066/P94UXNTS); CONUS Albers on WGS 84, 30 m | LndCov, FctImp 2013 & 2025 | `data/raw/nlcd/` |
| NSA boundaries | Baltimore City Open GIS Data (shapefile provided by user, EPSG:2248) | 279 NSAs, file dated 2026-06-28 | `data/vector/Neighborhood_Statistical_Area_(NSA)_Boundaries/` |
| NSA boundaries, UTM | Derived: `scripts/00_prepare_nsa.py` (EPSG:2248 → 32618 via NAD83 to WGS 84 (24)) | — | `data/vector/nsa_boundaries_32618.gpkg` |
| BWI weather | NOAA ISD hourly 72406093721 (2013–2025, FM-15 METAR: air temp, wind); GHCN-Daily USW00093721 (precip) | retrieved 2026-10-11 | `data/raw/noaa/` |

---

## 2. Decisions

Record a decision whenever it could change the results: what was chosen, what the
alternatives were, and why.

### 2026-10-11 — Analysis CRS: EPSG:32618
- **Choice:** UTM 18N for all measurement and overlay work. EPSG:3857 is for display only.
- **Why:** it's native for path 15/row 33 Landsat products, so analysis rasters need no
  reprojection, and its units are metres.

### 2026-10-11 — LST from the USGS Level-2 ST product
- **Choice:** use `ST_B10`/`ST_B6` with scale factors 0.00341802 and +149.0 K.
- **Alternatives:** a single-channel or split-window retrieval from TOA radiance.
- **Why:** the USGS product is emissivity-corrected, validated, and consistent across
  sensors, so there's no need to re-derive it unless the analysis requires it.

### 2026-10-11 — Summer window: July–August
- **Why:** the peak of the heat season, and narrower than June–August, which reduces
  phenology and sun-angle variation between years.
- **Trade-off:** fewer cloud-free observations per year. Check annual counts before
  committing to a period of record.

### 2026-10-11 — Separate conda environment for scripted analysis
- **Choice:** Miniforge plus the project-local env `.\env` (`environment.yml`). QGIS's
  bundled Python is left untouched.
- **Alternatives:** pip-installing into QGIS's Python.
- **Why:** QGIS's Python lacks rasterio, xarray, dask, and STAC clients, and pip-installing
  them risks GDAL conflicts that could break QGIS and the MCP plugin.

### 2026-10-11 — Raw data kept locally, with a manifest
- **Choice:** every source dataset is downloaded unmodified into `data/raw/<source>/` and
  recorded in `data/raw/MANIFEST.csv` (source, ID or query, retrieval date, size, SHA-256,
  license). Files ≤ 25 MB are committed to git. Larger files stay local and can be
  re-acquired from the manifest.
- **Alternatives:** analyzing from remote URLs/STAC only; Git LFS for large rasters.
- **Why:** sources get revised or reprocessed (e.g. Landsat collection updates, municipal
  boundary edits). A local copy plus a checksum pins exactly what the results were computed
  from. Large imagery stays out of git to keep the repo pushable to GitHub.
- **GEE exception:** large collections used server-side in GEE aren't downloaded, but every
  one is listed in the manifest (`storage = remote`) with its collection ID, filter, run date,
  and a committed list of the exact image IDs used. Exports used locally are stored and
  listed like any other file. **Rule: the manifest lists all data used, wherever it lives.**

### 2026-10-11 — Landsat access via Planetary Computer instead of GEE
- **Choice:** query Microsoft Planetary Computer STAC (`landsat-c2-l2`, an unmodified mirror
  of USGS C2 L2) and process locally in `.\env`; display in QGIS.
- **Alternatives:** GEE web editor (original script); GEE Python API.
- **Why:** no new software or account needed, every step is scriptable and inspectable, and
  data are kept locally per the raw-data rule. ~41 clipped scenes is small enough locally.

### 2026-10-11 — Raw Landsat stored as native-grid subsets, not full scenes
- **Choice:** copy only the window covering the NSAs + 450 m (686 × 559 px) from each source
  COG, with values, dtype, no-data and grid unchanged (no resampling). Full MTL and STAC item
  saved alongside; full source URL in the manifest.
- **Why:** full scenes would be ~5 GB for three bands; the subset is bit-identical within the
  window, and all scenes share one 30 m grid (origins ≡ 15 m mod 30).

### 2026-10-11 — Tier 1 only; one scene dropped for a corrupt source file
- **Choice:** T1 and L2SP only (as in the GEE script). `LC08_L2SP_015033_20220804_02_T1`
  (2.3% scene cloud) dropped: its QA_PIXEL object on Planetary Computer is an HTML page,
  not a GeoTIFF (`data/raw/landsat/skipped_scenes.csv`).
- **Consequence:** L8 2022 has only one scene (4% clear), so 2022 is effectively missing.
  Recover by fetching that QA_PIXEL from USGS EarthExplorer (needs a USGS login).

### 2026-10-11 — Two compositing variants computed side by side (exploratory)
- **A (GEE replication):** per-pixel mean of every clear pixel of every scene in Jul–Aug.
- **B (filtered, relative):** scenes ≥ 50% clear over the city only; each scene expressed as
  pixel − city median, then annual mean; OLS (p), Theil–Sen, Mann–Kendall per pixel.
- **Why:** with 1–3 usable dates per year, A mixes different dates in different pixels and
  lets cloud-edge or cloudy-day pixels (e.g. 2014, 2022 with 12% and 4% city coverage at
  ~31 °C) bias slopes. Relative LST removes most of the acquisition-day weather signal, so B
  tests *where the city warmed relative to itself*. Absolute trends remain confounded with
  the weather on the sampled days.
- **Open:** which variant is primary; whether to add L9 (2022+) and ST_QA / water masks.

### 2026-10-11 — Variant B adopted as the primary trend method
- **Choice:** relative LST (pixel − scene city median) from scenes ≥ 50% clear over the city;
  per-pixel OLS with p-values plus Theil–Sen / Mann–Kendall. Variant A kept as a comparison.
- **Alternatives:** A (absolute mean of all clear pixels, the original GEE method).
- **Why:** A's slopes are biased by cloud-sampling artifacts (2014, 2022) and confounded
  with acquisition-day weather; B isolates within-city change. Absolute city warming needs a
  separate weather check (e.g. air temperature on acquisition dates).

### 2026-10-11 — NAD83 → WGS 84 datum transformation for the NSA boundaries
- **Choice:** NAD83 to WGS 84 (24) (Delaware/DC/Maryland, 2 m accuracy), as selected by
  pyproj in the analysis; NSAs stored pre-projected in EPSG:32618 and set as the QGIS
  project default for EPSG:2248 → 32618.
- **Alternatives:** NAD83 to WGS 84 (1) (continental, 4 m), offered by QGIS.
- **Why:** consistency between scripts and QGIS; the two differ by ~0.2 m in central
  Baltimore, negligible relative to 30 m pixels.

### 2026-10-11 — Weather normalization to BWI air temperature (variant C)
- **Choice:** keep the absolute trends (A, B) and add C: scene LST adjusted by
  b·(T_air,scene − reference), with T_air interpolated from BWI METARs to the scene-centre
  time (15:46 UTC). b is fitted on scene city-median LST with a year term
  (`LST ~ T_air + year`) so a real trend is not absorbed into b. C1 uses each year's
  Jul–Aug mean air temperature at 15:46 UTC as reference (removes only sampling luck);
  C2 uses the 2013–2025 mean (also removes the climate trend → surface-driven change).
- **Alternatives:** raw LST − T_air (implies b = 1); per-pixel b (too noisy with 20 scenes);
  adding wind and 3-day precipitation (tested; neither significant, b unchanged 0.72→0.71).
- **Why:** with 1–3 clear days per year the absolute trend mixes climate, the luck of which
  days were clear, and surface change; this separates them.
- **Caveats:** BWI is ~15 km from downtown (regional air, mostly outside the UHI); a single
  citywide b over-corrects vegetated and under-corrects impervious pixels on hot days
  (adds noise, not bias, to the city mean); 20 scenes, so b is uncertain (95% CI 0.41–1.03).

### 2026-10-11 — Annual NLCD C1.2 from ScienceBase, stored as native-grid subsets
- **Choice:** download the CONUS zips from ScienceBase, keep the Baltimore window (NSAs + 600 m)
  on the native grid, record each zip's URL, size and SHA-256, and delete the zip.
- **Alternatives:** MRLC GeoServer WCS (GetCapabilities works but GetCoverage/GetMap returned
  HTTP 500 "Proxy Error" on 2026-10-11); USGS S3 bucket (requester pays, needs AWS account);
  LCMAP on Planetary Computer (older product, ends 2021).
- **Note:** Annual NLCD is CONUS Albers on the **WGS 84** datum, not EPSG:5070 (NAD83);
  subsets are kept in the distributed CRS.

### 2026-10-11 — Land-cover/LST comparison design
- **Choice:** NLCD 2013 and 2025 (matching the LST record) resampled onto the Landsat UTM
  grid (land cover: nearest neighbour; impervious: bilinear). Change expressed as class
  transitions (matrix, and grouped change classes built from class codes) and Δ impervious
  (pp). LST trends compared by class and regressed on Δ impervious at 90 m blocks (3×3,
  ≥ 7 valid pixels) to approach the 100 m thermal resolution. Open water excluded.
- **Alternatives:** annual NLCD series with year-of-change (step) models — more powerful,
  deferred; Chesapeake Conservancy 1 m land cover — finer, not yet justified.
- **Caveat:** 90 m blocks are still spatially autocorrelated; regression p-values are
  optimistic. Effect sizes and class medians are the robust outputs.

---

## 3. Process log

Add a dated entry for setup changes and for any run that produces a final dataset or figure.
Record the inputs, the script or tool, the outputs, and key numbers. Quick exploratory steps
don't need an entry.

### 2026-10-11 — Project setup
- Created the git repo (`main`), `.gitignore` (rasters, bulky vectors, archives, `env/`
  excluded), and `CLAUDE.md` (working rules).
- Confirmed the QGIS MCP connection (`ping` → pong). QGIS 3.44.15-Solothurn, Python 3.12.15.
- Installed Miniforge 26.7.2 (`winget`, user scope) at `C:\Users\rendo\miniforge3`.
- Created `.\env` from `environment.yml`. Key versions:
  - Python 3.12.15, GDAL 3.13.3, rasterio 1.5.2, pyproj 3.8.0, shapely 2.2.0, geopandas 1.2.0
  - numpy 2.5.4, xarray 2026.9.0, rioxarray 0.23.0, dask 2026.8.0
  - pystac-client 0.9.0, planetary-computer 1.0.0, odc-stac 0.5.3
  - scipy 1.18.1, pandas 3.0.6, statsmodels 0.15.0, scikit-learn 1.9.1, matplotlib 3.11.2
- Verified the env by writing a float32 DEFLATE COG in EPSG:32618 and reading it back with
  rioxarray (CRS and values matched). `GDAL_DATA` is set only when the env is run via
  `conda run`/activation.

### 2026-10-11 — Landsat 8 acquisition and exploratory trend run
- `scripts/01_acquire_landsat.py`: 42 scenes matched (L8, p15/r33, T1, L2SP, Jul–Aug
  2013–2025); 41 downloaded (ST_B10, QA_PIXEL, ST_QA subsets + MTL + STAC JSON), 1 skipped
  (corrupt source). 205 manifest rows. NSA shapefile added to manifest (6 rows).
- `scripts/02_lst_trend.py` → `data/processed/lst_trend/` (exploratory, no sidecars yet).
  20 of 41 scenes pass the ≥ 50% clear filter; B has no data for 2014 or 2022 (n = 11 years).
- City mean LST trend: A +0.30 °C/yr (p = 0.24, n = 13, distorted by cloudy 2014/2022);
  B on fixed pixels +0.25 °C/yr (p = 0.004, n = 11) — absolute, so weather-confounded.
- Pixel trends: A median +0.25 °C/yr, 29% of pixels p < 0.05; B relative median −0.03 °C/yr,
  9.7% p < 0.05 (3.6% warming, 6.1% cooling; ~5% expected by chance, pixels autocorrelated).
- QGIS project `project/baltimore_lst.qgz`; styles in `styles/`.

### 2026-10-11 — BWI weather acquisition and variant C run (exploratory)
- `scripts/03_acquire_bwi.py`: 13 ISD yearly CSVs + GHCN-D CSV → `data/raw/noaa/`
  (14 manifest rows). 2025 Jul–Aug has 57 of 62 days with a valid 15:46 UTC interpolation.
- `scripts/04_lst_bwi_normalized.py` → `data/processed/lst_trend/C*_*.tif`,
  `C_scene_weather.csv`, `C_city_timeseries.csv`, `C_city_decomposition.json/png`.
- b = 0.72 °C LST per °C air (95% CI 0.41–1.03, R² 0.63, n = 20 scenes).
- City trend on fixed common pixels (11 years), observed +0.25 °C/yr (p = 0.004) splits into
  climate +0.08, sampling +0.13, surface +0.06 °C/yr (surface p = 0.61, 95% CI ±0.20).
  C1 (climate + surface) +0.13 °C/yr (p = 0.19). Components sum to 0.257 vs 0.249 observed
  (pixel-level clear-sky weighting differs slightly between years).
- Air temperature at 15:46 UTC, all Jul–Aug days: +0.11 °C/yr over the 11 B years
  (p = 0.18); +0.16 °C/yr over 2013–2025 (p = 0.04). Overpass days alone: +0.28 °C/yr.
- Pixels: C1 median +0.13 °C/yr (9.7% significant warming, 0.3% cooling); C2 median
  +0.04 °C/yr (2.6% / 2.1%, i.e. at chance level).

### 2026-10-11 — Annual NLCD acquisition and land-cover vs LST trend run (exploratory)
- `scripts/05_acquire_nlcd.py`: LndCov and FctImp 2013, 2025 (4 zips, 0.92–1.46 GB, sizes
  match ScienceBase) → `data/raw/nlcd/` subsets 692 × 663 (12 manifest rows).
- `scripts/06_landcover_lst.py` → `data/processed/landcover/` (UTM rasters, transition
  matrix, `lst_trend_by_change_class.csv`, `summary.json`, preview PNG).
- City 210.3 km²; 8.1 km² (3.8%) changed class; mean impervious 54.7% → 54.4%. Area with
  Δimp ≥ +5 pp 4.6 km², ≤ −5 pp 11.3 km² (de-intensification 4.8 km² by class).
- Relative LST trend (B) median by Δimp: ≥ +20 pp +0.20 °C/yr (1.3 km²); +5–20 pp +0.02;
  stable −0.03; −5 to −20 pp −0.04; ≤ −20 pp −0.02. Vegetated→developed +0.12 °C/yr (0.44 km²).
- 90 m blocks: +0.064 °C/yr per 10 pp Δimp (r = 0.16, n = 25,429); C1/C2 similar
  (+0.066 / +0.068). Over 12 yr → +0.77 °C per 10 pp gained vs cross-sectional
  +1.40 °C per 10 pp (r = 0.89).
