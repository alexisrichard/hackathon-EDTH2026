# scoring/ — transparent collection-priority engine

**Lane:** ML & Scoring · **Owner:** _TBD_

An importable Python package the backend calls. It turns a vessel observation
and supplied sensor windows into an interpretable 0–1 defensive collection
priority with a per-factor breakdown.

```
priority = 0.30 × infrastructure_proximity
         + 0.25 × unusual_movement
         + 0.15 × (1 − ais_recency)
         + 0.20 × infrastructure_importance
         + 0.10 × satellite_availability
```
(See [`../PLAN.md`](../PLAN.md) §5.4.)

```
coherence/     # per-class behavioral models (fishing, tanker, container, bulk, RoPax, …)
kinematic/     # speed / course-change-rate / stop-frequency / dispersion features
criticality/   # local criticality lookup — reads data/geo/ (cables, naval bases, …)
score.py       # combines the terms → the public entrypoint
train/         # training scripts + experiment notebooks
```

**Proposed stack (confirm Friday):** scikit-learn / lightgbm for the baseline; PyTorch only if a trajectory transformer becomes worth it. Start classical, ship something.

**Contract:** use `score_observation(...)` and `rank_tasking(...)` as documented
in [`CONTRACT.md`](CONTRACT.md). Read AIS via `scripts/common` helpers and the S3
layout in [`../AGENTS.md`](../AGENTS.md) §2.

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md).

## Synthetic demo contract

The minimal backend boundary for the first demo is defined in
[`CONTRACT.md`](CONTRACT.md). It covers observation scoring, 50 km tasking-box
ranking, satellite windows, validation, and defensive-use disclaimers.

The offline-safe fictional fixture used to exercise that contract is in
[`demo_data/synthetic_scenario.json`](demo_data/synthetic_scenario.json), with
plain-language notes in [`demo_data/README.md`](demo_data/README.md).

## Run the transparent demo

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m scoring.run_demo
.\.venv\Scripts\python.exe -m unittest discover -s scoring/tests -v
```

The current rules are intentionally simple and visible: infrastructure
proximity 30%, unusual movement 25%, infrastructure importance 20%, AIS
staleness 15%, and supplied satellite availability 10%.
