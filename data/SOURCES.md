# Data sources and licenses

Provenance and license tracking for every dataset under `data/` and `s3://edth2026-baltic/`.
**Always check this file before redistributing data or shipping a demo to a third party.**

## Quick license-compatibility summary

| Family | Can we redistribute? | Can we use in a commercial demo? | Attribution required? |
|---|---|---|---|
| OSM (ODbL) | Yes, under ODbL share-alike | Yes | Yes — "© OpenStreetMap contributors" |
| Copernicus / Sentinel (free) | Yes | Yes | Yes — "contains modified Copernicus … data" |
| EMODnet (CC-BY 4.0) | Yes | Yes | Yes — "EMODnet Human Activities" |
| Marine Regions / VLIZ (CC-BY 4.0) | Yes | Yes | Yes — "Flanders Marine Institute (VLIZ)" |
| US Government / OFAC (public domain) | Yes | Yes | Recommended — "U.S. Treasury OFAC SDN" |
| UK OFSI (Open Government Licence) | Yes | Yes | Yes — "© Crown copyright, OGL v3" |
| Danish AIS (free, any use) | Yes | Yes | Recommended |
| Finnish AIS (CC-BY 4.0) | Yes | Yes | Yes — "Fintraffic / Finnish Transport Agency" |
| Norwegian AIS (NLOD) | Yes | Yes | Yes — "Kystverket, NLOD 2.0" |
| AISStream.io | Stream-only, no archive | Yes (live demo only) | Yes — "via AISStream.io" |
| Global Fishing Watch (research) | No (research-only) | No | Yes if used |
| KSE Russian shadow fleet | Research-only, ask before redistribution | Internal demo OK, public release — ask | Yes — "Kyiv School of Economics" |
| TeleGeography Submarine Cable Map | **No redistribution** | Visual reference only | Yes if visually referenced |
| Umbra Open Data | Yes (CC-BY 4.0 most assets — check per scene) | Yes | Yes — "Umbra Space" |
| Capella Open Data | Yes (CC-BY-NC 4.0 — non-commercial!) | **No commercial** | Yes — "Capella Space" |
| Orange Marine (if obtained) | Likely proprietary / NDA | Depends on agreement | Per agreement |

## Datasets currently in repo + S3 bucket

### Geo / criticality layers — `data/geo/` and `s3://edth2026-baltic/geo/`

| File | Source | License | Last fetched | Script | Notes |
|---|---|---|---|---|---|
| `submarine_cables.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 6,238 features. Mix of telecom + power; subset is `submarine_power_cables.geojson` |
| `submarine_power_cables.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 610 features. Estlink, NordBalt, SwePol all present |
| `pipelines.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 4,659 features. Includes onshore; filter on `submarine` or `location=underwater` |
| `ports.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 3,037 features. Includes leisure harbours; filter on `harbour:category=commercial` for strategic ports |
| `naval_bases.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 18 features |
| `refineries_lng.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 652 features. Cleaned of farm-fuel-tank noise |
| `offshore_platforms.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 13 features |
| `offshore_wind.geojson` | OSM via Overpass API | ODbL 1.0 | 2026-05-18 | `scripts/geo/fetch_osm_layers.py` | 68 features |

### Reference data — `data/reference/` and `s3://edth2026-baltic/reference/`

| File | Source | License | Last fetched | Script | Notes |
|---|---|---|---|---|---|
| `incidents.csv` | Hand-curated by project team | MIT-equivalent (ours) | 2026-05-18 | Manual | See `incidents_README.md` |
| `sanctions_maritime.csv` | OFAC SDN + UK OFSI (filtered) | OFAC: public domain (US Gov). OFSI: Open Government Licence v3.0 | 2026-05-18 | `scripts/reference/fetch_sanctions.py` | 1,699 entries. See `sanctions_README.md` |
| `raw/ofac_sdn.csv` | US Treasury OFAC | Public domain (US Gov) | 2026-05-18 | Same | Raw unfiltered download |
| `raw/uk_consolidated.csv` | UK OFSI (gov.uk) | Open Government Licence v3.0 | 2026-05-18 | Same | Raw unfiltered download |

### Reference data — planned

| Dataset | Source | License | Status |
|---|---|---|---|
| EU consolidated sanctions | EU Commission webgate, OpenSanctions.org | Public (EU works) / CC-BY for OpenSanctions | URL gated; see `sanctions_README.md` for fallback path |
| KSE Russian shadow fleet | Kyiv School of Economics | Research-only (request to KSE) | Manual fetch — email signup required |
| Vessel registry | Equasis, ITU MARS | Login-only | On-demand per-MMSI during runtime |
| EMODnet Human Activities cables | EMODnet | CC-BY 4.0 | Planned — higher accuracy than OSM |
| Marine Regions EEZ | Flanders Marine Institute (VLIZ) | CC-BY 4.0 | Planned |
| TeleGeography Submarine Cable Map | TeleGeography | Restricted (visual reference only) | Visual overlay only — do NOT bake into redistributable data |
| Orange Marine cable routes | Orange Marine (operator data) | Proprietary / NDA-pending | Awaiting outreach to Orange Marine CEO contact |

### AIS — planned, `s3://edth2026-baltic/ais/`

| Source | URL | License | Coverage | Volume (filtered) |
|---|---|---|---|---|
| Danish Maritime Authority | https://web.ais.dk/aisdata/ | Free for any use ("uden begrænsninger") | DK + western Baltic | ~80 GB |
| Finnish Fintraffic | https://www.traficom.fi/en/transport/maritime/maritime-and-marine-traffic-information | CC-BY 4.0 | Finnish waters + Gulf of Finland | ~40 GB |
| Norwegian Kystverket | https://kystdatahuset.no | NLOD 2.0 (Norwegian Licence for Open Government Data) | Norwegian waters, partial Baltic | ~20 GB |
| AISStream.io | https://aisstream.io | Free with key; no archive retention rights | Global live | live only |

### Satellite — planned, `s3://edth2026-baltic/sar/` and `optical/`

| Source | URL | License | Notes |
|---|---|---|---|
| Sentinel-1 SAR | https://dataspace.copernicus.eu | Free, Copernicus Open Access | Requires CDSE account |
| Sentinel-2 optical | https://dataspace.copernicus.eu | Free, Copernicus Open Access | Cloud-limited |
| Umbra Open Data | https://umbra.space/open-data | CC-BY 4.0 (verify per asset) | Archive only |
| Capella Open Data | https://www.capellaspace.com/data/gallery | CC-BY-NC 4.0 (non-commercial!) | Archive only — use in demo, not in commercial product |
| Planet Education | https://www.planet.com/markets/education-and-research | Research-only if approved | Stretch goal |
| ICEYE | https://www.iceye.com | Paid / ad-hoc researcher access | Stretch goal |

## Attribution string for the demo

Include this (or equivalent) in any public demo, screenshot, or pitch deck:

> Map data © OpenStreetMap contributors, ODbL. Contains modified Copernicus Sentinel data (2024–2026). EMODnet Human Activities, CC-BY 4.0. Marine Regions / Flanders Marine Institute, CC-BY 4.0. AIS data from Danish Maritime Authority, Fintraffic (CC-BY 4.0), Kystverket (NLOD 2.0). Sanctions data from U.S. Treasury OFAC and UK OFSI (OGL v3.0). © 2026 EDTH-2026 project team.

## How to update this file

1. When `fetch_*.py` scripts run, they update `fetched_at` timestamps in the per-dataset READMEs (`incidents_README.md`, `sanctions_README.md`, etc.).
2. When adding a new source, append a row in the relevant section *and* update the license-compatibility summary if a new license family appears.
3. When obtaining data under NDA or restricted license (e.g., Orange Marine), mark it clearly in the "Status" column and note constraints in the file's own README.
