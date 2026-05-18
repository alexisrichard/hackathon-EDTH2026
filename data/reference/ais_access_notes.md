# AIS data access — what works, what's gated

Operational notes for each AIS source. Updated 2026-05-18 during prep.

## Danish AIS — Danish Maritime Authority

**Status: WORKING. Bulk download in progress.**

- Public S3 bucket: `s3://aisdata.ais.dk/` (eu-central-1, anonymous)
- Path-style HTTPS URL required (bucket name has dots → wildcard SSL cert mismatch on virtual-host style)
- Layout: 2006–2024-Feb monthly zips (~15 GB each), 2024-Mar onwards daily zips (~500 MB each), 2025 most recent + 2026 daily zips at bucket root
- License: free, no restrictions
- Coverage: Danish waters + western Baltic Sea + parts of Skagerrak/Kattegat. **Includes some Gulf of Finland coverage** because AIS receivers and satellite pickups span the whole Baltic.

Pipeline: `scripts/ingest/danish_ais.py` — stream-extract zip → filter to Baltic bbox → per-day Parquet → upload to `s3://edth2026-baltic/ais/parquet/source=danish/`.

## Finnish AIS — Fintraffic / Digitraffic

**Status: BULK HISTORICAL DOWNLOAD GAP. Real-time API works.**

- Real-time/live API: `https://meri.digitraffic.fi/api/ais/v1/locations` (GeoJSON, requires `Accept-Encoding: gzip`)
- Historical via `/api/ais/v1/locations?mmsi=<n>&from=<ts>&to=<ts>` — per-MMSI only, not bulk by area
- License: CC-BY 4.0, free
- Swagger: `https://meri.digitraffic.fi/swagger/openapi.json`

**Gap:** there is no public bulk-download archive of historical Finnish AIS *positions*. Digitraffic's `/locations` endpoint is per-MMSI lookup, which means we'd have to:
1. Get list of all MMSIs that operated in Gulf of Finland in our target window (this list itself is hard)
2. Query each MMSI's history → thousands of API calls per day

**Workaround for the hackathon:**
- Danish AIS likely covers Gulf of Finland reasonably (S3 bucket aggregates satellite + terrestrial receivers)
- Use Digitraffic's per-MMSI query for the specific vessels we flag (Eagle S, Fitburg, etc.) — bounded, cheap
- For bulk coverage of Gulf of Finland, contact Fintraffic directly: `digitraffic@fintraffic.fi`. They've historically shared bulk extracts on research request.

## Norwegian AIS — Kystverket

**Status: GATED — beta download portal, no obvious bulk URL.**

- Beta UI: `https://ais-public.kystverket.no/` (interactive web download)
- Historical search: `https://hais.kystverket.no/`
- API portal: `https://kystdatahuset.no/` (Swagger documentation broken, paths return 404)
- License: NLOD 2.0 (Norwegian Licence for Open Government Data, similar to CC-BY)

**Why we deprioritize Norway:** the Baltic Sea is not Norwegian waters. Norwegian AIS receivers primarily cover the North Sea, Norwegian Sea, and Arctic. For our Baltic project, Danish + Finnish would already cover most of the action.

If we need a few specific cross-strait events, manually fetch from `hais.kystverket.no` for the MMSI + date.

## AISStream.io — live global stream

**Status: WORKING via WebSocket.**

- API key required (free signup at `https://aisstream.io/`)
- Live only, no archive retention
- License: free for development; commercial use needs paid tier

**Useful for:** the live-mode demo on Sunday at the hackathon. Not useful for prep / historical replay.

## Global Fishing Watch

**Status: Research access only.**

- API: `https://gateway.api.globalfishingwatch.org/`
- Strong on fishing-vessel ID + behavior labeling
- License: free for research; sign up at `https://globalfishingwatch.org/our-apis/tokens`
- Useful if we want fishing-class behavior models

## What I deferred to manual action

Per "what works, what's gated" — items that need a human to sign up or email:

- KSE Russian Shadow Fleet — `kse@kse.org.ua`; manual fetch into `data/reference/raw/kse_shadow_fleet_YYYYMMDD.xlsx`
- Fintraffic bulk historical AIS — direct email request
- AISStream.io API key — sign up at `aisstream.io`
- Copernicus account for full Sentinel-1/-2 downloads — `dataspace.copernicus.eu`
- Kaggle API token — `kaggle.com/settings/account` (see `kaggle_datasets_TODO.md`)
