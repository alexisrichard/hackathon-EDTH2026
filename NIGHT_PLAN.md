# NIGHT_PLAN.md — overnight autonomous execution

Owner: Claude (autonomous, overnight 2026-06-13/14). Branch: `claude/ui-v1`.
Source of truth for the night. Check items off as completed; append a REVIEW
block per part with the reviewer agent's verdict.

## Operating principles
- **Very high effort.** No band-aids, find root causes (per AGENTS.md §5).
- **Prove, don't hypothesize.** Verify with faithful traces + in-app, not claims.
- **Reviewer gate per part.** After each part, spawn a task-tailored reviewer
  agent (adversarial). Require a structured verdict (APPROVE / MODIFY / REJECT,
  per-issue `file:line` + fix). Iterate until APPROVE or ≤2 rounds, then document
  residuals and move on.
- **Commit at every checkpoint.** Clean messages. `scoring/` is Côme's lane →
  leave a PR + heads-up note for the morning, don't merge to main.
- **Independence.** If a part is blocked (missing data), build against the schema
  mock-first, document the gap, and proceed to the next part.
- **Mock-first.** Every external input (SAR signals, backend) has a mock so the
  demo never blocks. Swap real when it lands.
- **Update this file** (checkboxes + REVIEW blocks) as the night progresses.

---

## Part 1 — Data continuity, done right (stitch once at build time)

**Goal:** kill border effects structurally. Build clean, self-aligned day-tiles
so the app renders one tile with NO runtime stitching. Root-cause fix for the
midnight discontinuity saga.

**Why this works:** the cuts are currently "unclean" — per-day processing never
puts a keyframe at midnight and detects gaps per-day, so each tile is an island
the app must rejoin. Clean tiles touch exactly at the seam → no rejoining.

- [x] 1.1 `scripts/ingest/stitch_tracks.py`:
  - read all `frontend/public/data/ais/tracks_*.json` (sorted)
  - concat per-MMSI across days → continuous tracks; global de-spike
  - **global gap detection** (>600 s no ping = gap), correct across midnights
  - **filter static/sparse non-vessels**: AtoN (MMSI 99xxxxxxx), base stations
    (MMSI < 1e8 / leading-zero), and vessels whose whole-archive bbox < ~0.5 km
    (stationary). Write `data/reference/dropped_static_reporters.csv` for
    transparency (count, mmsi, reason).
  - **insert an interpolated keyframe at each UTC midnight a vessel crosses while
    actively tracked** (not inside a gap) so adjacent tiles share the exact seam
    point.
  - re-slice into per-day tiles (same filenames), clipped to the day with the
    boundary keyframes; preserve `meta`.
  - write to a temp dir, verify counts, then swap into `frontend/public/data/ais/`
    (back up originals to `data/ais/tiles_raw_backup/` — gitignored).
- [x] 1.2 Simplify `frontend/src/lib/trackStore.ts`: remove `mergeVessels`, the
  boundary logic, `MAX_BRIDGE`/`SEAM_GAP`, in-app de-spike. `TileManager` loads
  the current day (+ prefetch next/prev, keep `lastFleet` to avoid a blank during
  load) and renders `positionsFrom(currentTile, t)`. Keep gap-freeze + fade.
- [x] 1.3 Remove debug instrumentation (App.tsx `__tiles`/`__seek`/the DEBUG badge).
- [x] 1.4 Verify: faithful python trace across ≥5 midnights (corpus-edge +
  interior) → appeared/disappeared ≈ mid-day baseline; in-app screenshot at a
  midnight; `tsc` clean; no console errors.
- [x] 1.5 REVIEWER AGENT (data architecture). Iterate.
- [x] 1.6 Commit.

REVIEW-1: **DONE (commit `ace977b`).** Build-time stitch (`scripts/ingest/stitch_tracks.py`)
→ 1601 self-aligned day-tiles in `frontend/public/data/ais_v2/` (gitignored); app
renders one tile, no runtime merge (`trackStore.ts` simplified). Reviewer REJECTED
the first cut: gaps were RECOMPUTED from DP-simplified keyframes → 90.6% phantom
gaps, freezing 1124 steaming vessels and poisoning the (old) suspicion score.
Fixed by carrying the REAL source gaps clipped to each day + interpolated seam
keyframes at every midnight crossing. Moving-while-dark 1124→79; in-app midnight
continuity verified by faithful trace + screenshot.

---

## Part 2 — Finalize the ship scoring system (+ SAR signals)

**Goal:** a per-vessel point-in-time risk that actually surfaces the hero and
keeps clean traffic low — no class false-positives, no look-ahead. Integrate the
Signal Brick `vessel_signals.csv` (see `scoring/SIGNAL_BRICK_HANDOFF.md`).

Context to honor: earlier fleet validation found the class-AGNOSTIC behavioral
prior mis-calibrated (fishing/service vessels top, hero buried). The SAR signals
(`ais_dark_approach` for Yi Peng 3) are the strong, dated signal that surfaces
the hero. Ship score = behavioral_history (class-relative) + identity + watchlist
+ **sar_mismatch** (new).

- [x] 2.1 Check whether the Signal Brick files exist in the tree
  (`scoring/detect_dark_vessels.py`, `vessel_signals.csv`, …). If absent, build a
  **mock** `data/reference/vessel_signals.mock.csv` matching the schema + the
  handoff coverage table (Nord Stream 153 dark_vessel; C-Lion1 96 ais_blackout +
  176 ais_dark_approach incl. Yi Peng 3) so scoring/demo work; swap real later.
- [x] 2.2 Add `sar_mismatch` sub-signal to `scoring/ship_trust.py`:
  point-in-time (only `signal_date_utc` ≤ t), weighted
  `ais_dark_approach 1.0 / ais_blackout 0.7 × gap_factor`, fail-closed. Tests.
- [x] 2.3 Class-relative calibration of `behavioral_history` (promote the validated
  approach from `validate_fleet.py`: deviation within ship class; exclude in-port/
  anchored idle time from "loiter"). Tests. Keep it interpretable.
- [x] 2.4 A loader that assembles a vessel's full `score_vessel_risk` input from
  real data (behavioral from corpus, identity curated, watchlist curated, SAR
  from `vessel_signals`).
- [x] 2.5 Re-run `validate_fleet.py` as-of 2024-11-18: confirm Yi Peng 3 now ranks
  in the tail (via the SAR `ais_dark_approach` + behavior) and fishing/service no
  longer dominate. "Good enough" = hero in top ~2%, clean classes low, no
  look-ahead. Iterate constants (principled, not hero-tuned).
- [x] 2.6 REVIEWER AGENT (scoring correctness + no-overfit + no-look-ahead). Iterate.
- [x] 2.7 Commit (note: Côme's lane → PR + heads-up in the morning).

REVIEW-2: **DONE (commit `6b8a673`).** `ship_trust.py` gains a point-in-time
`sar_mismatch` sub-signal (dark_approach 1.0 / blackout 0.7×gap, fail-closed,
adds on top of base); `calibrate.py` class-relative behavioural prior; mock
`vessel_signals` + `sar_signals.py` loader; `validate_fleet.py` re-run. Reviewer
MODIFY: (1) SAR used DAY-granularity → leaked same-day-future signals — fixed with
instant granularity (`_parse_signal_instant`, `when <= as_of`); (2) liar-test —
added a same-day-but-after-t exclusion test; (3) the mock sprayed dark_approach on
'other'-class rescue/pilot boats (hero buried rank 366) — restricted to the
transit-class pool. Result: hero top ~3% on prior+SAR, top 67% on behaviour ALONE
(honest — the prior is unremarkable; SAR + live surface it). 42 tests green.
(Part 3 later refined the mock to be faithful to the dark-approach definition and
added the zone engine + 18 more tests.)

---

## Part 3 — Zone scoring (the cueing engine — the product)

**Goal:** the ranked task-next queue of (area, time, sensor). Combine, per 50 km
cell: infra-proximity × importance + aggregated vessel_risk + live unusual_movement
+ dark_vessel density (SAR). Produces the hero cue (C-Lion1 box driven by Yi Peng 3)
and a Nord Stream box driven by dark_vessel density.

- [x] 3.1 Real per-cell aggregation in `scoring/zone_score.py`: per-vessel argmax
  (one ship's infra/risk/live/sar, sub-weights sum to 1) + dark-density, combined
  by noisy-OR. Transparent terms that belong to ONE named driver (no Frankenstein).
- [x] 3.2 Demo-robust precomputed per-scenario JSON: `zone_score --emit
  frontend/public/data/cues/` writes `{index,c-lion1,nord-stream}.json` (cues +
  dark contacts + per-vessel breakdowns). (Backend duckdb stubs left for Part 4.)
- [x] 3.3 Validate: C-Lion1 top cue = Yi Peng 3 box (#1, 0.885); Nord Stream cue =
  dark-density box (no ship named). No-overfit confirmed: hero is top 67% on
  behaviour ALONE (rank 1412/2096) — surfaces only via SAR + live in the cue.
- [x] 3.4 REVIEWER AGENT — verdict MODIFY; all blockers fixed (see REVIEW-3).
- [x] 3.5 Commit — `ba3b36f`.

REVIEW-3: **MODIFY → resolved.** Adversarial subagent confirmed all 3 hard
invariants hold under tracing: no-look-ahead (all 3 paths fail-closed), no-overfit
(hero never special-cased in the math; grep-verified), honest attribution (terms
provably belong to one ship). Blockers fixed: (1) added `test_zone_score.py` (18
tests — the engine had ZERO coverage; old 42 tested other modules); (2) fail-closed
the zone dark-contact filter (was admitting blank `signal_date` via `(None or 0)`).
Nits fixed: stable per-row cell grid (deterministic bbox); dark-dominated cells
zero vessel terms/drivers to match "no AIS" prose; honest mock + calibrate
docstrings. Residual (→ Côme): raw `dark_events`/`kinematics` features saturate the
small-craft tail at 1.0; class-relative re-centres the mass (p50 .78→.33) but can't
un-saturate the tail — needs softer feature defs / a low-sample-confidence guard in
`behavioral.py`. Net: prior is a supporting signal; the cue discriminates via
infra+live+SAR. 60/60 scoring tests pass.

---

## Part 4 — Weave it all into the webapp

**Goal:** the dashboard shows the REAL scores/cues end-to-end. Replace the interim
`scenario.scoreFix` with the real ship-risk; render the real task-next cues; add a
SAR / dark-vessel overlay; show ship-risk breakdown in the alert feed (interpretable).

- [x] 4.1 Real `vessel_risk` wired via precomputed per-scenario JSON
  (`frontend/public/data/cues/`). Interim `scenario.ts` DELETED. New `lib/cues.ts`
  loader; fleet carries real risk + breakdown per MMSI; unscored outside theatre.
- [x] 4.2 Real ranked task-next boxes (`MapView` cue-boxes/tags) + the queue in
  `CuePanel` with per-box "why" + transparent term bars + Task button.
- [x] 4.3 SAR dark-vessel overlay (`sar-dark-contacts`) + a "Cueing engine" toggle
  group in `LayerPanel` (task-next cues + SAR dark contacts).
- [x] 4.4 Alert feed shows interpretable contributions (SAR / behaviour / identity)
  + the scenario "cued as-of" line; hero pinned PRIMARY CUE (guarded).
- [x] 4.5 Verified in-app (screenshots): C-Lion1 → Yi Peng 3 pinned (0.83 = SAR
  +0.50 · behaviour +0.33), #1 box on the corridor; Nord Stream → 153 SAR dark
  contacts on the pipeline, #1 dark-density cue, no AIS suspect.
- [x] 4.6 REVIEWER AGENT — APPROVE WITH NITS; honesty nits fixed (see REVIEW-4).
- [x] 4.7 Commit — `6747802` + `82b9dbb` (review fixes).

REVIEW-4: **APPROVE WITH NITS → resolved.** Reviewer traced both UI invariants and
confirmed they hold: no-overfit (hero risk 0.833 read verbatim from payload; MMSI
only used as demo config for the pin/always-show, never in a risk value) and honest
attribution (the #1 C-Lion1 cue driver IS the hero; Nord Stream pin suppressed).
Graceful degradation on missing cues, clean scenario-switch memo deps, faithful
term-by-term payload rendering — all verified. Fixes applied: (1) `activeScenario`
now gates on `at_ts` so a cue can't appear before its compute instant (verified:
03:00 same-day → inactive); (2) PRIMARY CUE pin only renders when the hero is truly
the #1 cue driver (`primaryCueMmsi`); (3) cue-tag `characterSet:"auto"` + alert feed
trimmed to 4. Residual (non-blocking): no frontend test runner — if one test is
added, make it `activeScenario`; rail scrolls below the fold on short screens (top
cue + hero alert always visible). tsc clean, prod build OK.

---

## Reviewer agent protocol
For each part, spawn `Agent` (general-purpose) with a tailored prompt:
- context: the part's goal + relevant files + AGENTS.md principles,
- ask for adversarial review: correctness, edge cases, liar-tests, consistency,
  safety, and the part's specific success criteria,
- require: structured verdict APPROVE/MODIFY/REJECT, per-issue `file:line` + concrete
  fix, and a one-line "would a staff engineer ship this?".
Act on blockers; re-review once; record residuals in the REVIEW block.

## Morning handoff (last step)
- Update `MEMORY.md` + this file's checkboxes/REVIEW blocks.
- Write a concise summary: what's done, each reviewer verdict, what's left, branch/
  PR status (esp. the `scoring/` PR + Côme heads-up), and any flagged residuals.
- Flag anything uncommitted/risky.

## Prioritization if time runs short
Part 1 (must — it's the open bug) → Part 2 → Part 3 → Part 4. Parts 3–4 may land
partial; if so, leave them in a clean, documented, compiling state with clear TODOs.
