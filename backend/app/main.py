"""FastAPI entrypoint for the maritime cueing-engine API.

Run from ``backend/`` with the root ``.venv`` active::

    DATA_SOURCE=mock uvicorn app.main:app --reload

Mock is the default, so plain ``uvicorn app.main:app --reload`` works with zero
AWS/network setup. Endpoints:

* ``GET /health``            — liveness + active data source
* ``GET /encoding``          — the shared shape/color display encoding (JSON)
* ``GET /vessels``           — vessel tracks (bbox + window)
* ``GET /scores``            — per-vessel suspicion at t
* ``GET /cues``              — top-N task-next recommendations at t
* ``GET /geo/criticality``   — criticality + cueing grid at t
* ``GET /scenarios``         — named demo replays
* ``GET /scenarios/{id}``    — one scenario
* ``GET /incidents``         — ground-truth incident catalogue

Interactive docs at ``/docs``.
"""

from __future__ import annotations

import app.core.paths  # noqa: F401  (puts repo root on sys.path before scripts.*)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import VERSION, get_settings
from app.core.display import _encoding
from app.data import get_data_source
from app.models.responses import HealthResponse
from app.routers import cues, frame, geo, scenarios, scores, vessels

settings = get_settings()

app = FastAPI(
    title="Baltic Maritime Cueing Engine API",
    description=(
        "Typed data layer for the EDTH 2026 maritime cueing engine. Serves vessel "
        "tracks, interpretable suspicion scores, ranked ISR task-next cues, the "
        "criticality grid, and the incident/scenario catalogue. Default data source "
        "is a realistic mock (the Eagle S / Estlink 2 incident) so the frontend "
        "works with zero backend setup. Coords are [lon, lat] EPSG:4326; times "
        "ISO-8601 UTC."
    ),
    version=VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(vessels.router)
app.include_router(scores.router)
app.include_router(cues.router)
app.include_router(frame.router)
app.include_router(geo.router)
app.include_router(scenarios.router)


@app.get("/health", response_model=HealthResponse, tags=["meta"], summary="Liveness")
def health() -> HealthResponse:
    """Liveness probe; reports which data source is active."""
    return HealthResponse(status="ok", data_source=get_data_source().name, version=VERSION)


@app.get("/encoding", tags=["meta"], summary="Shared display encoding")
def encoding() -> dict:
    """The shared shape/color display encoding (``shared/encoding/display_encoding.json``).

    Exposed so a client can verify it matches the TS mirror, or recompute display
    hints itself instead of trusting the per-vessel hints.
    """
    return _encoding()


@app.get("/", tags=["meta"], summary="Service banner")
def root() -> dict:
    """Minimal banner with a pointer to the docs."""
    return {
        "service": "Baltic Maritime Cueing Engine API",
        "version": VERSION,
        "data_source": get_data_source().name,
        "docs": "/docs",
    }
