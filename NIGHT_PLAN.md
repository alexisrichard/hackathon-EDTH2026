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

- [ ] 1.1 `scripts/ingest/stitch_tracks.py`:
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
- [ ] 1.2 Simplify `frontend/src/lib/trackStore.ts`: remove `mergeVessels`, the
  boundary logic, `MAX_BRIDGE`/`SEAM_GAP`, in-app de-spike. `TileManager` loads
  the current day (+ prefetch next/prev, keep `lastFleet` to avoid a blank during
  load) and renders `positionsFrom(currentTile, t)`. Keep gap-freeze + fade.
- [ ] 1.3 Remove debug instrumentation (App.tsx `__tiles`/`__seek`/the DEBUG badge).
- [ ] 1.4 Verify: faithful python trace across ≥5 midnights (corpus-edge +
  interior) → appeared/disappeared ≈ mid-day baseline; in-app screenshot at a
  midnight; `tsc` clean; no console errors.
- [ ] 1.5 REVIEWER AGENT (data architecture). Iterate.
- [ ] 1.6 Commit.

REVIEW-1: _(append verdict)_

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

- [ ] 2.1 Check whether the Signal Brick files exist in the tree
  (`scoring/detect_dark_vessels.py`, `vessel_signals.csv`, …). If absent, build a
  **mock** `data/reference/vessel_signals.mock.csv` matching the schema + the
  handoff coverage table (Nord Stream 153 dark_vessel; C-Lion1 96 ais_blackout +
  176 ais_dark_approach incl. Yi Peng 3) so scoring/demo work; swap real later.
- [ ] 2.2 Add `sar_mismatch` sub-signal to `scoring/ship_trust.py`:
  point-in-time (only `signal_date_utc` ≤ t), weighted
  `ais_dark_approach 1.0 / ais_blackout 0.7 × gap_factor`, fail-closed. Tests.
- [ ] 2.3 Class-relative calibration of `behavioral_history` (promote the validated
  approach from `validate_fleet.py`: deviation within ship class; exclude in-port/
  anchored idle time from "loiter"). Tests. Keep it interpretable.
- [ ] 2.4 A loader that assembles a vessel's full `score_vessel_risk` input from
  real data (behavioral from corpus, identity curated, watchlist curated, SAR
  from `vessel_signals`).
- [ ] 2.5 Re-run `validate_fleet.py` as-of 2024-11-18: confirm Yi Peng 3 now ranks
  in the tail (via the SAR `ais_dark_approach` + behavior) and fishing/service no
  longer dominate. "Good enough" = hero in top ~2%, clean classes low, no
  look-ahead. Iterate constants (principled, not hero-tuned).
- [ ] 2.6 REVIEWER AGENT (scoring correctness + no-overfit + no-look-ahead). Iterate.
- [ ] 2.7 Commit (note: Côme's lane → PR + heads-up in the morning).

REVIEW-2: _(append verdict)_

---

## Part 3 — Zone scoring (the cueing engine — the product)

**Goal:** the ranked task-next queue of (area, time, sensor). Combine, per 50 km
cell: infra-proximity × importance + aggregated vessel_risk + live unusual_movement
+ dark_vessel density (SAR). Produces the hero cue (C-Lion1 box driven by Yi Peng 3)
and a Nord Stream box driven by dark_vessel density.

- [ ] 3.1 Real per-cell aggregation in `scoring/` (extend `rank_tasking`): pull
  vessel_risk per vessel at t, criticality surface from `data/geo`, dark_vessel
  density from `vessel_signals` (0.1° bins). Transparent weighted terms.
- [ ] 3.2 Backend loader: replace the `cues_at`/`scores_at` TODO stubs in
  `backend/app/data/duckdb_source.py` with the real computation (or a precomputed
  per-scenario JSON for demo robustness, mock-first).
- [ ] 3.3 Validate: the top cue at the C-Lion1 replay is the Yi Peng 3 box; a
  Nord Stream cue surfaces from dark-vessel density. Distribution sane.
- [ ] 3.4 REVIEWER AGENT (cueing logic + demo-readiness). Iterate.
- [ ] 3.5 Commit.

REVIEW-3: _(append verdict)_

---

## Part 4 — Weave it all into the webapp

**Goal:** the dashboard shows the REAL scores/cues end-to-end. Replace the interim
`scenario.scoreFix` with the real ship-risk; render the real task-next cues; add a
SAR / dark-vessel overlay; show ship-risk breakdown in the alert feed (interpretable).

- [ ] 4.1 Wire the real `vessel_risk` into the frontend fleet (via backend
  `/scores` or a precomputed per-scenario JSON). Replace `scenario.ts` interim.
- [ ] 4.2 Render the real `/cues` (task-next boxes) + per-box "why".
- [ ] 4.3 SAR dark-vessel overlay (incident detections) as a toggle.
- [ ] 4.4 Alert feed shows the interpretable ship-risk breakdown (behavioral /
  identity / watchlist / sar) + the no-look-ahead "as-of" note for the hero.
- [ ] 4.5 Verify in-app: the hero replay shows Yi Peng 3 elevated, the cue box on
  the C-Lion1 corridor, the cable-cut narrative. Screenshot proof.
- [ ] 4.6 REVIEWER AGENT (integration + demo flow). Iterate.
- [ ] 4.7 Commit.

REVIEW-4: _(append verdict)_

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
