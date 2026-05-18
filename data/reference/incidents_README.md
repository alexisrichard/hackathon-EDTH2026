# incidents.csv

Hand-curated timeline of Baltic Sea undersea-infrastructure damage events since 2022. Used for:

1. Hero demo replays (§6, §9 of PLAN.md)
2. Model calibration — labeled positives for the scoring weights
3. Storytelling in the pitch

## Schema

| Column | Description |
|---|---|
| `incident_id` | Stable identifier, format `INC-YYYY-MM-DD` (with `-N` suffix if multiple events on same day) |
| `date_utc` | Event date in UTC (best estimate from sources) |
| `time_utc` | Time of incident in UTC, `HH:MM`, or empty if unknown |
| `name` | Short human-readable label |
| `vessel_name` | Primary suspect vessel, or `unknown` |
| `vessel_flag` | Flag state |
| `vessel_type` | One of: `bulk_carrier`, `container_ship`, `oil_tanker`, `general_cargo`, `fishing`, `tug`, `military_aux`, `passenger`, `other`, `unknown` |
| `infrastructure_name` | Named asset(s) damaged |
| `infrastructure_type` | One of: `telecom_cable`, `power_cable`, `pipeline`, `mixed`, `wind_farm`, `other` |
| `lat_approx`, `lon_approx` | Best public estimate of damage location, decimal degrees WGS84 |
| `region` | Free-text region description |
| `attribution_status` | See taxonomy below |
| `location_precision` | `gps_fix`, `segment_midpoint`, `event_centroid`, `centroid_of_multiple_blast_sites`, `region_only` |
| `sources` | Semicolon-separated URLs |
| `notes` | Free-text |

## `attribution_status` taxonomy

| Value | Meaning |
|---|---|
| `confirmed` | Court conviction or official state admission |
| `strong` | Vessel detained, anchor recovered, investigation active, no acquittal yet |
| `suspected` | Vessel of interest identified but no detention or no clear link |
| `dismissed` | Investigation closed without charges (e.g., prosecutor failed to prove intent) |
| `accidental` | Official ruling of accidental damage |
| `disputed` | Multiple conflicting positions; inquiry inconclusive |
| `unknown` | No attribution determined |

**Important for modeling:** A `dismissed` or `accidental` ruling does NOT invalidate the row as a positive label. The behavioral *pattern* (anchor drag over a cable, AIS dropout near critical infrastructure, etc.) is exactly what our scoring engine should catch — regardless of whether a court later found intent. Use these rows for training feature distributions; use `confirmed` + `strong` rows for narrative + jury appeal in the pitch.

## Current coverage (as of 2026-05-18)

**9 events**, covering the named Baltic incidents from Sep 2022 through Jan 2026:

| # | Date | Event | Status |
|---|---|---|---|
| 1 | 2022-09-26 | Nord Stream 1+2 explosions | disputed |
| 2 | 2023-10-08 | Balticconnector + EE-FI cables (Newnew Polar Bear) | strong |
| 3 | 2024-11-17 | BCS East-West (Yi Peng 3) | disputed |
| 4 | 2024-11-18 | C-Lion1 (Yi Peng 3) | disputed |
| 5 | 2024-12-25 | Estlink 2 + 4 telecom cables (Eagle S) | dismissed |
| 6 | 2025-01-26 | Latvia-Sweden Ventspils-Gotland (Vezhen) | accidental |
| 7 | 2025-02-21 | Germany-Finland Cinia data cable | suspected |
| 8 | 2025-12-31 | Finland-Estonia Elisa data cable (Fitburg) | strong |
| 9 | 2026-01-02 | Lithuania-Latvia Sventoji-Liepaja | suspected |

## Research backlog — getting to ~50 events

The original plan target of ~50 events is realistic only if we expand the definition beyond "named cable cut with suspect vessel" to include:

- **Pre-2022 baseline incidents** (cable repair logs from ICPC; helps the model learn what "normal" damage looks like vs the post-2022 sabotage wave)
- **AIS-dropout events near critical infrastructure** without confirmed damage (suspicious behavior, no cable cut)
- **Slow-speed transits over named cables** with shadow-fleet vessels (behavioral pattern even without damage)
- **NATO Baltic Sentry interceptions** (post-Jan 2025) where suspect vessels were investigated but no damage occurred

Specific sources to scrape, in order of effort/value:

1. **Bairdmaritime Factbox** — `https://www.bairdmaritime.com/marine-projects/marine-infrastructure/factbox-suspected-underwater-cable-sabotage-in-the-baltic-sea` — already cross-referenced for current entries; re-check monthly for new ones.
2. **gCaptain timeline** — `https://gcaptain.com/timeline-of-suspected-underwater-sabotage-in-baltic-sea/` — maritime industry compilation.
3. **Wilson Center map** — `https://www.wilsoncenter.org/article/mapping-undersea-infrastructure-attacks-baltic-sea` — academic compilation with coordinates.
4. **Wikipedia "2024 Baltic Sea submarine cable disruptions"** — `https://en.wikipedia.org/wiki/2024_Baltic_Sea_submarine_cable_disruptions` — references for source-chasing.
5. **Atlantic Council issue brief** — `https://www.atlanticcouncil.org/in-depth-research-reports/issue-brief/how-the-baltic-sea-nations-have-tackled-suspicious-cable-cuts/` — policy-grade compilation.
6. **ICPC Cable Damage Statistics** — `https://www.iscpc.org/` — annual reports; the only authoritative source for *all* cable damage including pre-2022 baseline.
7. **KSE Russian Shadow Fleet incident log** — KSE Institute monthly reports document shadow-fleet vessels' suspicious transits even without damage. Email-request access.
8. **ENISA telecom resilience reports** — `https://www.enisa.europa.eu/topics/incident-reporting` — EU's incident reporting summary catches more than the press-covered events.

**Pragmatic split:** keep `incidents.csv` to confirmed-damage events (target ~15 well-documented). Create a separate `suspicious_behaviors.csv` for behavioral observations without confirmed damage (target ~50-100 entries from KSE / ENISA / press). The model uses #1 for calibration and #2 for behavioral feature distributions.

## Editing convention

- Append new entries; preserve historical ones even if attribution changes (update the `attribution_status` field and explain in `notes`).
- One row per damaged asset on a given day even if same vessel — but you can bundle if all asset damage shares a single anchor-drag pass.
- When a court ruling changes attribution (e.g., Eagle S → dismissed), update the row + add a note line; never delete.
- Date in UTC. If you only have local time, convert (e.g., EET is UTC+2 in winter, UTC+3 in summer).
