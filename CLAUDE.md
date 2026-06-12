# CLAUDE.md — hackathon-EDTH2026 (Baltic Maritime Cueing Engine)

Project-level instructions. These override defaults. The repo is shared by a 3-person team during a live hackathon — optimize for speed *and* not breaking each other's work.

---

## 1. What this project is

**A maritime cueing engine for Baltic undersea-infrastructure protection.** Built for [EDTH 2026 Paris](https://luma.com/edth-2026-paris), **June 12–14, 2026** (the hackathon is happening now).

The system ingests AIS, satellite imagery (SAR + optical), and strategic-infrastructure layers, then outputs **prioritised ISR tasking recommendations** — *"point the next satellite pass at this 50 km box at 14:00, here's why."* The output is not "this vessel is suspicious"; it's a ranked **task-next queue** of (area, time, recommended sensor). This is the *tip-and-cue* problem; the cueing layer is the product.

Core score (each term interpretable — see [`PLAN.md`](PLAN.md) §5):
```
suspicion(vessel,t) = kinematic_anomaly × (1 − class_coherence) × local_criticality × dark_modifier
```

**Read [`PLAN.md`](PLAN.md) for the full system design, scope tiers, demo flow, and threat model** (Nord Stream, Balticconnector, C-Lion1, Estlink 2 / Eagle S, Latvia–Sweden).

### Current state (as of clone)
This repo is **only the data-prep layer** — every dataset is downloaded, scripted, or honestly documented as a gap. The model, scoring engine, dashboard, and demo are **hackathon-weekend work, deliberately not pre-built.** When you build app code, it's net-new.

- **Minimum (must ship):** map + time scrubber, vessel tracks from Parquet for one month, criticality overlay (cables + naval bases), one naive anomaly detector, one incident replay (Eagle S / Christmas Eve 2024).
- **Target:** class-conditional behavioral coherence engine, multi-incident replay, interpretable alert breakdown, top-N areas-to-task panel.
- **Stretch:** Sentinel-1 dark-vessel cross-check, live AISStream mode, spoofing detection, DAS mock integration.

Suggested stack (finalize day-of): DuckDB (S3 reads) / PostGIS · FastAPI · React + deck.gl / MapLibre · scikit-learn / lightgbm baseline, PyTorch if needed. **Mock-data philosophy:** every external source has a mock fallback so the demo never depends on venue WiFi.

---

## 2. Data & S3 — the source of truth

**Bucket: `s3://edth2026-baltic/` · region `eu-west-3` (Paris). Do not create resources in other regions.** ~536 GB / 65k objects.

| Prefix | Size | What |
|---|---|---|
| `ais/parquet/source=danish/year=YYYY/month=MM/day=DD/` | ~510 GB | Danish AIS, Baltic-filtered, 2022-01-01 → 2026-05-20 (~1,601 days) |
| `kaggle/` | ~26 GB | 10 ML training datasets (SAR, optical, drone video, AIS samples) |
| `geo/` | ~210 MB | 36+ criticality GeoJSON layers (large ones; small ones are in git) |
| `reference/` | ~27 MB | sanctions, incidents, KSE shadow fleet, marine weather |
| `sar/`, `optical/`, `cameras/` | small | Sentinel-1/-2 incident crops, coastal-camera clips |

- **Small layers are committed in git** under `data/geo/*.geojson` and `data/reference/*.csv` — work with those directly, no download needed.
- **Large files are S3-only** (gitignored). Pull with `python scripts/common/sync_from_s3.py {geo|reference|kaggle|all}` or `... ais YYYY-MM-DD` for one day.
- **Prefer reading Parquet/GeoJSON straight from S3 with DuckDB `httpfs`** (no local download) — see commands below.
- Data dictionary, source-by-source: [`DATA_GUIDE.md`](DATA_GUIDE.md). Provenance + license matrix: [`data/SOURCES.md`](data/SOURCES.md). Setup: [`ONBOARDING.md`](ONBOARDING.md).
- **Honest gaps** (don't rediscover them): KSE per-vessel shadow-fleet list is aggregate-only (emailed, awaiting reply); Finnish bulk historical AIS is shallow (Danish partially covers Gulf of Finland); Orange Marine cable routes pending a contact.
- **License guardrails:** OpenSanctions (EU FSF) and Capella Open Data SAR are **non-commercial** — fine for the hackathon, must be replaced for a commercial product. Include the attribution string from `SOURCES.md` in any public demo/deck.

### Conventions
- **Baltic bbox:** lat 52°N–66°N, lon 9°E–30°E. Use `scripts.common.bbox.BALTIC_BBOX`, don't hardcode.
- **Coordinates:** EPSG:4326 (WGS84) for storage; project to local UTM as needed.
- **Parquet partitioning:** `year=YYYY/month=MM/day=DD/`.
- **Never commit:** `.env*`, raw AIS dumps, anything under `data/ais|sar|optical/`, the venv. **Always commit:** code you wrote, GeoJSON under `data/geo/`, CSVs under `data/reference/`.

### Credentials
- Gated API keys live in `.env.local` at repo root (gitignored): `AISSTREAM_API_KEY`, `EQUASIS_USERNAME`/`PASSWORD`, `COPERNICUS_CLIENT_ID`/`SECRET`, `GFW_API_TOKEN`.
- AWS S3 is via `aws configure` → `~/.aws/credentials`, region `eu-west-3`. Verify with `aws sts get-caller-identity` and `aws s3 ls s3://edth2026-baltic/`.
- All keys are to be **rotated after the hackathon**.

---

## 3. Commands

```bash
# Environment (Python 3.12)
source .venv/bin/activate                 # venv at repo root
python -c "import geopandas, duckdb, pyarrow, boto3, pyais; print('ok')"   # smoke test

# Verify S3
aws sts get-caller-identity
aws s3 ls s3://edth2026-baltic/           # expect: ais cameras geo kaggle optical reference sar samples

# Pull data
python scripts/common/sync_from_s3.py geo            # all geo layers
python scripts/common/sync_from_s3.py ais 2024-12-25 # one day of Danish AIS

# Read straight from S3 with DuckDB (no download) — the preferred query path
python -c "import duckdb; c=duckdb.connect(); c.execute(\"INSTALL httpfs; LOAD httpfs; SET s3_region='eu-west-3'\"); print(c.execute(\"SELECT COUNT(*) FROM read_parquet('s3://edth2026-baltic/ais/parquet/source=danish/year=2024/month=12/day=25/*.parquet')\").fetchall())"

jupyter lab                               # notebooks in data/samples/notebooks/
```

Repo layout: `scripts/{common,geo,ingest,reference}/` (fetchers + helpers), `data/{geo,reference}/` (committed small data), `outreach/` (team comms), `scripts/overnight.ps1` (heavy bulk downloads, Windows).

---

## 4. How to work

### Branch isolation (shared repo — this matters)
- **Never commit or push to `main`.** Three teammates plus agent sessions share this repo; committing on `main` entangles work and reverts trees out from under each other.
- At the first sign you'll edit/commit, switch to a session branch: `git switch -c claude/<topic>`. For parallel work prefer a worktree. Open a PR rather than pushing to `main`.

### Plan first, for anything non-trivial
- Enter plan mode for any task that's 3+ steps or has architectural decisions. Write the plan down, check in before implementing.
- If something goes sideways, **stop and re-plan** — don't keep pushing a failing approach.
- Use subagents liberally for research/exploration/parallel analysis to keep the main context clean. One focused task per subagent.

### Verification before "done"
- Never mark a task complete without proving it works: run it, check output, demonstrate correctness. For data work, that means actually querying the data and showing counts/rows — not assuming the file is shaped how the docs say.
- Ask: "would a staff engineer approve this?"

### Adversarial code review (post-implementation)
- After any non-trivial change — yours or a subagent's — review it adversarially before declaring done. Prefer a fresh subagent as reviewer (you're the worst reviewer of your own code).
- Check: **correctness** (logic, edge cases, error paths), **liar-tests** (tests that pass without exercising the change), **consistency** (matches surrounding patterns), **safety** (no data loss / broken state), **security** (input handling, secrets, injection).
- Output a structured verdict with per-issue `file:line` and a concrete fix.

### Elegance, balanced
- For non-trivial changes, pause and ask "is there a more elegant way?" If a fix feels hacky, redo it properly. Skip this for simple, obvious fixes — don't over-engineer. It's a hackathon: bias toward shipping the demo, but don't lay traps for Sunday-you.

---

## 5. Core principles

- **Prove, don't hypothesize.** Every root cause ends with proof — actual data, code path, or log line. Never "likely" / "probably." Either verify it or say "I don't know yet, let me check."
- **Trace full chains.** When something fails, trace tool → target → params → return → resulting output before concluding. "LLM/data variance" is not an explanation without the chain.
- **Investigate every anomaly.** Don't report "98% coverage" and move on — find the missing 2% and why. Surface metrics hide real bugs.
- **Every bug is our bug.** No "pre-existing / not from this task" dismissals. Fix it or log it as a tracked issue with a fix plan.
- **Simplicity first, minimal impact.** Make each change as simple as possible; touch only what's necessary; find root causes, no temporary hacks. Senior-engineer standards.

---

## 6. Session end
Before wrapping up, leave the next session/teammate oriented: update this file or `README.md` if the project state or conventions changed, and flag any uncommitted or unpushed work. Don't leave secrets or large data staged.
