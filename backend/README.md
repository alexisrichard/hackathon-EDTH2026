# backend/ — API service

**Lane:** Data & Backend · **Owner:** _Alexis / TBD_

Serves the data the dashboard needs: vessel tracks, suspicion scores, cueing recommendations, and scenario replays. Reads AIS parquet + geo layers from S3 via DuckDB; calls `scoring.score` for the suspicion numbers.

**Proposed stack (confirm Friday):** FastAPI + uvicorn, DuckDB (`httpfs` over S3), pydantic for the schemas.

```
app/
├── main.py        # FastAPI app
├── routers/       # /vessels  /scores  /cues  /incidents  /scenarios
└── data/          # DuckDB-over-S3 query layer
```

**Contract:** the API shape is the source of truth in [`../shared/api_contract.md`](../shared/api_contract.md) — agree it with frontend before building. Call `scoring.score.suspicion(...)` (stub it until the ML lane delivers).

**Run:** _TBD_ — likely `uvicorn app.main:app --reload` from this dir, with the root `.venv` active.

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md) and [`../PLAN.md`](../PLAN.md) §5–6.
