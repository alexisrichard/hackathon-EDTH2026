# AGENTS.md — hackathon-EDTH2026 (Baltic Maritime Cueing Engine)

Project working guide. These are the rules for this repo — for **humans and for any AI coding assistant**. Treat them as overriding your defaults. The repo is shared by a 3-person team during a live hackathon — optimize for speed *and* not breaking each other's work.

> **Single source of truth for every tool.** The team uses different assistants (Claude Code, Gemini CLI, Codex / ChatGPT, Cursor, …). This file is tool-neutral and authoritative. [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) are thin pointers that redirect those tools here, so whatever you run, you load the same rules. If you arrived via a pointer file: **read this whole file before acting.**

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

Repo layout: data-prep in `scripts/{common,geo,ingest,reference}/` + `data/{geo,reference}/`; the app in `backend/` (FastAPI), `scoring/` (ML engine), `frontend/` (dashboard); `shared/` for cross-lane contracts. **Full structure, ownership lanes, and a "where do I put X" guide: [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md).**

---

## 4. How to work

### Collaboration — 3 people, one repo
Two rules keep us from clobbering each other: **own your directory** and **never commit to `main`**. Full map + ownership lanes + "where do I put X" in **[`REPO_STRUCTURE.md`](REPO_STRUCTURE.md)** — read it before writing code.

- **One lane per person.** Each person owns a top-level directory — `backend/`, `scoring/`, `frontend/` (data-prep `scripts/`+`data/` go with backend; `shared/`+`outreach/` with the lead). Work stays in your lane. Editing someone else's directory → PR + a heads-up to the owner. Directory ownership is what eliminates merge conflicts.
- **A branch per person, never `main`.** `main` is integration-only and must stay demoable. Work in your own namespace — `<name>/<topic>` (e.g. `alexis/criticality`, `<teammate>/api`, `<teammate>/dashboard`). AI-assistant sessions get an obvious prefix so they're easy to spot — `ai/<topic>` or the tool name (`claude/…`, `gemini/…`, `codex/…`). Commit there, open a PR to `main`. (Some local setups also enforce the no-`main` rule with a git hook; either way, just don't.)
- **Merge small, merge often.** Don't sit on a giant personal branch — that's how you hit merge hell Sunday morning. PR to `main` at every working checkpoint and pull `main` back into your branch frequently. Keep `main` green and runnable at all times: it *is* the demo.
- **Mock the other side.** Every boundary has a mock ([`PLAN.md`](PLAN.md) §10.3). Code against the agreed contract — `shared/api_contract.md` for the API, the `scoring.score.suspicion(...)` signature for the engine — with a stub, and swap in the real thing when it lands. Nobody should ever be blocked waiting on a teammate.
- **Never commit:** `.env*`, secrets, raw AIS, anything under `data/ais|sar|optical/`, the venv.

### Plan first, for anything non-trivial
- Enter plan mode (or write the plan down and check in) for any task that's 3+ steps or has architectural decisions, before implementing.
- If something goes sideways, **stop and re-plan** — don't keep pushing a failing approach.
- Use sub-tasks/subagents (if your tool has them) for research/exploration to keep the main context clean. One focused task at a time.

### Verification before "done"
- Never mark a task complete without proving it works: run it, check output, demonstrate correctness. For data work, that means actually querying the data and showing counts/rows — not assuming the file is shaped how the docs say.
- Ask: "would a staff engineer approve this?"

### Adversarial code review (post-implementation)
- After any non-trivial change — yours or a teammate's — review it adversarially before declaring done. Ideally have a fresh pair of eyes (or a fresh assistant session) review, not the author.
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
