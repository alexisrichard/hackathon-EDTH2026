# Data sources and licenses

Provenance and license tracking for every dataset under `data/` and `s3://edth2026-baltic/`.
**Always check this file before redistributing data or shipping a demo to a third party.**

Last updated: 2026-05-18

## Quick license-compatibility summary

| Family | Can we redistribute? | Can we use in a commercial demo? | Attribution required? |
|---|---|---|---|
| OSM (ODbL) | Yes, under ODbL share-alike | Yes | Yes — "© OpenStreetMap contributors" |
| Copernicus / Sentinel (free) | Yes | Yes | Yes — "contains modified Copernicus … data" |
| EMODnet (CC-BY 4.0) | Yes | Yes | Yes — "EMODnet Human Activities" |
| Marine Regions / VLIZ (CC-BY 4.0) | Yes | Yes | Yes — "Flanders Marine Institute (VLIZ)" |
| US Government / OFAC (public domain) | Yes | Yes | Recommended — "U.S. Treasury OFAC SDN" |
| UK OFSI (Open Government Licence) | Yes | Yes | Yes — "© Crown copyright, OGL v3" |
| OpenSanctions (CC-BY-NC 4.0) | Yes for non-commercial | **No** — commercial requires license | Yes — "OpenSanctions" |
| Danish AIS (free, any use) | Yes | Yes | Recommended |
| Finnish AIS / Digitraffic (CC-BY 4.0) | Yes | Yes | Yes — "Fintraffic / Digitraffic" |
| Norwegian AIS (NLOD 2.0) | Yes | Yes | Yes — "Kystverket, NLOD 2.0" |
| AISStream.io | Stream-only, no archive | Yes (live demo only) | Yes — "via AISStream.io" |
| Umbra Open Data (CC-BY 4.0) | Yes | Yes | Yes — "Umbra Space" |
| Capella Open Data (CC-BY-NC 4.0) | Yes for non-commercial | **No** — non-commercial only | Yes — "Capella Space" |
| TeleGeography Submarine Cable Map | **No redistribution** | Visual reference only | Yes if visually referenced |
| KSE Russian shadow fleet | Research-only, ask before redistribution | Internal demo OK, public release — ask | Yes — "Kyiv School of Economics" |
| Kaggle datasets | Varies per dataset — check each | Varies | Per Kaggle terms + dataset-specific |
| HELCOM (Helsinki Commission) | Free with attribution | Yes | Yes — "HELCOM" |
| Natural Earth | Public Domain (CC0) | Yes | Recommended |
| GMRT bathymetry | Free for non-commercial; cite Ryan et al. (2009) | Non-commercial only | Yes — "GMRT" |
| Orange Marine (if obtained) | Likely proprietary / NDA | Depends on agreement | Per agreement |

## Datasets currently in repo + S3 bucket

### Geo / criticality layers — `data/geo/` and `s3://edth2026-baltic/geo/`

| File | Source | License | Last fetched | Script | Size | Notes |
|---|---|---|---|---|---|---|
| `submarine_cables.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 5.1 MB | 6,238 features. C-Lion1, BCS East-West, Estlink, Baltika present |
| `submarine_power_cables.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 1.1 MB | 610 features |
| `pipelines.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 6.3 MB | 4,659 features |
| `ports.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 2.6 MB | 3,037 features (includes leisure) |
| `naval_bases.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 80 KB | 18 features |
| `refineries_lng.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 584 KB | 652 features |
| `offshore_platforms.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 13 KB | 13 features |
| `offshore_wind.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 136 KB | 68 features |
| `emodnet_pipelines.geojson` | EMODnet Human Activities | CC-BY 4.0 | 2026-05-18 | `scripts/geo/fetch_emodnet_layers.py` | 6.4 MB | 520 features. Authoritative offshore-pipeline routes |
| `emodnet_windfarmspoly.geojson` | EMODnet Human Activities | CC-BY 4.0 | 2026-05-18 | `scripts/geo/fetch_emodnet_layers.py` | 860 KB | 159 features. Wind farm footprints |
| `emodnet_windfarms_point.geojson` | EMODnet Human Activities | CC-BY 4.0 | 2026-05-18 | `scripts/geo/fetch_emodnet_layers.py` | 58 KB | 124 features. Individual turbine locations |
| `emodnet_cables_combined.geojson`† | EMODnet Human Activities | CC-BY 4.0 | 2026-05-18 | `scripts/geo/fetch_emodnet_layers.py` | 47 MB | 300 features. Merged national cable layers (DE, NL, NO) |
| `marine_regions_eez_baltic.geojson`† | VLIZ Marine Regions (WFS) | CC-BY 4.0 | 2026-05-18 | `scripts/geo/fetch_marine_regions_eez.py` | 36 MB | 12 EEZ polygons for Baltic states + adjacent |
| `bathymetry_baltic.nc`† | GMRT (Global Multi-Resolution Topography) | Free non-commercial | 2026-05-18 | `scripts/geo/fetch_bathymetry.py` | 29 MB | Sea floor depths, NetCDF grid |
| `chokepoints.geojson` | Hand-curated by project team | Project (MIT-equivalent) | 2026-05-18 | Manual | 3 KB | 9 maritime chokepoints (Skagerrak, Øresund, Great Belt, etc.) |
| `ne_countries_50m.geojson` | Natural Earth | CC0 (Public Domain) | 2026-05-18 | `scripts/geo/fetch_natural_earth.py` | 539 KB | 17 country polygons clipped to Baltic region |
| `ne_coastline_10m.geojson` | Natural Earth | CC0 | 2026-05-18 | same | 1.3 MB | 228 coastline segments |
| `ne_ports_10m.geojson` | Natural Earth | CC0 | 2026-05-18 | same | 29 KB | 133 ports |
| `ne_ocean_10m.geojson`† | Natural Earth | CC0 | 2026-05-18 | same | 17 MB | 1 ocean polygon (used for masking) |
| `ne_rivers_10m.geojson` | Natural Earth | CC0 | 2026-05-18 | same | 519 KB | 86 rivers |
| `ne_urban_areas_10m.geojson` | Natural Earth | CC0 | 2026-05-18 | same | 4.5 MB | 1107 urban areas |
| `osm_tss.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_seamarks.py` | 97 KB | 371 Traffic Separation Scheme segments |
| `osm_restricted_areas.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 2.5 MB | 1,277 restricted/military areas |
| `osm_anchorages.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 151 KB | 583 anchorages |
| `osm_lighthouses.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 4.6 MB | 5,115 lighthouses |
| `osm_buoys.geojson`† | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 14.8 MB | 41,219 buoys (cardinal/lateral/special) |
| `osm_wrecks.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 347 KB | 1,051 wrecks |
| `osm_fairways.geojson` | OSM Overpass | ODbL 1.0 | 2026-05-18 | same | 1.1 MB | 831 fairway centerlines |
| `helcom_shipping_accidents.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | `scripts/geo/fetch_helcom.py` | 4.6 MB | 4,932 reported Baltic shipping accidents |
| `helcom_detected_spills.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | same | 2.8 MB | 5,838 detected oil/substance spills |
| `helcom_ais_passage_crossings.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | same | 22 KB | 14 AIS passage-line crossings reference |
| `helcom_dredging_sites_*.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | same | 1.3 MB | Dredging activity (points + areas) |
| `helcom_disposal_sites_areas.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | same | 3.0 MB | 1,668 disposal site areas |
| `helcom_fishing_intensity_total_2016_2021.geojson` | HELCOM MADS | Free with attribution | 2026-05-18 | same | 8.6 MB | 10,000 fishing intensity cells |
| `marine_weather/INC-*.json` | Open-Meteo Marine + Archive (ERA5) | CC-BY 4.0 | 2026-05-18 | `scripts/ingest/fetch_marine_weather.py` | ~150 KB × 9 | Hourly wave + wind + temp + pressure for each incident ±14 days |

† Large files (>10 MB) — kept in S3 only, gitignored. Use `scripts/common/sync_from_s3.py geo` to fetch.

### Reference data — `data/reference/` and `s3://edth2026-baltic/reference/`

| File | Source | License | Last fetched | Script | Notes |
|---|---|---|---|---|---|
| `incidents.csv` | Hand-curated by project team | MIT-equivalent (ours) | 2026-05-18 | Manual | 9 well-documented Baltic incidents with attribution taxonomy |
| `sanctions_maritime.csv` | OFAC SDN + UK OFSI + EU FSF (via OpenSanctions) | OFAC: public domain; OFSI: OGL v3.0; OpenSanctions: CC-BY-NC 4.0 | 2026-05-18 | `scripts/reference/fetch_sanctions.py` | 1,773 entries. Mixed-license — non-commercial only because of OpenSanctions inclusion |
| `sentinel_scenes.csv` | Element84 Earth-Search STAC | Sentinel data: free (Copernicus) | 2026-05-18 | `scripts/ingest/sentinel_stac_search.py` | 441 scenes catalogued (no actual imagery downloaded yet) |
| `commercial_sar_scenes.csv` | Umbra + Capella STAC walk | Umbra: CC-BY 4.0; Capella: CC-BY-NC 4.0 | 2026-05-18 | `scripts/ingest/commercial_sar_search.py` | Baltic-intersecting scenes per incident |
| `raw/ofac_sdn.csv` | US Treasury OFAC | Public domain (US Gov) | 2026-05-18 | `fetch_sanctions.py` | Raw download (gitignored) |
| `raw/uk_consolidated.csv` | UK OFSI | Open Government Licence v3.0 | 2026-05-18 | `fetch_sanctions.py` | Raw download (gitignored) |
| `raw/eu_fsf_targets.csv` | OpenSanctions normalized EU FSF | CC-BY-NC 4.0 | 2026-05-18 | `fetch_sanctions.py` | Raw download (gitignored) |
| `aisdk_README.txt` | Danish Maritime Authority | Free | 2026-05-18 | `scripts/ingest/danish_ais.py` | Schema reference for AIS CSV |
| `ais_access_notes.md` | Internal | — | 2026-05-18 | Manual | Notes on bulk-access status for each AIS source |
| `kaggle_datasets_TODO.md` | Internal | — | 2026-05-18 | Manual | Maritime datasets on Kaggle to evaluate |

### AIS — `s3://edth2026-baltic/ais/parquet/`

| Source | Bucket layout | License | Status |
|---|---|---|---|
| Danish | `source=danish/year=YYYY/month=MM/day=DD/part-XXXX.parquet` | Free, no restrictions | **In progress** — pipeline at `scripts/ingest/danish_ais.py`. Incident windows downloading |
| Finnish | (not yet) | CC-BY 4.0 | Bulk-download gap — see `ais_access_notes.md` |
| Norwegian | (not yet) | NLOD 2.0 | Deprioritized — see `ais_access_notes.md` |
| AISStream.io live | (not bulk-stored, demo only) | Free with key | Sign up at `aisstream.io` |

### Satellite — `s3://edth2026-baltic/sar/` and `optical/`

| Source | Bucket | License | Status |
|---|---|---|---|
| Sentinel-1 SAR | element84 STAC (catalogued); raw via Copernicus | Free, Copernicus Open Access | Catalog only. Raw downloads need Copernicus account |
| Sentinel-2 optical | element84 STAC (catalogued); raw via Copernicus | Free, Copernicus Open Access | Catalog only. Raw downloads need Copernicus account |
| Umbra Open Data SAR | `s3://umbra-open-data-catalog/` (anonymous) | CC-BY 4.0 | Catalog walked; Baltic hits enumerated in `commercial_sar_scenes.csv` |
| Capella Open Data SAR | `s3://capella-open-data/` (anonymous) | CC-BY-NC 4.0 | Catalog walked; **non-commercial only** |
| Planet Education | `planet.com/markets/education-and-research` | Research-only if approved | Application required; stretch goal |
| ICEYE | `iceye.com` | Paid / ad-hoc researcher access | Stretch goal |

## Attribution string for the demo

Include this (or equivalent) in any public demo, screenshot, or pitch deck:

> Map data © OpenStreetMap contributors, ODbL. EMODnet Human Activities, CC-BY 4.0. Marine Regions / Flanders Marine Institute, CC-BY 4.0. Contains modified Copernicus Sentinel data (2022–2026). AIS data from Danish Maritime Authority. Sanctions data from U.S. Treasury OFAC, UK OFSI (OGL v3.0), and OpenSanctions (CC-BY-NC). Commercial SAR samples from Umbra Space (CC-BY) and Capella Space (CC-BY-NC). © 2026 EDTH-2026 project team.

## Commercial-use guardrails

If we want to commercialize ANY part of this after the hackathon, the following must be replaced or licensed:

- **OpenSanctions EU FSF data** → revert to direct EU consolidated XML feed (no NC restriction) OR license OpenSanctions commercially
- **Capella Open Data SAR** → drop OR pay for commercial use
- **TeleGeography cable map** → license OR replace with EMODnet/OSM-only cables
- **KSE shadow fleet** → seek explicit redistribution license

Everything else is commercial-safe as long as attribution is preserved.

## How to update this file

1. When `fetch_*.py` scripts run, they should update `fetched_at` timestamps in per-dataset READMEs.
2. When adding a new source, append a row to the relevant section *and* update the license-compatibility summary if a new license family appears.
3. When obtaining data under NDA or restricted license (e.g., Orange Marine), mark it clearly in the "Status" column and note constraints in the file's own README.
