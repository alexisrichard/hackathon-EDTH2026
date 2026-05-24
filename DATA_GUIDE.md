# Data sources — specialist reference

One card per source. Read top-to-bottom to judge which datasets are useful for your specific question; jump via the index below.

For **license, attribution, and per-file inventory** see [`data/SOURCES.md`](data/SOURCES.md).
For **how to set up access** (S3 keys, API tokens) see [`ONBOARDING.md`](ONBOARDING.md).

## Index

**Vessel position data**
- [Danish AIS — bulk historical](#danish-ais--danish-maritime-authority-bulk-feed)
- [AISStream — live feed](#aisstream--live-baltic-feed-via-websocket)

**Satellite imagery**
- [Sentinel-1 SAR](#sentinel-1-sar--c-band-radar)
- [Sentinel-2 optical](#sentinel-2-optical--multispectral)
- [Commercial SAR — Umbra / Capella](#umbra--capella-commercial-sar-open-data)

**Infrastructure (cables, pipes, ports, wind)**
- [EMODnet — authoritative offshore infrastructure](#emodnet-human-activities--authoritative-offshore-infrastructure)
- [OpenStreetMap — community-tagged infrastructure](#openstreetmap--cables-pipes-ports-naval-bases-refineries-wind)
- [OpenStreetMap seamarks — navigational features](#openstreetmap-seamarks--tss-anchorages-lighthouses-buoys-wrecks-fairways)

**Maritime hazards + environment**
- [HELCOM — Baltic accidents, spills, fishing](#helcom--baltic-shipping-accidents-spills-dredging-fishing-intensity)
- [Bathymetry — GMRT sea floor depths](#bathymetry--gmrt-sea-floor-grid)
- [Marine weather — Open-Meteo + ERA5](#marine-weather--open-meteo-marine--era5-historical)

**Boundaries + basemap**
- [Marine Regions EEZ](#marine-regions-eez--vliz-world-eez)
- [Natural Earth basemap](#natural-earth-basemap--cc0-public-domain-vector)

**Vessel-level intelligence**
- [Sanctions — OFAC + UK OFSI + EU FSF](#sanctions--ofac--uk-ofsi--eu-fsf)
- [KSE shadow fleet tracker](#kse-russian-shadow-fleet-tracker)
- [Equasis vessel registry](#equasis--per-imo-vessel-registry)
- [Global Fishing Watch events](#global-fishing-watch--per-vessel-events)

**Project-internal + ML**
- [Incidents register](#incidents-register--project-curated)
- [Kaggle ML training datasets](#kaggle--ml-training-datasets)

---

## Danish AIS — Danish Maritime Authority bulk feed

**What it is.** Daily ZIP archives of every AIS broadcast received by the Danish coastal network (HF + satellite-fed). Free, no API key, no quota — Denmark publishes the full Baltic catch since 2006.

**What it provides** (per row).
MMSI, IMO (when broadcast), vessel name, type, length/breadth, draft, lat/lon, COG, SOG, heading, navigation status (anchored / underway / restricted manoeuvrability / …), destination, ETA.

**Coverage.** Strong across Skagerrak, Kattegat, Belts, Sound, western and central Baltic — including the Nord Stream, C-Lion1, Balticconnector and Estlink-2 incident sites. **Weaker** in the eastern Gulf of Finland and Latvia/Estonia near-shore (use Finnish Digitraffic to backfill if needed).

**Temporal resolution.** Class-A transponders broadcast every 2–10 s when underway, 3 min when anchored. Class-B and AtoN every 30 s – 3 min. Static info every 6 min.

**Volume in our copy.** 1,601 days (2022-01-01 → 2026-05-20), Baltic-bbox-filtered, ~330 GB in S3. Typical day ≈ 15–25M kept rows / 10–20k unique MMSI.

**Useful for.** Per-vessel tracks, AIS-gap detection (a key shadow-fleet signal), loiter/anchor patterns near cables, behavioural baselines.

**Caveats.** Vessels can switch AIS off ("dark behaviour") — absence ≠ no vessel. IMO field is optional; ~15 % of rows lack it. Source publishes ~1 day late, so today and yesterday will always be missing.

**Format / how to query.** Hive-partitioned Parquet at `s3://edth2026-baltic/ais/parquet/source=danish/year=YYYY/month=MM/day=DD/`. DuckDB one-liner:
```sql
SELECT mmsi, lat, lon, sog, ts
FROM read_parquet('s3://edth2026-baltic/ais/parquet/source=danish/year=2024/month=12/day=25/*.parquet')
WHERE mmsi = 273399740;  -- example
```

**License.** Public, no restrictions. Attribution: *"Danish Maritime Authority"*.

---

## AISStream — live Baltic feed via WebSocket

**What it is.** Real-time AIS aggregator (terrestrial + satellite). Free API key, WebSocket subscription with bbox filter. Designed for live dashboards, not bulk archival — their ToS disallows long-term storage.

**What it provides** (per message). MMSI, IMO, ship name, type, lat/lon, COG, SOG, heading, nav status, timestamp. Same schema as bulk AIS, just push-streamed instead of CSV-batched.

**Coverage.** Global; we subscribe to the Baltic bounding box only. Includes vessels not visible to Danish receivers (e.g. eastern Gulf of Finland).

**Latency.** Typically <30 s from transponder broadcast to WebSocket frame.

**Throughput in our tests.** ~38 msg/sec sustained for the Baltic bbox.

**Useful for.** The Sunday demo's live ticker — proving the cueing engine works on live data, not just replay.

**Caveats.** Don't archive to S3 (ToS). For historical look-back, use the Danish bulk feed instead. Coverage drops to satellite-only beyond ~50 km from terrestrial receivers.

**Format / how to query.** `scripts/ingest/aisstream_consumer.py` — reads `AISSTREAM_API_KEY` from `.env.local`, prints decoded messages.

**License.** Free with API key. Attribution: *"via AISStream.io"*.

---

## Sentinel-1 SAR — C-band radar

**What it is.** ESA Copernicus C-band synthetic aperture radar — sees through clouds, works day and night. The maritime ISR workhorse.

**What it provides.** Ground-Range-Detected (GRD) imagery in:
- **IW mode** (most over land/coast): 10 m resolution, ~250 km swath, VV+VH dual polarisation.
- **EW mode** (over open ocean): 40 m resolution, ~400 km swath, HH+HV polarisation.

**Coverage + revisit.** 6-day equatorial revisit when 1A+1B both operational. Note: **1B failed Dec 2021**; 1C launched **Dec 2024** and is now operational. So 2022–2024 is single-satellite (~12-day revisit), 2025+ back to ~6 days.

**What's in our copy.** 441 scenes catalogued from the Element84 Earth-Search STAC index covering all 9 incident windows. 9 incident-AOI true-colour SAR crops rendered to JPEG via the Copernicus Sentinel Hub Process API — replay-ready.

**Useful for.** Vessel detection in any weather (bright radar returns on calm sea); oil-spill signatures (dark slicks dampen sea-surface roughness); cable-laying ship signatures (distinctive long thin radar shadow + slow speed).

**Caveats.** Sea state matters — high winds add speckle and can hide small vessels. Wake detection requires careful processing (we don't run it; the raw imagery is provided for inspection or downstream models).

**Format / how to query.** Scene catalog at `data/reference/sentinel_scenes.csv`. Crops at `s3://edth2026-baltic/sar/incident=*/`. Re-render any AOI with `scripts/ingest/fetch_sentinel_imagery.py --incident <ID>`.

**License.** Free, Copernicus Open Access. Attribution: *"contains modified Copernicus Sentinel data (2022–2026)"*.

---

## Sentinel-2 optical — multispectral

**What it is.** ESA Copernicus 13-band optical multispectral satellite. The high-confidence ID complement to Sentinel-1.

**What it provides.** 10 m resolution for visible + NIR bands; 20 m SWIR; 60 m atmospheric. True-colour and false-colour composites available; 290 km swath.

**Coverage + revisit.** 5-day revisit at equator when 2A+2B both operational (status: both operational since 2017).

**What's in our copy.** 441 scenes catalogued (overlapping the S1 set). 9 incident-AOI true-colour crops rendered to JPEG with **adaptive cloud thresholding** (10 % → 30 % → 60 % → 95 %) — picks the cleanest available scene per incident.

**Useful for.** Vessel ID confirmation (you can read the hull, see the wake); port activity (count vessels in slips); visible oil sheen.

**Caveats.** Daylight only; useless under cloud. Baltic is cloudy roughly **70 %** of the time, so for any specific date the chances of a clean Sentinel-2 image are slim. Always pair with Sentinel-1.

**Format / how to query.** Same as Sentinel-1; crops at `s3://edth2026-baltic/optical/incident=*/`.

**License.** Free, Copernicus Open Access. Same attribution as Sentinel-1.

---

## Umbra + Capella — commercial SAR open data

**What it is.** Two commercial SAR constellations (Umbra Lab, Capella Space) that publish a curated sample of their imagery for free as "open data" via anonymous S3 buckets.

**What it provides.** Higher resolution than Sentinel-1 (Umbra: down to 0.25 m spotlight; Capella: 0.5 m). Baltic coverage is **sparse and opportunistic** — there is no scheduled revisit; you get what they happened to image.

**What's in our copy.** STAC catalogs walked, Baltic-intersecting scenes enumerated in `data/reference/commercial_sar_scenes.csv`. We did NOT bulk-download — these are leads to fetch on-demand if a specific incident has commercial coverage.

**Useful for.** Spot-checks where Sentinel-1's 10 m isn't enough (e.g. confirming a specific vessel was at a specific spot at a specific time). Demo "wow factor".

**Caveats.** **Capella is CC-BY-NC** — non-commercial only. Replace if commercialising. Umbra is CC-BY.

**License.** Umbra: CC-BY 4.0. Capella: CC-BY-NC 4.0.

---

## EMODnet Human Activities — authoritative offshore infrastructure

**What it is.** European Marine Observation and Data Network — the EU's official offshore infrastructure portal. Government-sourced, peer-reviewed, gold-standard for any "where is the pipeline / wind farm / cable" question that needs to stand up to scrutiny.

**What it provides** (our subset).
- `emodnet_pipelines.geojson` — 520 features, authoritative offshore pipeline routes
- `emodnet_cables_combined.geojson` — 300 features, national submissions merged (DE, NL, NO complete; Baltic states sparser — see *Caveats*)
- `emodnet_windfarmspoly.geojson` — 159 wind farm footprints
- `emodnet_windfarms_point.geojson` — 124 individual turbine locations

**Update cadence.** 1–2x per year, depending on layer.

**Useful for.** Trusted infrastructure layer for the criticality score. When a vessel-position scoring engine needs to answer "is this anchor sitting on top of an active pipeline?", EMODnet is the source it should defer to.

**Caveats.** Cable coverage is **uneven** — Germany, Netherlands, Norway submit comprehensive data; the eastern Baltic (Estonia, Latvia, Lithuania, Poland, Finland) is sparser. This is the gap Orange Marine cable-route data would fill if Alexis's CEO contact comes through.

**Format / how to query.** Local GeoJSON in `data/geo/`. Load with GeoPandas:
```python
import geopandas as gpd
cables = gpd.read_file("data/geo/emodnet_cables_combined.geojson")
```

**License.** CC-BY 4.0. Attribution: *"EMODnet Human Activities"*.

---

## OpenStreetMap — cables, pipes, ports, naval bases, refineries, wind

**What it is.** Community-tagged geographic data via the Overpass API. Complements EMODnet by including infrastructure that's known but not officially submitted to government databases.

**What it provides** (our subset, all in `data/geo/`):
- `submarine_cables.geojson` — 6,238 features. Includes C-Lion1, BCS East-West, Estlink, Baltika, plus older/decommissioned routes EMODnet doesn't carry.
- `submarine_power_cables.geojson` — 610 features
- `pipelines.geojson` — 4,659 features (combines onshore + offshore)
- `ports.geojson` — 3,037 features (includes commercial + leisure; filter on `harbour=*` tag)
- `naval_bases.geojson` — 18 features
- `refineries_lng.geojson` — 652 refineries + LNG terminals
- `offshore_wind.geojson` — 68 wind farm areas
- `offshore_platforms.geojson` — 13 offshore platforms

**Coverage.** Global; we filter to Baltic bbox in the fetch script.

**Useful for.** Catching cables and pipes EMODnet misses (especially in the eastern Baltic), and as the only practical source for naval bases / refineries / individual ports.

**Caveats.** **Cable route geometries are often schematic** — drawn from public press releases or news maps, not from survey data. Treat the existence and rough corridor as authoritative; treat the exact lat/lon points with scepticism. EMODnet is the better source when available.

**Refresh.** `python scripts/geo/fetch_osm_layers.py`

**License.** ODbL 1.0. Attribution: *"© OpenStreetMap contributors"*.

---

## OpenStreetMap seamarks — TSS, anchorages, lighthouses, buoys, wrecks, fairways

**What it is.** The OpenSeaMap subset of OSM — navigational features tagged using IHO S-57 conventions. Critical for distinguishing "vessel is in a designated anchorage" (normal) vs. "vessel is anchored in the middle of a TSS over a cable" (anomalous).

**What it provides** (all in `data/geo/`):
- `osm_tss.geojson` — 371 Traffic Separation Scheme segments
- `osm_restricted_areas.geojson` — 1,277 restricted / military / no-fishing zones
- `osm_anchorages.geojson` — 583 designated anchorages
- `osm_lighthouses.geojson` — 5,115 lighthouses (useful as geographic landmarks)
- `osm_buoys.geojson` — 41,219 buoys (cardinal / lateral / special)
- `osm_wrecks.geojson` — 1,051 mapped wrecks (some are radar/SAR-relevant false-positives)
- `osm_fairways.geojson` — 831 fairway centerlines

**Useful for.** Context for any anomaly score. A loitering vessel inside `osm_anchorages` is unremarkable; the same loitering pattern 5 km off a designated anchorage and 200 m off a known cable corridor is the signal.

**Caveats.** Restricted-area coverage is uneven by country. Buoy positions can be slightly stale relative to current IALA notices.

**Refresh.** `python scripts/geo/fetch_osm_seamarks.py`

**License.** ODbL 1.0.

---

## HELCOM — Baltic shipping accidents, spills, dredging, fishing intensity

**What it is.** Helsinki Commission's MADS (Map And Data Service) — the regional environmental + maritime authority for the Baltic. Multi-decade observation record.

**What it provides** (all in `data/geo/`):
- `helcom_shipping_accidents.geojson` — **4,932** reported Baltic shipping accidents (collisions, groundings, fires, sinkings) with type and date
- `helcom_detected_spills.geojson` — **5,838** oil/substance spills detected (mostly via aerial surveillance + satellite)
- `helcom_ais_passage_crossings.geojson` — 14 reference passage-line crossings (useful for traffic-flux baselining)
- `helcom_dredging_sites_*.geojson` — dredging activity, points + areas
- `helcom_disposal_sites_areas.geojson` — 1,668 designated disposal site polygons
- `helcom_fishing_intensity_total_2016_2021.geojson` — 10,000 cells of fishing intensity (hours/year)

**Time range.** Accidents: 1989–2024. Spills: 1998–2024. Fishing: 2016–2021.

**Useful for.** **Baseline rate of incidents** — distinguishing "another anchor-drag accident in a high-traffic zone" from "anomalous cable damage in a normally quiet area". Also useful for ground-truthing the incident register's "accidental vs. suspicious" attribution.

**Caveats.** Spill detections are subject to weather + surveillance gaps; absence does not mean none happened. Accident reporting depth varies by country.

**License.** Free with attribution.

---

## Bathymetry — GMRT sea floor grid

**What it is.** Global Multi-Resolution Topography (Lamont-Doherty Earth Observatory) — merged ship-survey + satellite-derived sea floor depths.

**What it provides.** `bathymetry_baltic.nc` — NetCDF grid covering Baltic + North Sea, depths in metres negative-below-sea-level. Resolution varies (~100 m in well-surveyed shallow areas, coarser offshore).

**Useful for.** Cable burial-depth context, shallow-water minefield reasoning, "can this draft fit here" filters for vessel candidates.

**Caveats.** Free for non-commercial use only. Cite Ryan et al. (2009) if used in any publication.

**License.** Free non-commercial; commercial users must license through Marine Geoscience Data System.

---

## Marine weather — Open-Meteo Marine + ERA5 historical

**What it is.** Per-incident hourly atmospheric + sea-state record. Open-Meteo Marine API for waves/swell, plus ERA5 reanalysis (ECMWF) for wind, temperature, surface pressure.

**What it provides.** For each of the 9 incidents (and ±14 days around them):
- Significant wave height + direction + period
- Wind speed + direction at 10 m
- Sea-surface temperature
- Surface pressure

Hourly resolution.

**Useful for.** **Ruling out the weather as a cause.** When the Eagle S dragged the anchor through Estlink-2 on Dec 25 2024, sea state was Beaufort 2–3 (mild) — the "ship lost control in heavy weather" defence falls apart on the data. This dataset is the receipt for that argument.

**Format / how to query.** JSON per incident at `data/reference/marine_weather/INC-*.json`.

**License.** CC-BY 4.0 (Open-Meteo) + Copernicus ERA5.

---

## Marine Regions EEZ — VLIZ world EEZ

**What it is.** Flanders Marine Institute's authoritative world EEZ polygon dataset. Used for any "whose waters is this vessel in?" question.

**What it provides.** `marine_regions_eez_baltic.geojson` — 12 EEZ polygons covering Denmark, Sweden, Finland, Estonia, Latvia, Lithuania, Poland, Germany, Russia, Norway, plus adjacent.

**Useful for.** Attribution context (e.g. incident inside vs. outside Estonian EEZ has different jurisdictional weight); cueing prioritisation by zone responsibility.

**Caveats.** Some EEZ boundaries in the Baltic are disputed (e.g. Russia-Ukraine, certain median-line negotiations). VLIZ uses the published reference baseline; not necessarily the de-facto operational boundary.

**License.** CC-BY 4.0. Attribution: *"Flanders Marine Institute (VLIZ)"*.

---

## Natural Earth basemap — CC0 public-domain vector

**What it is.** Standard public-domain basemap layers used by virtually every map renderer.

**What it provides.** Countries (50 m + 10 m), coastlines (10 m), ports, ocean polygon, rivers, urban areas — all clipped to the Baltic region.

**Useful for.** Any cartographic context. Burn the country fills + coastlines first, then everything else on top.

**License.** CC0 (Public Domain). No attribution required (recommended).

---

## Sanctions — OFAC + UK OFSI + EU FSF

**What it is.** Combined maritime sanctions list from three authoritative jurisdictions:
- **OFAC SDN** — U.S. Treasury Specially Designated Nationals list
- **UK OFSI** — UK Office of Financial Sanctions Implementation
- **EU FSF** — EU Financial Sanctions Files (via OpenSanctions normalisation)

**What it provides.** `sanctions_maritime.csv` — **1,773 entries** with IMO number (where listed), vessel name, current and historical names, flag, owner, manager, program (e.g. "RUSSIA-EO14024", "IRAN"), reason, listing date.

**Useful for.** Exact-match lookups on any vessel of interest. If a flagged AIS contact matches a sanctioned IMO, the analyst gets an immediate justification chain.

**Caveats.** **EU FSF data is provided via OpenSanctions, which is CC-BY-NC** — fine for the hackathon and internal demos, but a commercial product would need to either license OpenSanctions or revert to the EU's own (less-clean) consolidated XML. See [`data/SOURCES.md`](data/SOURCES.md) § *Commercial-use guardrails*.

**Refresh.** `python scripts/reference/fetch_sanctions.py`

**License.** OFAC: public domain (US Gov). OFSI: OGL v3.0. OpenSanctions: CC-BY-NC 4.0.

---

## KSE Russian shadow fleet tracker

**What it is.** Quarterly tracker published by the Kyiv School of Economics Institute — the de-facto open-source authority on the Russian shadow oil-tanker fleet.

**What we have.** The public PDF parsed into structured data: top ship managers + top buyers by quarter, by country, by vessel count. Aggregate stats, not vessel-level.

**What we want but don't have.** The vessel-level list (IMO → manager → buyer → estimated revenue) — KSE keeps that internal. Email sent to KSE Institute requesting research access; awaiting reply.

**Useful for.** Patterns ("manager X is over-represented in shadow-fleet listings → flag any AIS contact under that manager"). Confirming a vessel is plausibly part of the shadow fleet given its ownership chain.

**Caveats.** Aggregate-only without the vessel-level dataset. The KSE quarterly cadence means the freshest list is ~1–3 months old.

**License.** Research-only; ask before redistribution. Attribution: *"Kyiv School of Economics"*.

---

## Equasis — per-IMO vessel registry

**What it is.** The industry-standard vessel registry consortium (run by France's transport ministry + EU + flag states). Free to access with registration; **no public API** — we use a session-based form login + HTML scrape, on-demand only.

**What it provides** (per IMO). Vessel name + name history; current and historical ownership; manager; ISM company; classification society; flag history; port-state inspection record (which port, which deficiencies, which year).

**Useful for.** **Unmasking shell-company ownership.** A vessel of interest with an opaque on-paper owner often reveals a clearer pattern through Equasis's historical chain. Also the cleanest source for IMO-level metadata.

**Caveats.** **Per-vessel lookup only** — bulk scraping violates their ToS. Designed for "we have 5 suspect IMOs, give us full profiles", not "give us everyone".

**Refresh.** `python scripts/reference/equasis_lookup.py --imo 9329760`

**License.** Free with registration; redistribution of derived data restricted. Discuss before publishing.

---

## Global Fishing Watch — per-vessel events

**What it is.** GFW v3 API (Global Fishing Watch, the SkyTruth + Oceana + Google joint project). They continuously process the global AIS feed and emit derived **events** — behavioural classifications.

**What it provides** (event types, per vessel).
- **Port visits** — vessel entered/exited a port boundary, with duration
- **Loitering** — vessel below speed threshold for N hours, with anchor point
- **Encounters** — two vessels rendezvous at sea (often indicative of STS transfers)
- **AIS gaps** — vessel transponder went dark for >N hours
- **Fishing** — apparent fishing activity, with effort hours

**What's in our copy.** 25 vessel-event rows for the named incident suspects (Eagle S, Yi Peng 3, Vezhen, Fitburg, Newnew Polar Bear, etc.) at `s3://edth2026-baltic/reference/gfw_events/`.

**Useful for.** Pre-computed behavioural anomaly features. Rather than re-deriving "did the Eagle S go dark for 6 hours before the Estlink-2 cut?" from raw AIS, you can read GFW's answer directly.

**Caveats.** GFW's event detection has thresholds we don't control; their definition of "loitering" is theirs, not ours. For final hackathon scoring, derive your own features from the raw AIS too.

**Refresh.** `python scripts/ingest/fetch_gfw.py` (per-IMO).

**License.** Free with API token; attribution required: *"Global Fishing Watch"*.

---

## Incidents register — project-curated

**What it is.** Hand-curated ground-truth: the 9 well-documented Baltic infrastructure incidents from Nord Stream (Sep 2022) to Sventoji cable cut (Sep 2025) to Latvia/Sweden Vezhen (Jan 2026).

**What it provides.** `data/reference/incidents.csv` — for each incident: date, infrastructure type (gas pipe / data cable / power cable), AOI bbox, named suspect vessels (IMOs), attribution taxonomy (deliberate / accidental / unknown), and curated source links (press, government statements, OSINT reports).

**Useful for.** Replay during the demo. Ground truth for any classifier you train. Source of the AOI bboxes used by the Sentinel imagery downloaders.

**License.** Project-internal (MIT-equivalent if released).

---

## Kaggle — ML training datasets

**What it is.** 10 maritime-domain datasets queued/downloaded for use as training data if any team member wants to train (or fine-tune) a vessel-detection model.

**What's included.**
- Drone-video Ship Detection Sample (SDS) — labelled video frames of vessels from drones
- HRSID — High-Resolution SAR Image Dataset (SAR ship detection)
- LS-SSDD — Large-Scale SAR Ship Detection Dataset
- MASATI — Maritime Satellite Imagery dataset (Sentinel-2 + Maxar)
- AFO — Aerial Floating Objects
- Ports — labelled port-region photos
- Kattegat AIS — sampled AIS tracks for ML
- + 3 supplementary maritime datasets

**Total volume.** 16.5 GB at `s3://edth2026-baltic/kaggle/`.

**Useful for.** Pre-training or fine-tuning ship-detection CV models. Not used by the cueing engine itself; provided as training material for anyone who wants to extend.

**Caveats.** Licenses vary per dataset — check the individual dataset description on Kaggle before redistributing.

**License.** Per Kaggle terms + dataset-specific. See [`data/SOURCES.md`](data/SOURCES.md) for the matrix.

---

## When in doubt

- **License/attribution questions** → [`data/SOURCES.md`](data/SOURCES.md)
- **How to set up access** → [`ONBOARDING.md`](ONBOARDING.md)
- **How to refresh a dataset** → `scripts/<category>/fetch_*.py` (each script is idempotent + skip-if-exists)
- **What the data is being used for** → [`PLAN.md`](PLAN.md)
