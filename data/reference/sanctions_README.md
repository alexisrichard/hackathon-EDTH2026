# sanctions_maritime.csv

Maritime-relevant sanctions data, normalized from US (OFAC SDN), EU, and UK (OFSI) sources.
Refreshed by running `scripts/reference/fetch_sanctions.py`.

## Schema

| Column | Description |
|---|---|
| `source` | `OFAC_SDN`, `EU_consolidated`, `UK_OFSI` |
| `entry_id` | Source-specific stable identifier |
| `name` | Primary vessel or entity name |
| `type` | `vessel`, `shipping_entity`, or source-specific |
| `country` | Best-guess country of origin or flag |
| `imo` | IMO number (7 digits), where available |
| `mmsi` | MMSI number, where available |
| `flag` | Vessel flag state, where distinct from country |
| `owner` | Registered owner (OFAC only) |
| `notes` | Raw description string from source |
| `fetched_at` | UTC timestamp of the fetch run |

## Current coverage (as of 2026-05-18)

| Source | Entries | Notes |
|---|---|---|
| OFAC SDN | 1,480 | Vessel-typed entries only. IMO present for most; MMSI for many. Strong Iran/Cuba/Venezuela coverage. |
| UK OFSI | 219 | Ships + shipping-related entities. Heavy on Russian shipping/oil-trading shell companies. |
| EU consolidated | 0 | URL `webgate.ec.europa.eu/fsd/fsf/...` returns 403. See "Known gaps" below. |

## Known gaps

### EU consolidated list
The canonical URL `https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content` requires a token. Workarounds, in order of preference:

1. **EU Sanctions Map** — visit `https://www.sanctionsmap.eu/`, register, request export.
2. **EU Open Data Portal** — `https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions` exposes the dataset; the *download* link is what we need to wire into the script.
3. **OpenSanctions.org** — third-party aggregator with normalized EU + US + UK data; their CSV downloads are free for non-commercial use. URL: `https://www.opensanctions.org/datasets/eu_fsf/`.

### KSE Russian Shadow Fleet Tracker
The most operationally relevant source for our threat model. Kyiv School of Economics maintains a regularly-updated dataset of Russian shadow-fleet tankers.

**Access (as of May 2026):** the dataset is *not* a stable HTTPS download. Steps:

1. Go to `https://kse.ua/about-the-school/news/russian-shadow-fleet/` (or search "KSE shadow fleet tracker").
2. KSE publishes an Excel/CSV updated roughly monthly; check the latest news post for the download link.
3. Some access requires email signup or an academic-research request to `kse@kse.org.ua`.
4. Save the result as `data/reference/raw/kse_shadow_fleet_YYYYMMDD.xlsx`.
5. Add a parser to `scripts/reference/fetch_sanctions.py` that reads the Excel, extracts IMO/MMSI/vessel name, and merges with `source=KSE_SHADOW_FLEET`.

**Why this matters:** Eagle S, Yi Peng 3, Newnew Polar Bear, Vezhen — the named incident vessels — are NOT on OFAC. They are *suspected* shadow fleet, tracked by KSE but not formally sanctioned. Without KSE, our model has a blind spot for exactly the demo vessels we care about.

### Equasis vessel registry
Login-required (`https://www.equasis.org`). For each MMSI we flag during runtime, we'd hit Equasis on-demand for owner/flag history. Not a bulk-download. Defer to during-event integration.
