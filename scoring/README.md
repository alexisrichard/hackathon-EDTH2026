# scoring/ — the suspicion engine

**Lane:** ML & Scoring · **Owner:** _TBD_

An importable Python package the backend calls. Turns a vessel track + context into an interpretable 0–1 suspicion score with a per-term breakdown.

```
suspicion(vessel, t) = kinematic_anomaly × (1 − class_coherence) × local_criticality × dark_modifier
```
(See [`../PLAN.md`](../PLAN.md) §5.4 — each term is meant to be explainable to a defense audience.)

```
coherence/     # per-class behavioral models (fishing, tanker, container, bulk, RoPax, …)
kinematic/     # speed / course-change-rate / stop-frequency / dispersion features
criticality/   # local criticality lookup — reads data/geo/ (cables, naval bases, …)
score.py       # combines the terms → the public entrypoint
train/         # training scripts + experiment notebooks
```

**Proposed stack (confirm Friday):** scikit-learn / lightgbm for the baseline; PyTorch only if a trajectory transformer becomes worth it. Start classical, ship something.

**Contract:** expose a stable `suspicion(track, t) -> {score, terms}` so the backend can stub it early and swap in the real thing. Read AIS via `scripts/common` helpers and the S3 layout in [`../CLAUDE.md`](../CLAUDE.md) §2.

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md).
