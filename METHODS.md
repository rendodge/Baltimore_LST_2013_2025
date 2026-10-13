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
| Season | July–August (primary); year-round analysis added (`scripts/24_allyear_trends.py`: all months, harmonic seasonal model + per-season trends) | Set |
| Period of record | 2013–2025, **Landsat 8 only for all analyses** (user decision 2026-10-11, after the L9 contrast check); L8 + L9 products kept as replication only | Set |
| Sensor configuration | `LST_SENSORS=LC08,LC09` → `data/processed/lst_trend_lc08_lc09/`; default (L8) → `data/processed/lst_trend/`. Weather fit includes a sensor term; no L9 offset correction | Set |
| Temporal aggregation | One summer-mean composite per year; per-pixel OLS slope (°C/yr) for trends | Set (default) |
| Land cover | USGS Annual NLCD Collection 1.2 (1985–2025 available); Land Cover + Fractional Impervious, 2013 vs 2025 | Set |
| Vegetation | NDVI from scaled SR_B4/SR_B5 (ρ = DN × 0.0000275 − 0.2), same QA mask, variant-B scenes and Jul–Aug composites as LST (`scripts/22_ndvi_trend.py`) | Set |
| Analysis CRS | EPSG:32618 (WGS 84 / UTM 18N) | Set |
| Cloud/quality masking | `QA_PIXEL` bits 0–5 (incl. cirrus, as in the original GEE script); water not masked; `ST_QA` reported, not thresholded | Threshold **open** |
| Scene filter (variant B) | Scene used only if ≥ 50% of city pixels are clear | Exploratory |
| Trend variable | **B (primary):** relative LST (pixel − scene city median), scenes ≥ 50% clear; A (GEE replication, absolute) kept for comparison only | Set |
| Weather normalization (variant C) | B scenes; LST − b·ΔT_air (BWI METAR at overpass, b fitted with year term). C1 keeps the summer air-temperature trend (removes sampling luck); C2 removes it (surface only) | Exploratory |
| Processing platforms | Planetary Computer STAC → conda env `.\env` scripts → QGIS 3.44 (MCP) | GEE not used (not set up) |

### Datasets

| Dataset | Source / ID | Version or dates | Location in repo |
|---|---|---|---|
| Landsat C2 L2 | USGS via Planetary Computer `landsat-c2-l2`; L8 and L9, p15/r33, T1, L2SP | L8 all months: 224 scenes Apr 2013–Dec 2025 (1 skipped; 41 in Jul–Aug); L9 Jul–Aug: 15 scenes 2022–2025 | `data/raw/landsat/` |
| Annual NLCD | USGS EROS, Collection 1.2, via ScienceBase (doi:10.5066/P94UXNTS); CONUS Albers on WGS 84, 30 m | LndCov, FctImp 2013 & 2025 | `data/raw/nlcd/` |
| NSA boundaries | Baltimore City Open GIS Data (shapefile provided by user, EPSG:2248) | 279 NSAs, file dated 2026-06-28 | `data/vector/Neighborhood_Statistical_Area_(NSA)_Boundaries/` |
| NSA boundaries, UTM | Derived: `scripts/00_prepare_nsa.py` (EPSG:2248 → 32618 via NAD83 to WGS 84 (24)) | — | `data/vector/nsa_boundaries_32618.gpkg` |
| BWI weather | NOAA ISD hourly 72406093721 (2013–2025, FM-15 METAR: air temp, wind); GHCN-Daily USW00093721 (precip) | retrieved 2026-10-11 | `data/raw/noaa/` |
| Median household income | BNIA Vital Signs by Community Statistical Area (55 CSAs; ACS 5-yr, nominal $); file provided by user, EPSG:2248 | 2006–10 … 2019–23 | `data/Median_Household_Income_-_Community_Statistical_Area/` |
| Streams (hyper-resolution) | Chesapeake Bay Hyper-Resolution Hydrography, HUC8 02060003 streamLine (CC/UMBC, ScienceBase 679cfd13d34e89501cd2d6ed, pub. 2025-05-23), clipped to city | source imagery 2008–2021 | raw `data/raw/streams/`; city `data/vector/streams_cc_city.gpkg` |
| Streams (NHD) | USGS NHD High Resolution HU8 02060003 NHDFlowline (pub. 2023-12-15), clipped to city | — | raw `data/raw/streams/`; city `data/vector/streams_nhd_city.gpkg` |
| Terrain | USGS 3DEP 1/3 arc-second DEM tile n40w077 (Planetary Computer `3dep-seamless`, native-grid window); CC geomorphon 10 m, HUC8 02060003 (ScienceBase S3) | DEM source 2014 | `data/raw/terrain/` |
| NAIP aerial imagery | USDA NAIP via Planetary Computer (`naip`), clips around 7 candidate NSAs | 2013, 2015, 2017 (1 m), 2018 (0.6 m, leaf-off), 2021 (0.6 m), 2023 (read at 0.6 m from 0.3 m) | `data/raw/naip/` (local) |
| Chesapeake Conservancy LULC | 1 m, 56-class LULC 2024 Edition, Baltimore City (ScienceBase 68011bd8d4be0263cab0ff37); ESRI:102039 (NAD83 Albers) | 2013/14, 2017/18, 2021/22 | `data/raw/cc_lulc/` |

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

### 2026-10-11 — Chesapeake 1 m LULC as top-of-surface cover fractions on the Landsat grid
- **Choice:** 8 groups from the 56 CC classes (canopy, structures, roads, other impervious,
  turf, bare, herbaceous/shrub, water), aggregated from 1 m directly to the 30 m Landsat UTM
  grid by area-weighted averaging (one resampling step); analysed at 90 m blocks. Tree canopy
  over impervious/turf counts as canopy (what the thermal sensor sees). Periods 2013/14 and
  2021/22 (closest CC periods to the 2013–2025 LST record).
- **Change model:** LST trend ~ Δ each cover group, turf omitted as reference (fractions sum
  to 100%), so coefficients = effect of 10 pp of that cover replacing turf. Blocks need full
  CC coverage in both periods and < 10% water. Thinned grid (every 4th block) as a rough
  autocorrelation check.
- **Why:** NLCD showed warming with impervious gain but no cooling with loss; CC separates
  roofs, pavement, canopy, turf, bare and herbaceous cover, to test what replaced the loss.
- **Caveats:** CC change periods (8 yr) differ from the 12-yr LST trend; CC and NLCD disagree
  on where impervious changed (r = 0.27 at 90 m); classification differences between CC
  editions/years can create apparent change.

### 2026-10-11 — Q2 design: cover state vs LST trend on stable blocks
- **Choice:** 90 m blocks with < 2 pp change in every CC cover group (2013/14 → 2021/22),
  full CC coverage, < 10% water; cover state = 2013/14 fractions. Trends compared by
  impervious and canopy deciles and by an ordered cover typology (canopy ≥ 50% → roofs ≥ 35%
  → roads + other impervious ≥ 50% → turf ≥ 35% → herbaceous/shrub ≥ 35% → mixed). 95% CIs from
  a spatial block bootstrap (1 km tiles, 1000 resamples). Per-type weather-adjusted trends
  from scene medians: LST ~ T_air + year, and type gap ~ T_air + year.
- **Why:** separates "did places with a given cover warm differently" (Q2) from cover-change
  effects (Q3); typology thresholds chosen from the stable-block distributions.
- **Note:** B and C1 differ by a per-scene constant, so between-type differences are nearly
  the same in both; only the level differs.

### 2026-10-11 — Landsat 9 used to replicate, not (yet) merged into the primary series
- **Choice:** keep L8-only results as primary; use L9 (2022–2025) for (A) sensor agreement,
  (B) an independent change test (late-period change from L8 vs from L9, each against a
  disjoint set of L8 baseline years: odd vs even 2013–2021), and (C) trend variants
  L8 + L9 and "swap" (L8 to 2021, L9 only from 2022).
- **Why:** adding L9 doubles recent observations mid-series (a known source of bias in
  trends); replication first establishes whether the sensors agree and which spatial
  patterns are reproducible.
- **No L9 offset correction applied:** estimated L9 − L8 offset +0.63 °C, 95% CI −1.3 to +2.6
  (n = 28 scenes) — not distinguishable from zero; relative-LST results are immune to it.

### 2026-10-11 — Landsat 8 + 9 adopted as the primary scene set (user decision)
- **Choice:** variant B (≥ 50% clear, relative LST) and C1/C2 computed from L8 + L9; the
  L8-only products are kept unchanged for comparison.
- **Why:** the replication showed the sensors agree (no detectable offset; relative pattern
  r = 0.97) and the key results reproduce; L9 fills 2022 and adds 8 usable scenes (28 vs 20).
- **Consequences:** 12 years with data instead of 11; b refitted with a sensor term
  (0.81, 95% CI 0.59–1.04). Mid-series change in observation density (L9 from 2022) remains a
  caveat for trends. Downstream analyses (06, 07, 10, 11) still read the L8-only products
  until rerun.

### 2026-10-11 — Landsat 8 only for everything (user decision; supersedes L8 + 9 as primary)
- **Choice:** all analyses (trend maps, NSA summaries, cover comparisons, city trend) use
  Landsat 8 only. L8 + L9 products (`data/processed/lst_trend_lc08_lc09/`,
  `data/processed/l9_replication/`) are kept as replication only and labelled as such in QGIS.
- **Alternatives:** L8 primary for spatial work with L8 + L9 for the city trend; per-pixel
  scene-level model with a sensor term (harmonization).
- **Why:** L9 scenes show lower hot–cool contrast than L8 for the same date and air temperature
  (−0.84 °C, p = 0.065), and adding them only at the end of the record produced artificial
  hot/cool convergence across NSAs (trend vs mean relative LST: −0.44 with L9, −0.16 without).
  A single consistent sensor avoids the issue.

### 2026-10-11 — Income comparison at CSA level, not NSA
- **Choice:** compare BNIA median household income (2019–2023 ACS) with LST metrics recomputed
  for each of the 55 CSAs from the pixels (same series-trend method as the NSA summary).
- **Alternatives:** assign CSA income to NSAs (279 points sharing 55 income values —
  pseudo-replication; ~80 NSAs straddle CSA boundaries); ACS block groups reallocated to NSAs
  via 2020 blocks (Census API now requires a key — not set up).
- **Note:** median, not mean, household income; ACS margins of error are not in the BNIA file.

### 2026-10-11 — Stream effect tested against terrain and surrounding cover
- **Choice:** OLS of mean relative LST on 90 m blocks with distance-to-open-channel bins
  (reference 450–1000 m), SEs clustered by 1 km tile, under three adjustments: own-block cover;
  + terrain (elevation, slope, TPI 300 m / 1 km, solar illumination at overpass, geomorphon
  valley / ridge shares); + surrounding canopy and impervious (3×3 and 7×7 blocks ≈ 270 / 630 m).
- **Why:** stream valleys are low-lying and lie within large forested parks; park cooling and
  the ~100 m thermal footprint extend beyond a block's own cover.
- **Caveat:** surrounding-cover terms absorb both physical spillover (park cool islands) and
  sensor blur; they cannot be separated here.

### 2026-10-11 — Robustness to individual scenes: haze flag and leave-one-scene-out
- **Choice:** flag scenes whose thermal or NDVI contrast is ≤ −2 SD below the day-of-year
  expectation; recompute key results without them, and run a leave-one-scene-out jackknife
  over the 20 variant-B scenes. Results are kept with all scenes; the jackknife range is
  reported alongside each headline number.
- **Why:** each year rests on 1–3 scenes, so single scenes (haze, weather) can drive trends.

### 2026-10-12 — Year-round trends: harmonic seasonal model (user choices)
- **Choice:** all Landsat 8 months, scenes ≥ 50% clear (101 scenes: DJF 16, MAM 29, JJA 24,
  SON 32). Per-pixel and per-NSA harmonic regression (trend + annual + semi-annual terms) on
  relative LST and on BWI-normalized LST with season-specific LST–air sensitivity (C1, C2);
  per-season composite trends; city trends from scene medians with season-year-clustered SEs.
  Significance also checked with a stricter test (de-seasonalized annual means, one value per
  season-year, OLS), because scene-level and 13–14-cluster tests are optimistic.
- **Alternatives:** simple annual means (biased by the seasonal mix of clear scenes);
  per-season composites only (winter has no clear scene in 4 years).
- **Safeguard:** `load_scenes()` now defaults to months (7, 8), so summer analyses are
  unchanged by the all-month download (verified: 41 scenes, 20 used).

### 2026-10-12 — Riparian buffer width definition
- **Choice:** at points every 150 m on open CC channels, continuous forested buffer width = outer
  edge of the last 1 m-derived distance band (0–10, 10–20, 20–30, 30–50, 50–75, 75–100, 100–150,
  150–200, 200–300 m) such that every band from the channel outward has ≥ 50% canopy (both banks
  combined; water excluded). Outcomes: Jul–Aug mean relative LST ≤ 45 m from the channel and
  100–200 m away; control: impervious share 300–600 m from the point; SEs clustered by 1 km tile.
- **Caveat:** thermal data are acquired at ~100 m, so differences between narrow buffers
  (< ~50–100 m total) are only partly resolvable; the detected threshold is partly set by the sensor.

### 2026-10-12 — Step detection on year-round relative LST
- **Choice:** per 90 m block and per NSA, de-seasonalized (harmonic part removed) annual means of
  relative LST (13 years, ≥ 2 scenes/yr, ≥ 11 years); single step at 2015–2023 (≥ 2 years each
  side); sup-F calibrated by 20,000 white-noise simulations (5%); classed as a step only if it
  also fits better than a linear trend.
- **Caveat:** the white-noise calibration ignores spatially shared year effects; citywide step
  frequency (23%) and a 2018 cluster show it is too liberal at block level. Block step years are
  leads to verify, not dates of events.

### 2026-10-12 — CORRECTION: buffer width is a per-side distance
- The 2026-10-12 buffer-width entries described the width as "total across both banks". The
  distance bands were measured from the channel with both banks pooled, so the width is a
  **per-side** distance (corridor total ≈ 2×). Corrected reading: significant corridor cooling
  from 50–100 m per side (≈ 100–200 m total corridor); hinge ≈ 70 m per side. Figure and script
  labels fixed; per-bank widths are measured explicitly in the deep dive (`scripts/29`–`30`).

### 2026-10-12 — ECOSTRESS added as a secondary thermal source (buffer deep dive)
- **Choice:** ECO_L2T_LSTE v002 (70 m, tile 18SUJ), June–August 2018–2025, all overpass times;
  pixels kept where cloud == 0, QC mandatory bits ≤ 1, 250–350 K; scenes ≥ 50% city clear; relative
  LST (pixel − scene city median); local-time bins (EDT). Used only to test time of day and finer
  resolution for the buffer question; Landsat 8 stays primary.
- **Alternatives:** Landsat only (one overpass ≈ 10:40 local, 100 m); MODIS (1 km, too coarse).
- **Caveats:** different period (2018–25) and months (Jun–Aug vs Jul–Aug); ECOSTRESS geolocation
  error (tens of metres) and variable view angle blur narrow corridors; uneven bin sizes (20–43 scenes).

### 2026-10-12 — Interpreting the buffer-width "threshold" with a sensor blur model
- **Choice:** a 1-D cross-section simulation (box footprint + Gaussian blur, distributed grid)
  gives the fraction of a true corridor anomaly each sensor records versus buffer width; the
  apparent threshold is compared with this attenuation curve before being read as physical.
- **Consequence:** the observed fall-off (≈ 24/57/87% of plateau cooling at 10–30/30–50/50–100 m
  per side) is similar to Landsat's expected capture (15/42/64/84/95% at 10/30/50/75/100 m), so the
  hinge (~60 m per side) cannot be claimed as a physical minimum width. Claim: cooling scales with
  forested width up to ~100 m per side; no evidence of a benefit beyond that.

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

### 2026-10-11 — Chesapeake Conservancy 1 m LULC added (display only so far)
- `scripts/08_acquire_cc_lulc.py`: three city GeoTIFFs (2013, 2018, 2021; ~37 MB each, stored
  unmodified, `storage = local`) + product XML → `data/raw/cc_lulc/`.
- Display: VRTs with mode-resampled overviews in `data/processed/cc_lulc/` (raw files
  untouched); QGIS group with a family-grouped palette from the XML class list
  (`styles/cc_lulc_palette.qml`; not the official CC symbology). ESRI:102039 → EPSG:32618 set
  to NAD83 to WGS 84 (24) in the project, as for the NSAs.
- Project CRS had been switched to EPSG:2248; reset to EPSG:32618.
- Not yet used in any analysis. Periods (2013/14, 2017/18, 2021/22) differ from the NLCD
  endpoints (2013, 2025).

### 2026-10-11 — CC cover fractions and cover-change vs LST run (exploratory)
- `scripts/09_cc_fractions.py` → `data/processed/cc_lulc/cc_frac_<group>_<year>_utm.tif`;
  groups sum to 100% in fully covered cells. Means 2013/14 → 2021/22 over the 25,013 blocks
  used (< 10% water): canopy 28.6 → 28.2%, impervious (structures+roads+other) 49.5 → 50.4%.
- `scripts/10_cc_change_lst.py` → `cc_change_regression.csv`, `cc_change_replacement.csv`,
  `cc_change_summary.json`, Δ canopy / Δ impervious rasters, preview PNG. 25,013 blocks.
- Cross-section (mean relative LST, r² = 0.79), °C per 10 pp replacing turf: structures
  +1.03, roads +0.76, other impervious +0.68, bare +0.38, herbaceous +0.01 (ns), canopy −0.51.
- Change (relative trend B, r² = 0.05), °C/yr per 10 pp replacing turf: structures +0.055
  (thinned +0.049, p < 1e-6), other impervious +0.031 (thinned +0.035, p < 1e-4), canopy
  −0.014 (thinned −0.005, ns), bare +0.013 (thinned p = 0.08), roads and herbaceous ns.
  C2 gives the same pattern.
- Impervious loss ≥ 5 pp by dominant replacement (median B trend; stable −0.030):
  → herbaceous/shrub −0.078 (n = 182), → canopy −0.044 (n = 54), → turf −0.025 (n = 164),
  → bare +0.027 (n = 72). Gains: from canopy +0.020, turf +0.023, herbaceous +0.071, bare +0.063.

### 2026-10-11 — Q2 run: cover state vs LST trend (exploratory)
- `scripts/11_q2_cover_state_trend.py` → `data/processed/cc_lulc/q2_*.csv`, preview PNG.
  17,150 stable blocks, 273 tiles.
- Median relative trend (B) by type, °C/yr [95% CI]: turf −0.007 [−0.020, 0.010], pavement
  −0.023 [−0.040, −0.009], canopy −0.025 [−0.040, −0.011], mixed −0.034, herbaceous −0.035,
  roof-dominated −0.064 [−0.085, −0.047]. C1 (absolute): turf +0.147, pavement +0.138,
  canopy +0.114, roofs +0.092.
- Impervious deciles non-monotonic: lowest trends in deciles 7–9 (67–90% impervious,
  rowhouse-like), deciles 1 and 10 ≈ −0.015. OLS on fractions: small negative coefficients
  significant on the full grid, not on the thinned grid (except roads, p = 0.035).
- Scene-level sensitivity to air temperature rises with imperviousness (b: canopy 0.68 →
  roofs 0.81 °C/°C; roof gap vs T_air +0.10, p = 0.09). Weather-adjusted per-type trends all
  non-significant (18–20 scenes; CIs ≈ ±0.2–0.3 °C/yr); roof gap trend −0.066 (p = 0.21).

### 2026-10-11 — Landsat 9 acquisition and replication run (exploratory)
- `scripts/01_acquire_landsat.py landsat-9` (script now takes a platform argument and keeps
  the other platform's manifest rows): 15 L9 scenes, 75 manifest rows, none skipped.
  8 L9 scenes pass the ≥ 50% clear rule, including 2 in 2022 (no usable L8 2022).
- `scripts/02_lst_trend.py`: `load_scenes(city, sensors=("LC08",))` — default unchanged.
- `scripts/12_l9_replication.py` → `data/processed/l9_replication/`.
- A: relative LST pattern 2022–25, L8 vs L9: r = 0.97 (mean |diff| 0.84 °C).
- B: independent change maps, L8 vs L9: r = 0.19 (Spearman 0.13). Blocks with NLCD
  impervious gain ≥ 20 pp: ΔL8 +1.9 °C, ΔL9 +1.2 °C vs stable −0.3 / +0.1 °C.
- C: impervious-gain effect (°C/yr per 10 pp, gain ≥ 5 pp blocks): L8 0.100 ± 0.014;
  L8 + L9 0.087 ± 0.013; swap 0.083 ± 0.013. Trend map r with L8-only: 0.83 (L8 + L9),
  0.61 (swap). City C1 trend: L8 +0.13 ± 0.21 (11 yr); L8 + L9 +0.14 ± 0.22 (12 yr, p = 0.17);
  swap +0.15 ± 0.22 (p = 0.16).

### 2026-10-11 — Landsat 8 + 9 trend products (exploratory)
- `scripts/02_lst_trend.py` / `04_lst_bwi_normalized.py` take the sensor set from
  `LST_SENSORS`; run with `LC08,LC09` → `data/processed/lst_trend_lc08_lc09/`.
- 56 scenes, 28 pass the ≥ 50% clear rule; 12 years (2014 still missing).
- City (fixed 149,538 pixels): observed +0.23 °C/yr (p = 0.09) = climate +0.10 + sampling
  +0.11 + surface +0.05 (p = 0.66); C1 +0.145 °C/yr (p = 0.17, SE 0.097).
- Pixels: B relative median −0.007 °C/yr (11.4% p < 0.05: 4.5% warming, 6.9% cooling);
  C1 median +0.155; C2 median +0.063.
- QGIS group "Landsat 8 + 9 (2013–2025)"; replication layers moved into its subgroup.

### 2026-10-11 — NSA trend summary; Landsat 9 contrast artifact found (exploratory)
- `scripts/13_nsa_summary.py` → `data/processed/nsa/nsa_lst_<sensors>.gpkg/.csv` (279 NSAs; NSA-mean
  annual series → OLS trend, 95% CI, p, BH q; cover and census context).
- L8 + L9: 26 NSAs p < 0.05 for the relative trend, none at q < 0.10; C1 median +0.146 °C/yr.
  Across NSAs the relative trend correlates with mean relative LST −0.44, impervious −0.47,
  canopy +0.37 (hot neighbourhoods "converging"). L8 only: −0.16, −0.18, +0.06.
- `scripts/14_scene_contrast_check.py`: per-scene contrast (≥ 80% impervious minus ≥ 70% canopy)
  depends strongly on day of year (−0.041 °C/day, p < 0.001, r² 0.43) but has no year trend
  (+0.015, p = 0.79, with controls); L9 scenes show ~0.84 °C lower contrast than L8 for the same
  date and air temperature (p = 0.065). Mean day of year does not differ between periods.
- **Interpretation:** most of the L8 + L9 hot/cool convergence comes from adding lower-contrast
  L9 scenes at the end of the record, not from real change. Local change results (impervious
  gain effect) are unaffected (replicated). Decision on the primary scene set reopened.

### 2026-10-11 — NSA summary, Landsat 8 (primary)
- `scripts/13_nsa_summary.py` (default sensors) → `data/processed/nsa/nsa_lst_lc08.gpkg/.csv`.
- Relative trend: 27 of 279 NSAs at p < 0.05 (≈ 14 expected by chance), none at q < 0.10.
  C1: median +0.120 °C/yr; 18 at p < 0.05, none at q < 0.10.
- Across NSAs the relative trend is only weakly related to mean relative LST (−0.16),
  impervious (−0.18), canopy (+0.06), CC impervious change (+0.15), NLCD impervious change
  (+0.16), population density (−0.19).
- QGIS: group "NSA summary: Landsat 8, 2013–2025" (relative trend, C1 trend, mean relative LST;
  styles `styles/nsa_*.qml`); L8 + L9 group renamed "Replication only" and hidden.

### 2026-10-11 — Income vs LST by CSA (exploratory, Landsat 8)
- `scripts/15_csa_income_scatter.py` → `data/processed/csa/csa_lst_income_lc08.csv`,
  `figures/scatter_income/income_vs_{rel_trend,c1_trend,mean_rel}.png`.
- Median household income (2019–23) vs relative trend: Spearman +0.02 (p = 0.88); vs C1 trend
  +0.00 (p = 0.98); vs mean relative LST −0.18 (p = 0.19). n = 55 CSAs.
- Hot CSAs include both low-income west/east-side rowhouse areas and high-income waterfront
  rowhouse areas (Canton, Highlandtown, Fells Point, Federal Hill); the coolest are
  high-income northern (Roland Park, Guilford) and park-adjacent CSAs.

### 2026-10-11 — Share of Black residents vs LST by NSA (exploratory, Landsat 8)
- `scripts/16_nsa_race_scatter.py` → `data/processed/nsa/nsa_race_lst_lc08.csv`,
  `figures/scatter_race/pct_black_vs_{mean_rel,rel_trend,c1_trend}.png`. 258 NSAs (≥ 100
  residents); x = Blk_AfAm / Population (2020). Population-weighted exposure with 95% CI from a
  spatial block bootstrap (2 km tiles of NSA centroids, 2000 resamples).
- Mean relative LST: Spearman +0.08 (p = 0.18); exposure Black +0.52 °C vs white +0.62 °C,
  difference −0.10 [−1.27, +1.09].
- Relative trend: Spearman +0.13 (p = 0.04); exposure difference +0.020 °C/yr [−0.004, +0.044].
- C1 trend: Spearman +0.19 (p = 0.002), Pearson +0.24; exposure difference +0.034 °C/yr
  [−0.001, +0.075]. Naive p-values ignore spatial dependence; bootstrap CIs just include 0.

### 2026-10-11 — Stream networks added (display; exploratory)
- `scripts/17_acquire_streams.py`: CC streamLine.zip (30.3 MB, local) + metadata XML, NHD HU8
  shapefile (12.8 MB, git); clipped to the NSA union in EPSG:32618.
- City: CC 964 reaches, 243.6 km (157.6 km open channel; 86.0 km with ≥ 50% "connector", i.e.
  no visible channel polygon — likely piped, culverted, under road, or through open water);
  Strahler orders 1–6. NHD 233 flowlines, 175.0 km (StreamRiver 99.8, Coastline 47.3,
  ArtificialPath 21.9, Connector 6.0 km); no underground-conduit features in the city.
- Neither network maps the historically buried streams of the central city.
- QGIS group "Streams" (styles `streams_cc_channel.qml`, `streams_nhd_named.qml`).

### 2026-10-11 — Summer LST vs distance to streams (exploratory, Landsat 8)
- `scripts/18_stream_distance_lst.py` → `data/processed/streams/stream_distance_*.csv`,
  `figures/stream_distance/{lst_vs_dist_open,resid_vs_dist_open,resid_open_vs_hidden}.png`.
  25,215 blocks of 90 m (< 10% water); distance from block centre to the nearest CC reach.
  Cover-adjusted LST = residual of mean relative LST ~ CC 2021/22 cover fractions (r² 0.79).
  Near (≤ 90 m) minus far (450–1000 m), 95% CI from 1 km tile bootstrap.
- Open channel: raw −5.6 °C [−6.5, −4.8]; canopy +39 pp near streams; cover-adjusted
  −1.17 °C [−1.41, −0.86], fading to ~0 by ~300 m. Same > 1 km from the harbour (−1.19 °C).
- No visible channel (cnctR ≥ 0.5): raw −2.8 °C, cover-adjusted −0.49 °C [−0.79, −0.25].

### 2026-10-11 — Terrain acquisition and stream vs terrain run (exploratory, Landsat 8)
- `scripts/19_acquire_terrain.py`: 3DEP subset 13.1 MB (local), STAC JSON, geomorphon 10 m
  10.4 MB (git; by-name ScienceBase URL 404, public S3 URL used).
- `scripts/20_stream_terrain_lst.py` → `data/processed/streams/terrain_*.csv`,
  `figures/stream_distance/{terrain_bins,stream_size}.png`. 24,948 blocks. Sun at overpass
  (31 Jul 15:46 UTC): elevation 62.0°, azimuth 131.7°.
- R²: cover 0.811; + terrain 0.822; + surroundings 0.905.
- 0–90 m vs 450–1000 m: cover −1.38 °C [−1.68, −1.08]; + terrain −1.33 [−1.64, −1.02];
  + surroundings −0.18 [−0.39, +0.03] (ns); 90–180 m: −1.16 → −1.09 → +0.05.
- Terrain (M2): illumination +5.3 °C per unit cos(i) (sun-facing slopes warmer), slope
  −0.09 °C/deg, elevation −0.010 °C/m, valley −0.0035 and ridge −0.0042 °C/pp; TPI ns.
- Stream size (blocks < 180 m): by Strahler order, cover-adjusted means −0.67 (1) to −1.00 (4–6),
  joint p = 0.02; after terrain p = 0.11; after surroundings p = 0.06, non-monotonic. By
  channel width: p = 0.23 / 0.37 / 0.41.

### 2026-10-11 — Named stream corridor profiles (exploratory, Landsat 8)
- `scripts/21_stream_corridor_profiles.py` → `data/processed/streams/corridor_{profiles,summary}.csv`,
  `figures/stream_distance/corridor_profiles.png`. NHD flowlines by name, points every 90 m,
  135 m-radius corridors.
- Corridor mean relative LST: Gwynns Falls −6.3 °C (coolest; upper third −9.3, lower third −2.6),
  Herring Run −5.9, Stony Run −4.9, Jones Falls −1.1 (lower third +2.6). Across all points,
  LST vs canopy r = −0.91, vs impervious r = +0.94.
- Trends (sampled from the trend rasters): C1 Gwynns +0.20 °C/yr (upper third +0.26) vs Herring
  +0.08, Jones +0.03, Stony −0.05. Upper-Gwynns NSAs (Dickeyville, Franklintown, Wakefield,
  Hunting Ridge, Gwynns Falls/Leakin Park) C1 +0.15 to +0.33 (p 0.002–0.03 each; none at
  q < 0.10); relative trends +0.04 to +0.07 vs NSA median −0.04.
- CC canopy change in corridors small: Gwynns middle third −3.3 pp (largest), upper −0.4 pp.

### 2026-10-11 — NDVI trend test of the forest-condition hypothesis (exploratory, Landsat 8)
- `scripts/01_acquire_landsat.py` now also fetches SR_B4 and SR_B5 (82 new subsets for the 41 L8
  scenes; manifest storage for MTL/STAC set to git by the script).
- `scripts/22_ndvi_trend.py` → `data/processed/ndvi/` (annual, mean, slope, p rasters;
  `nsa_ndvi_trend.csv`, `stable_forest_blocks.csv`, `corridor_ndvi_trend.csv`),
  `figures/ndvi/{forest_nsa,stable_forest}_ndvi_vs_lst_trend.png`. 20 scenes, 11 years.
- City median summer NDVI 0.49; median trend −0.0013 /yr.
- Forested NSAs (canopy ≥ 55%, n = 15): upper-Gwynns NSAs mean NDVI trend −0.0021 /yr vs other
  −0.0034 /yr (Mann–Whitney p = 0.16); Leakin Park ≈ 0. NDVI trend vs C1 trend across forested
  NSAs: Spearman −0.08 (p = 0.77). Largest NDVI declines: Herring Run Park (−0.0056), Original
  Northwood, Dickeyville.
- Stable forest blocks (≥ 70% canopy both periods, n = 2,093): C1 trend rises with NDVI trend,
  +0.085 °C/yr per +0.01 NDVI/yr [+0.045, +0.124] (tile-clustered) — opposite in sign to the
  browning → warming hypothesis. Upper-Gwynns stable forest: NDVI trend −0.0009 vs −0.0028
  elsewhere; C1 +0.20 vs +0.10.
- **Interpretation:** no evidence that loss of greenness explains the upper Gwynns warming. NDVI
  saturates in dense canopy (Leakin Park mean 0.82), so a moisture-sensitive index (NDMI, SWIR1)
  would be a stronger test. The positive NDVI–LST trend association in forest suggests a shared
  scene/pixel-level factor (e.g. residual haze or cloud-edge effects lowering both).

### 2026-10-11 — Haze sensitivity and jackknife (exploratory, Landsat 8)
- `scripts/23_haze_sensitivity.py --jackknife` → `data/processed/haze/{scene_contrast,sensitivity,
  jackknife,jackknife_summary}.csv`. Flagged: LC08 2024-08-25 only (NDVI contrast z = −2.23;
  2021-07-16 z = −1.56 not flagged).
- Without 2024-08-25: city C1 +0.13 → +0.17 °C/yr; NSAs at p < 0.05 28 → 12; trend-vs-heat ρ
  −0.14 → +0.16; roof − turf −0.057 → −0.029; gain effect 0.100 → 0.098; forest NDVI −0.0025 →
  −0.0012 /yr (p 0.48).
- Jackknife ranges (all 20 drops): gain effect +0.096 to +0.110 per 10 pp; upper-Gwynns relative gap
  +0.068 to +0.117 °C/yr (20/20 positive); race exposure difference (rel) +0.008 to +0.034,
  (C1) +0.014 to +0.048 (20/20 positive); roof − turf −0.105 to −0.022 (20/20 negative); city C1
  +0.04 to +0.25 (most influential: 2023-07-06, 2023-08-23); NSAs at p < 0.05: 12–34;
  trend-vs-heat ρ −0.54 to +0.16; forest NDVI trend never significant (p ≥ 0.13).

### 2026-10-12 — Year-round Landsat 8 trend run (exploratory)
- `scripts/01_acquire_landsat.py landsat-8 --all-months`: 224 scenes (1,568 manifest rows).
- `scripts/24_allyear_trends.py` → `data/processed/lst_allyear/` (harmonic and seasonal trend
  rasters, seasonal mean relative LST, `city_trends.csv`, `season_comparison.csv`,
  `nsa_lst_allyear_lc08.gpkg/.csv`, `paving_by_season.csv`), `figures/allyear/*.png`.
- LST–air sensitivity b: DJF 0.85, MAM 0.95, JJA 0.81, SON 1.23.
- City (scene medians): observed year-round +0.25 °C/yr [0.09, 0.42]; C1 +0.19 [−0.11, 0.48]
  (leave-one-year-out +0.07 to +0.25); C2 +0.01 [−0.23, 0.26]. C1 by season: DJF +0.21
  (p = 0.05), MAM +0.12, JJA +0.18 [0.09, 0.27], SON −0.10. C2 ≤ 0.07 in every season.
- Pixels: relative trend 25% p < 0.05 by the strict annual test (8.9% warming, 16.1% cooling);
  C1 0.7%, C2 0.5%.
- NSA relative trend: 24 NSAs at q < 0.10 by the strict test (64 by the scene-level test);
  C1 none. Rank correlation with Jul–Aug NSA results: trend 0.75, mean 0.99. Across NSAs,
  relative trend vs mean relative LST ρ = −0.11 (p = 0.08); scene hot–cool contrast shows no
  decline (+0.018 °C/yr, p = 0.37), so not a contrast artifact.
- Heat pattern by season: hot–cool contrast DJF 1.9, MAM 5.5, JJA 9.5, SON 4.5 °C; cover r²
  0.44 / 0.70 / 0.79 / 0.71; roofs +0.12 / +0.67 / +1.04 / +0.38 and canopy −0.22 / −0.31 /
  −0.50 / −0.37 °C per 10 pp. Seasonal mean maps correlate 0.79–0.97.
- Paving effect (relative trend per 10 pp NLCD impervious gain): year-round +0.054
  [0.036, 0.071]; DJF 0.000; MAM +0.051; JJA +0.099; SON +0.031.

### 2026-10-12 — BWI long-record trends and acceleration test (context for LST rates)
- `scripts/25_bwi_long_record.py` (GHCN-D USW00093721). Jul–Aug mean Tmax trend (°C/decade):
  1940–2025 +0.14, 1970–2025 +0.24, 1990–2025 +0.33, 2000–2025 +0.84, 2013–2025 +1.56; annual Tmax
  2013–2025 +1.68 is the largest of 74 13-year windows since 1940 (Jul–Aug 72/74). 13-year window
  trends vary widely (e.g. −0.5 to −0.6 for windows ending 2017–2018).
- Hinge at 2000 (1970–2025, HAC SEs): slope increase annual Tmax +0.48 °C/decade (p = 0.025),
  annual Tmin +0.78 (p < 0.001), Jul–Aug Tmax +0.44 (p = 0.18); quadratic term p = 0.019 /
  < 0.001 / 0.26.
- **Interpretation:** warming at BWI has accelerated since ~2000 (clearly for annual Tmax/Tmin,
  suggestively for summer Tmax), but the 2013–2025 13-yr rate also reflects interannual
  variability (cool start, record-warm 2024–2025) and overstates the underlying rate.
- 2013–2025 vs 2000–2012 (same script; slope difference, HAC SEs): Jul–Aug Tmax +2.32 → +1.56
  °C/decade, difference −0.76 [−2.69, +1.17] (p = 0.44); annual Tmax +1.16 → +1.68, +0.52
  [−0.85, +1.89] (p = 0.46); annual Tmin +1.33 → +1.20, −0.13 (p = 0.78). Mean level 2013–2025
  is +0.56 to +0.70 °C above 2000–2012. No evidence the last 13 years warmed faster than the
  previous 13; the acceleration is relative to the late 20th century.

### 2026-10-12 — Buffer width vs summer LST (exploratory, Landsat 8)
- `scripts/26_buffer_width.py` → `data/processed/streams/buffer_width_{points,model,hinge}.csv`,
  `figures/stream_distance/buffer_width.png`. 1,042 points on 728 open reaches; 762 with full
  1 m coverage (city-edge windows dropped). Width classes: < 10 m 28, 10–30 167, 30–50 91,
  50–100 169, 100–200 131, ≥ 200 176.
- Corridor LST vs < 10 m (controlling context impervious): 10–30 m +0.10 °C (ns); 30–50 m −0.97
  [−2.44, +0.50]; 50–100 m −2.89 [−4.30, −1.47]; 100–200 m −3.61 [−5.04, −2.18]; ≥ 200 m −3.48
  [−4.86, −2.10]. Hinge: −0.64 °C per 10 m up to ~70 m total width, then flat.
- Neighbourhood 100–200 m from channel: 50–100 m −1.01 [−1.91, −0.12]; 100–200 m −1.64; ≥ 200 m
  −3.47 [−4.39, −2.55] (keeps increasing with width).

### 2026-10-12 — Step detection run (exploratory, Landsat 8 all months)
- `scripts/27_step_detection.py` → `data/processed/steps/{block_steps,nsa_steps}.csv`,
  `step_year_90m.tif`, `step_C_90m.tif`, `figures/steps/{nsa24_step_series,nsa24_step_years}.png`.
- 25,547 blocks; step 23.1%, trend-like 3.0%, no change 74.0% (sup-F 5% critical 10.48).
  Block step share: 24 significant NSAs median 31% vs 21% elsewhere; NSA-level steps 9/24 vs 40/249.
- Citywide 2018 cluster: 1,201 cooling and 473 warming step blocks (≈ 3–4× other years), across
  all heat quintiles; 2018 warming steps are turf-rich (median turf 24% vs 10% in no-change blocks),
  cooling steps have more canopy and roofs → a land-cover-type-dependent shift after 2018
  (plausibly drier late summers browning turf), not redevelopment.
- Distinct NSA-level steps: Perkins 2023 −1.60 °C (81% of blocks step, 13 cooling); McElderry Park
  2016 −1.11 (73%); Biddle Street 2016 −0.64; Broadway East 2019 −0.57; Middle Branch/Reedbird
  Parks 2021 −0.49; Cherry Hill 2021 −0.45; Shipley Hill 2018 −0.44; Darley Park 2019 −0.41;
  Orchard Ridge 2017 +0.53. Other significant-trend NSAs (e.g. Ramblewood, Midtown-Edmondson,
  Saint Paul) look gradual rather than stepwise.

### 2026-10-12 — NAIP visual verification of LST steps (exploratory)
- `scripts/28_acquire_naip.py` → 42 clips (7 NSAs × 6 years) in `data/raw/naip/` (manifest, local),
  strips in `figures/naip/`, QGIS group "NAIP verification". Visual reads at thumbnail scale
  (to be confirmed at full resolution):
  - Perkins (step 2023, −1.6 °C): public-housing campus unchanged 2013–2021; 2023 shows the northern
    half cleared to a bright construction site with a large new white-roofed building — timing
    matches; cooling direction is plausible from brighter fill/roofs but not established.
  - Orchard Ridge (warming step 2017): a new red running track/athletic field and expanded
    construction/cleared ground appear between 2015 and 2017 — timing and direction consistent.
  - Middle Branch/Reedbird Parks (step 2021): park meadows look denser/greener by 2021–2023;
    a construction pad appears on the east edge in 2021.
  - Cherry Hill (step 2021): same 2021 construction pad and greener park edges; no single obvious cause.
  - Broadway East (step 2019): gradual greening of vacant lots and street trees 2017–2023.
  - Biddle Street (2016) and McElderry Park (2016): no clear change visible at thumbnail scale.

### 2026-10-12 — Buffer-width deep dive (exploratory, Landsat 8 + ECOSTRESS)
- `scripts/29_buffer_points.py` → `data/processed/streams/buffer_points_v2.csv` (854 points, 150 m
  spacing on open CC channels; per-bank 1 m canopy bands 2013/2021, continuity, context rings,
  terrain, order, harbour distance, population density, cross-stream LST profiles).
- `scripts/30_buffer_analysis.py` → `deepdive_*.csv`, `deepdive_priority_points.gpkg`,
  `figures/buffer_deepdive/{threshold_and_seasons,robustness,cooling_distance}.png`.
  Per-side width, ref ≥ 200 m, Jul–Aug corridor relative LST: 10–30 m +1.5 to +2.5 °C, 30–50 m
  +0.9 to +1.5, 50–100 m +0.3 to +0.9 (significant with tile FE, 500 m FE, within-reach FE,
  continuity), 100–200 m ≈ 0. Hinge 60 m (tile bootstrap 95% CI 40–110), −0.52 °C per 10 m below.
  Continuity −0.61 °C per +10 pp. Both banks matter. Seasonal gradient JJA > MAM > SON > DJF
  (<10 m: 3.08 / 2.11 / 1.70 / 0.78). Cooling extends 120 m (<10) to 390 m (≥ 200) from channel.
  Buffer canopy gain 2013→2021 → relative trend −0.023 to −0.031 °C/yr per 10 pp (tile FE, p < 0.01).
- `scripts/31_acquire_ecostress.py` → 470/473 granules (3 failed, HTTP 502) in `data/raw/ecostress/`.
- `scripts/32_ecostress_buffer.py` → `data/processed/ecostress/{rel_mean_<bin>.tif,scenes.csv,
  buffer_by_time.csv}`, `figures/buffer_deepdive/ecostress_time_of_day.png`. 170 scenes used
  (night 43, morning 20, midday 42, afternoon 39, evening 26). Corridor 10–30 m vs ≥ 200 m:
  night +0.10 (p 0.05), morning +0.54, midday +1.39, afternoon +1.26, evening +0.36 °C; 50–100 m
  midday +0.70 (p < 0.001). Neighbourhood (90–210 m) shows a similar gradient by day.
- `scripts/33_detection_limit.py` → `detection_limit.csv/png` (A = 2.99 °C; threshold 0.58 °C;
  minimum detectable width ≈ 15 m per side for both sensors).
