"""Top-level API response envelopes.

These are the exact JSON shapes the frontend consumes (``shared/api_contract.md``).
We keep a thin envelope per endpoint (``{ "vessels": [...] }`` etc.) so the
contract reads naturally and is easy to extend without breaking clients.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.geo import CriticalityGrid, CueRecommendation
from app.models.scenario import Incident, Scenario
from app.models.scoring import ScoredVessel
from app.models.vessel import VesselTrack


class VesselsResponse(BaseModel):
    """`GET /vessels` — tracks in a bbox + time window."""

    vessels: list[VesselTrack] = Field(default_factory=list)


class ScoresResponse(BaseModel):
    """`GET /scores` — per-vessel suspicion at instant t."""

    t: datetime | None = Field(
        None, description="Evaluation instant echoed back (ISO-8601 UTC)."
    )
    scores: list[ScoredVessel] = Field(default_factory=list)


class CuesResponse(BaseModel):
    """`GET /cues` — ranked task-next recommendations."""

    t: datetime | None = Field(
        None, description="Evaluation instant echoed back (ISO-8601 UTC)."
    )
    cues: list[CueRecommendation] = Field(default_factory=list)


class ScenariosResponse(BaseModel):
    """`GET /scenarios` — named demo replays."""

    scenarios: list[Scenario] = Field(default_factory=list)


class IncidentsResponse(BaseModel):
    """`GET /incidents` — the catalogued ground-truth timeline."""

    incidents: list[Incident] = Field(default_factory=list)


class GeoResponse(BaseModel):
    """`GET /geo/criticality` — the criticality + cueing grid at instant t."""

    grid: CriticalityGrid


class HealthResponse(BaseModel):
    """`GET /health` — liveness + which data source is active."""

    status: str = Field("ok")
    data_source: str = Field(..., description="'mock' or 'duckdb'.")
    version: str = Field(...)
