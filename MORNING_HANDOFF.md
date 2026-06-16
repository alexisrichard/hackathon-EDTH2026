# Morning handoff — overnight 2026-06-13/14

Branch: **`claude/ui-v1`** (not merged to `main`). All four NIGHT_PLAN parts done,
each gated by an adversarial reviewer agent. Full detail + reviewer verdicts in
[NIGHT_PLAN.md](NIGHT_PLAN.md).

## TL;DR — what's demo-ready
The webapp now renders the **real scoring/cueing engine** end-to-end (the interim
overfit `scenario.ts` is deleted). Two honest, no-overfit demo scenarios:

- **C-Lion1 / Yi Peng 3** (opens here, 2024-11-18 08:41Z): Yi Peng 3 is the **#1
  task-next cue** and the pinned **PRIMARY CUE** in the alert feed (risk 0.83 = SAR
  dark-approach +0.50 · behaviour +0.33). It leads via the *combination*, not a
  memorised prior — on behaviour alone it's mid-pack (rank 1412/2096).
- **Nord Stream** (scrub to 2022-09-26): **153 SAR dark contacts** clustered on the
  pipeline; #1 cue "84 dark SAR contacts, no AIS — a suspect that went dark". No
  ship named (no AIS suspect) — the dark-density archetype.

`tsc` clean, prod build OK, verified in-app (screenshots taken during the session).

## Commits on `claude/ui-v1`
- `ace977b` Part 1 — build-time tile stitch (1601 self-aligned day-tiles → `ais_v2/`, gitignored); killed the midnight-discontinuity saga.
- `6b8a673` Part 2 — ship scoring: SAR `sar_mismatch` sub-signal + class-relative calibration.
- `ba3b36f` Part 3 — zone cueing engine (`scoring/zone_score.py`): per-vessel argmax + noisy-OR dark density; emits `frontend/public/data/cues/`.
- `6747802` + `82b9dbb` Part 4 — wire the engine into the webapp + review fixes (no-look-ahead to the minute, honest pin guard).
- `724a61e` plan/docs.

## ⚠️ Côme — `scoring/` is your lane (PR + review owed)
The overnight plan tasked me with finalizing ship + zone scoring, which touches your
files. Please review before we merge anywhere:
- New: `scoring/zone_score.py`, `scoring/calibrate.py`, `scoring/sar_signals.py`, `scoring/tests/test_zone_score.py`, `scripts/reference/mock_vessel_signals.py`.
- Modified: `scoring/ship_trust.py` (SAR sub-signal), `scoring/validate_fleet.py`.
- **Known limitation handed to you:** the behavioural prior's upper tail saturates —
  raw `dark_events`/`kinematics` pin at 1.0 for ~12 small `other`/`pleasure` craft,
  so class-relative re-centres the mass (p50 0.78→0.33) but can't un-saturate the
  tail. Fix lives in `behavioral.py` (softer feature defs / low-sample-confidence
  guard), not the calibration. Documented in `calibrate.py`'s docstring. It does NOT
  break the demo (the cue ranks the hero #1 via SAR+live), but those small craft
  show as the #2–#5 cues / top raw-prior alerts.

## Swap-in points (mock → real, when ready)
- **SAR signals:** drop the real `vessel_signals.csv` at repo root / `scoring/` /
  `data/reference/` — `scoring/sar_signals.py` resolves it over the mock
  automatically. Then re-run `python3 -m scoring.zone_score --emit frontend/public/data/cues`.
- **Backend:** `backend/app/data/duckdb_source.py` still has `scores_at`/`cues_at`
  stubs — the webapp currently reads the precomputed `cues/*.json` (demo-robust). A
  live backend path can replace the static JSON later; the frontend types in
  `frontend/src/lib/cues.ts` are the contract.

## Residuals / not done
- No frontend test runner (hackathon-acceptable). If adding one, start with
  `activeScenario` (the load-bearing day+`at_ts` gate).
- Right rail scrolls below the fold on short screens; top cue + hero alert always
  visible. Deploy hosting still TBD (see [[ais-replay-archive]] in memory).
- The hero's AIS type is "other" in the data; the frontend force-shows cue drivers
  so it never vanishes when the Other class is toggled off.

## Run it
```
# scoring (no bare `python`; use python3, venv at .venv)
source .venv/bin/activate
python3 -m unittest discover -s scoring/tests -p 'test_*.py'      # 60 tests
python3 -m scoring.zone_score                                      # print both queues
python3 -m scoring.validate_fleet --as-of 2024-11-18 --lookback 90 # no-overfit check
# frontend
cd frontend && npm run dev   # opens on the C-Lion1 moment
```
