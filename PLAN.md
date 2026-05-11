# Project [name TBD] — Maritime Cueing for Undersea Infrastructure Protection

**EDTH 2026 Paris · June 12–14**
**Team of 3:** engineer/entrepreneur (telecom, cyber, submarine cables) · engineer · cyber + defense

---

## 1. One-line pitch

A maritime cueing engine that watches every AIS-broadcasting vessel in the Baltic, scores each one for behavioral coherence and proximity to strategic infrastructure, and tells operators *where to point their scarce ISR sensors next*.

## 2. Strategic context

Naval warfare is going through the same asymmetry shock that land warfare went through with cheap drones. A €20k USV can sink a billion-euro frigate. A single bulk carrier dragging an anchor can sever a cable carrying a meaningful share of a region's internet traffic.

Since 2022, the Baltic has become the live testing ground for this:

| Date | Event |
|---|---|
| 26 Sep 2022 | Nord Stream 1 + 2 explosions |
| 8 Oct 2023 | Balticconnector pipeline + Estonia–Finland telecom cable cut by *Newnew Polar Bear* |
| 17–18 Nov 2024 | C-Lion1 + BCS East-West cables cut by *Yi Peng 3* |
| 25 Dec 2024 | Estlink 2 power cable + 4 telecom cables cut by *Eagle S* (Russian shadow fleet) |
| 26 Jan 2025 | Latvia–Sweden cable cut |

The doctrine response is real and named:

- **France** — *Stratégie ministérielle de maîtrise des fonds marins* (Feb 2022). Active seabed warfare doctrine.
- **NATO** — Critical Undersea Infrastructure Cell, stood up 2024.
- **EU** — recommendation on submarine cable security (Feb 2024).

EDTH Paris is a near-perfect venue for this.

## 3. The problem we're solving

> **Defenders are not lacking alerts. They are lacking prioritization.**

The ocean is too big to watch continuously. Satellites are scarce, expensive, and tasked. AIS is continuous and free but drowning in noise — and frequently spoofed. Real ISR analysts allocate their high-quality sensors based on tip-offs from cheaper continuous sources. This is called the **tip-and-cue problem**, and the cueing layer is mostly absent or proprietary.

Our system *is* that cueing layer.

The output is **not** "this vessel is suspicious." The output is **"task your next satellite pass on this 50 km box at 14:00, and here is the reasoning."**

## 4. Plausible customers

Worth knowing because it shapes UX and pitch framing. Pick one as the primary on Friday:

- **NATO Critical Undersea Infrastructure Cell** — multi-national, undersea-focused, exactly our problem space.
- **French Marine Nationale (CECMED / ALFAN)** — French seabed warfare doctrine maps to this directly.
- **EMSA (European Maritime Safety Agency)** — pan-European, civil maritime focus.
- **Telco consortia (ASN, Orange Marine, SubCom)** — own the cables; would buy infrastructure-protection services.
- **Marine insurers (Lloyd's of London syndicates)** — underwrite cable repair, sanctions risk; have real budget.

Default for the demo: NATO CUI Cell. Most legible to a defense audience.

---

## 5. The system

Three layers, fused into a single suspicion score per vessel and per area.

### 5.1 Behavioral coherence engine (the ML core)

Per-class vessel behavior models: fishing, tanker, container, bulk carrier, RoPax, research, military auxiliary, tug, pleasure.

For each vessel, score how coherent its actual behavior is with the *normal* behavior for its declared class in this area at this time.

Examples:
- A fishing trawler not over a fishing ground, transiting like a tanker → flag.
- A container ship looping in open water for hours → flag.
- A bulk carrier slowing to 2 knots over a known cable → strong flag.

This catches **AIS spoofing** and **intent inconsistency** in a way pure kinematic anomaly detection cannot. It also produces interpretable alerts ("declared X, behaving like Y, in Z context"), which matters for a defense audience that won't trust a black box.

Relevant literature: Pallotta, Vespe et al. (maritime trajectory mining), recent transformer-based AIS work.

### 5.2 Strategic criticality surface

A spatial heatmap of how strategically important each cell of ocean is. Built from public/open data:

- Submarine telecom cables (TeleGeography, OSM)
- Power cables (Estlink, NorNed, etc.)
- Pipelines (Nord Stream remains, Balticconnector, Yamal-Europe extensions)
- Naval bases (OSM `military=naval_base`)
- Major commercial ports (Natural Earth + OSM)
- Refineries, LNG terminals (OSM, OpenInfraMap)
- Offshore oil/gas platforms (OSPAR Commission)
- Offshore wind farms (4C Offshore, OSM)
- Maritime chokepoints (manual: Skagerrak, Gulf of Finland, Øresund, Great Belt)
- Naval exercise zones (national hydrographic offices, NOTMARs)

Vessel suspicion gets *multiplied* by local criticality. A weird vessel in the open Atlantic is whatever; the same vessel over Estlink 2 is an alarm.

### 5.3 Sensor fusion

- **AIS** — continuous, cheap, spoofable. The baseline.
- **Sentinel-1 SAR** — free, ~6–12 day revisit. Sees ships through cloud and at night. Lets us detect AIS-quiet vessels (visible to radar, not in AIS feed = "dark vessel candidate").
- **Sentinel-2 optical** — free, ~5 day revisit, cloud-limited. Useful when clear.
- **Umbra Open Data / Capella Open Data** — free archive of high-res commercial SAR. Hero shots on incident dates.
- **(Stretch) DAS feed from a partner team** — distributed acoustic sensing on submarine cables. Mock-data-first integration via a clean schema; real feed swapped in if a partner team materializes.

### 5.4 The combined score

```
suspicion(vessel, t) = kinematic_anomaly(vessel, t)
                     × (1 − class_coherence(vessel, t))
                     × local_criticality(vessel.position)
                     × dark_modifier(vessel, t)
```

Each term is interpretable. When a vessel is flagged, the dashboard shows the breakdown: *"flagged because: declared fishing vessel, trajectory inconsistent with fishing class (0.12), within 2 km of submarine cable (criticality 0.91), AIS dropout in last 47 minutes."*

### 5.5 The cueing output

Per-area scoring, aggregated and ranked:

- Top-N geographic boxes ranked by expected information value of a sensor pass.
- Per-box justification (which vessels are driving the score).
- "Task next" queue: a prioritized list of (area, time, recommended sensor type) tuples.

This is the real product. Anomaly detection is a means; tasking-recommendation is the end.

---

## 6. What it looks like

A web dashboard. Single screen, three panels:

1. **Map** (most of the screen). Vessel tracks, cable routes, criticality overlay, alert markers. Time-scrub bar at the bottom.
2. **Alert feed** (right sidebar). Top suspicious vessels right now, with one-click drill-in.
3. **Cueing panel** (bottom right). "Top 5 areas to task next" — boxes on the map with confidence and reasoning.

**Hero demo flow:**

> "It's December 24, 2024. Eagle S enters the Gulf of Finland. Watch the suspicion score climb as it slows over Estlink 2. Watch the cueing engine recommend tasking a satellite to this exact 30km box. Now watch the cable status flip red 14 minutes later."

Modes: replay (any week 2022 → today), live (AISStream.io feed), scenario (preloaded incident dates with explanations).

---

## 7. Data sources

### 7.1 AIS

| Source | URL | Coverage | Format | Volume (filtered) | Cost |
|---|---|---|---|---|---|
| Danish Maritime Authority | https://web.ais.dk/aisdata/ | DK + western Baltic | Daily CSV (RAR archives) since 2006 | ~80–150 GB filtered to Baltic 2022→ | Free |
| Finnish Fintraffic | https://www.traficom.fi (open data section) | Finnish waters incl. Gulf of Finland | API + downloads | ~40 GB | Free |
| Norwegian Kystverket | https://kystverket.no | Norwegian waters, partial Baltic | API | ~20 GB | Free |
| AISStream.io | https://aisstream.io | Global live feed via WebSocket | JSON streaming | Live only, no archive | Free with key |
| Global Fishing Watch | https://globalfishingwatch.org | Global, fishing-biased | API + CSV | Variable | Free for research |

**Strategy:** Danish + Finnish + Norwegian = near-complete western Baltic + Gulf of Finland coverage. Filter to bounding box (~52°N–66°N, 9°E–30°E), normalize schemas, store as Parquet partitioned by year/month.

### 7.2 Satellite imagery

| Source | URL | Type | Revisit | Cost |
|---|---|---|---|---|
| Sentinel-1 (ESA) | https://dataspace.copernicus.eu | SAR, all-weather | 6–12 days (Baltic) | Free |
| Sentinel-2 (ESA) | https://dataspace.copernicus.eu | Optical, cloud-limited | ~5 days | Free |
| Umbra Open Data | https://umbra.space/open-data | Commercial SAR, ~25 cm | Archive only | Free |
| Capella Open Data | https://www.capellaspace.com/data/gallery | Commercial SAR | Archive only | Free |
| Planet Labs Education | https://www.planet.com/markets/education-and-research/ | Optical, daily | Daily | Free if accepted |
| ICEYE | https://www.iceye.com | SAR, sub-daily on tasking | n/a | Paid; researcher access ad-hoc |

**Strategy:** Pull Sentinel-1/-2 scenes for incident dates ±7 days. Check Umbra/Capella archives for incident-date hits. Apply for Planet research access as a stretch.

### 7.3 Strategic infrastructure (criticality layer)

| Layer | Source | License |
|---|---|---|
| Submarine telecom cables | TeleGeography Submarine Cable Map | Free for non-commercial, may need to hand-trace from public sources for redistribution |
| Submarine cables (alt) | OSM `submarine_cable` tag | ODbL |
| Power cables (Estlink, NorNed, etc.) | ENTSO-E grid map, OSM | Mixed |
| Pipelines | OSM `man_made=pipeline` | ODbL |
| Ports | Natural Earth, OSM | Public domain / ODbL |
| Naval bases | OSM `military=naval_base` | ODbL |
| Refineries, LNG terminals | OSM, OpenInfraMap | ODbL |
| Offshore platforms | OSPAR Commission, OSM | Mixed |
| Offshore wind farms | 4C Offshore, OSM | Mixed |
| Maritime EEZ boundaries | Marine Regions (VLIZ) | CC-BY |
| Naval exercise zones | National hydrographic offices, NOTMARs | Public |

### 7.4 Reference data

| Layer | Source | Notes |
|---|---|---|
| EU sanctions list | https://www.sanctionsmap.eu | Consolidated EU restrictive measures |
| UK sanctions list | https://www.gov.uk/government/publications/the-uk-sanctions-list | OFSI |
| US sanctions list | https://sanctionssearch.ofac.treas.gov | OFAC SDN |
| Russian shadow fleet tracker | KSE Institute (Kyiv School of Economics) | Public dataset, regularly updated |
| Vessel registry (MMSI lookup) | ITU MARS database, Equasis | Free with registration |
| Vessel type / flag history | Equasis | Free, slow scraping |
| Incident timeline | Manual curation from press, ENISA, NATO CCDCOE | <50 events |

### 7.5 Volume estimate

| Layer | Filtered volume | Notes |
|---|---|---|
| AIS (DK+FI+NO, 2022→, Baltic bbox, per-minute) | ~150 GB | Parquet |
| Sentinel-1 (incident windows) | ~80 GB | GRD scenes |
| Sentinel-2 (incident windows, cloud-free) | ~50 GB | L2A scenes |
| Umbra/Capella (if hits) | ~20 GB | Variable |
| Geo + reference + incidents | <1 GB | GeoJSON, CSV |
| **Total** | **~300 GB** | |

S3 cost: ~$7–10/month at standard tier.

---

## 8. Pre-event preparation

**Goal:** arrive at the hackathon with all data downloaded, cleaned, and loadable. No application code. Build day-of.

### 8.1 S3 bucket layout

```
s3://edth2026-baltic/
├── ais/
│   ├── raw/                    # Original DK/FI/NO dumps
│   └── parquet/                # Cleaned, Baltic bbox, partitioned
│       └── year=YYYY/month=MM/
├── sar/
│   ├── sentinel1/
│   ├── umbra/
│   └── capella/
├── optical/
│   └── sentinel2/
├── geo/
│   ├── cables.geojson
│   ├── pipelines.geojson
│   ├── ports.geojson
│   ├── eez.geojson
│   ├── naval_bases.geojson
│   ├── refineries.geojson
│   └── platforms.geojson
├── reference/
│   ├── sanctions_eu.csv
│   ├── sanctions_uk.csv
│   ├── sanctions_us.csv
│   ├── shadow_fleet.csv
│   ├── vessel_registry.csv
│   └── incidents.csv
└── samples/
    └── notebooks/              # Starter analysis notebooks
```

### 8.2 Prep tasks

| # | Task | Effort | Owner |
|---|---|---|---|
| 1 | Provision S3 bucket + IAM credentials for team | 1 h | TBD |
| 2 | Write Danish AIS download + filter + parquet pipeline | 4 h | TBD |
| 3 | Run pipeline for Jan 2022 → present | 2 h compute | TBD |
| 4 | Same for Finnish AIS | 3 h | TBD |
| 5 | Same for Norwegian AIS | 2 h | TBD |
| 6 | Sentinel-1/-2 download for incident windows (Copernicus API) | 4 h | TBD |
| 7 | Check Umbra/Capella archives for Baltic hits | 2 h | TBD |
| 8 | Compile criticality layers (cables, ports, military, energy) | 5 h | TBD |
| 9 | Compile reference data (sanctions, shadow fleet, registry) | 3 h | TBD |
| 10 | Hand-curate incident timeline | 2 h | TBD |
| 11 | Write 2–3 starter notebooks (load AIS, plot tracks, query criticality) | 3 h | TBD |
| 12 | Brief the team on what's where + auth instructions | 1 h | TBD |
| **Total** | | **~32 h** | One person, or split 3 ways |

### 8.3 What we explicitly do NOT do before the hackathon

- ❌ Build the dashboard
- ❌ Train the ML model
- ❌ Implement the scoring engine
- ❌ Decide the final scope tier (decided Friday afternoon)

The fun is doing the work during the hackathon. Prep is purely data plumbing.

---

## 9. Scope tiers

Decide on Friday afternoon based on team energy and what's working.

### 9.1 Minimum (must ship Sunday)

- Web dashboard with Mapbox/MapLibre, time scrubber.
- Vessel tracks rendered from Parquet on S3 for one selected month.
- Criticality overlay (cables + naval bases minimum).
- One naive anomaly detector: speed-based (slow vessels near cables) or kinematic (sudden course changes).
- Replay of *one* incident (e.g., Eagle S / Christmas Eve 2024).

### 9.2 Strong (target)

Above, plus:

- Class-conditional behavioral coherence engine — trained on at least 3–4 vessel classes.
- Multi-incident replay (3–5 named incidents accessible via sidebar).
- Interpretable alert breakdown ("flagged because…").
- Top-N "areas to investigate" panel.
- Polished UX, clear demo script.

### 9.3 Stretch (bonus)

Above, plus:

- Sentinel-1 cross-check showing dark-vessel candidates (radar detection vs AIS).
- DAS partnership integration via mock schema (or real if a partner team is available).
- Active GPS-spoofing detector (impossible kinematics, identity collisions).
- AIS-spoofing-via-class-mismatch detection.
- Live mode using AISStream.io.

---

## 10. Technical approach (rough)

### 10.1 Stack suggestions

Light suggestions only — finalize on Friday.

- **Data:** DuckDB (local + S3 reads) and/or PostGIS for geospatial queries
- **Storage:** S3 + Parquet, GeoJSON for layers
- **Backend:** FastAPI (Python) — lets us share code with the ML side
- **Frontend:** React + deck.gl (or MapLibre) for the geo-heavy UI
- **ML:** scikit-learn / lightgbm for baseline, PyTorch if a transformer-based trajectory model becomes the right choice
- **Orchestration:** plain Python scripts + Makefile. No Airflow, no Kubernetes.

### 10.2 ML notes

- Behavioral coherence: train per-class trajectory models (HMM, autoencoder on resampled tracks, or transformer encoder on tokenized AIS sequences). Score = log-likelihood of observed track under declared-class model.
- Kinematic anomaly: classical features (speed, course change rate, stop frequency, spatial dispersion) → isolation forest or one-class SVM.
- Combine via the formula in §5.4. Calibrate weights on labeled incidents (manually labeled).

### 10.3 Mock-data philosophy

Every external data source has a mock generator. Real S3 data is the default; mocks are the fallback if S3 auth, network, or the venue WiFi flakes during the demo. Same for any DAS partner-team feed — mock first, real swapped in if available.

---

## 11. Pitch framing

A 5-minute pitch needs:

1. **The problem in one slide:** Baltic incident map + cost-of-cable-repair + "we don't lack alerts, we lack prioritization."
2. **Live demo:** Eagle S replay, alert fires, cueing engine recommends tasking, cable goes down.
3. **The technical novelty:** behavioral coherence (not kinematic-only), interpretable scores, criticality fusion.
4. **The product surface:** "this is the cockpit for whoever is allocating ISR capacity over critical undersea infrastructure."
5. **Roadmap:** today Baltic, tomorrow North Atlantic / Mediterranean / Pacific. Today AIS+SAR, tomorrow + DAS + acoustic + drone-relay.

The single most important thing for jury impact: *the hero demo has to be tight.* Three minutes, scripted, no live data dependencies. Recorded as a backup video in case anything fails.

---

## 12. Open questions for the team

1. **Project name.** Watchtower? Beacon? Argus? Lighthouse? Tétrapode? Phare? Open.
2. **Region focus.** Full Baltic (~150 GB AIS) or narrow to Gulf of Finland for prep simplicity (~30 GB)?
3. **Customer for the pitch.** Default NATO CUI Cell. Alternatives: Marine Nationale, EMSA, telcos, insurers.
4. **DAS partnership.** Recruit another team in advance? Stretch goal with mock only? Drop entirely?
5. **Pre-event division of labor.** One person doing all 32 hours of prep, or split three ways?
6. **Hardware element.** Pure software, or also a small ROV / sensor demo?
7. **Pre-event skills upskilling.** Should anyone read up on maritime ML / AIS analysis ahead of time? Pallotta+Vespe survey is the obvious starting point.

---

## 13. References

- ENISA, *Subsea Cables – What is at Stake* (2023)
- NATO ACT, *Critical Undersea Infrastructure* working papers
- France, *Stratégie ministérielle de maîtrise des fonds marins* (Feb 2022)
- EU Commission, *Recommendation on Submarine Cable Security* (Feb 2024)
- KSE Institute, *Russian Shadow Fleet Tracker*
- Pallotta, Vespe, et al. — maritime traffic anomaly detection literature (multiple papers, ~2013–2020)
- Recent (2023–2024) transformer-based vessel trajectory papers (search arXiv: "AIS transformer anomaly")

---

*Last updated: drafting phase, May 2026. This is a working document — edit freely.*
