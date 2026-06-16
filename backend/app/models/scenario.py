"""Scenario & incident models — the demo replays and the ground-truth timeline.

An :class:`Incident` is a real catalogued seabed-warfare event (seeded from
``data/reference/incidents.csv`` and ``scripts/common/bbox.py`` ``INCIDENTS``).
A :class:`Scenario` is a curated, demoable wrapper around one incident — a named
replay with a time window, an AOI bbox, the suspect MMSI, and a narrative — i.e.
the shape of ``shared/scenarios.json`` (REPO_STRUCTURE §4, frontend-plan §5).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# [min_lon, min_lat, max_lon, max_lat], EPSG:4326.
BBox = tuple[float, float, float, float]


class Incident(BaseModel):
    """A real catalogued undersea-infrastructure incident (ground truth)."""

    incident_id: str = Field(..., description="Stable id, e.g. 'INC-2024-12-25'.")
    name: str = Field(..., description="Short human-readable incident name.")
    date_utc: str = Field(..., description="Incident date, 'YYYY-MM-DD'.")
    time_utc: str | None = Field(None, description="Approx incident time 'HH:MM' UTC, if known.")
    lat: float = Field(..., ge=-90, le=90, description="Approx incident latitude.")
    lon: float = Field(..., ge=-180, le=180, description="Approx incident longitude.")
    vessel_name: str | None = Field(None, description="Suspect vessel name, if attributed.")
    vessel_flag: str | None = Field(None, description="Suspect vessel flag, if known.")
    vessel_type: str | None = Field(None, description="Suspect vessel type, if known.")
    infrastructure_name: str | None = Field(None, description="Damaged infrastructure.")
    infrastructure_type: str | None = Field(None, description="cable / pipeline / mixed / …")
    region: str | None = Field(None, description="Free-text region label.")
    attribution_status: str | None = Field(
        None, description="strong / disputed / dismissed / accidental / suspected / …"
    )
    narrative: str | None = Field(None, description="One-paragraph context from the catalogue.")
    sources: list[str] = Field(default_factory=list, description="Source URLs.")


class Scenario(BaseModel):
    """A named, demoable incident replay (mirrors ``shared/scenarios.json``)."""

    id: str = Field(..., description="Slug id, e.g. 'eagle-s-2024-12-25'.")
    name: str = Field(..., description="Display name, e.g. 'Eagle S / Estlink 2'.")
    start: datetime = Field(..., description="Replay window start, ISO-8601 UTC.")
    end: datetime = Field(..., description="Replay window end, ISO-8601 UTC.")
    bbox: BBox = Field(..., description="Area of interest [min_lon, min_lat, max_lon, max_lat].")
    suspect_mmsi: int | None = Field(None, description="MMSI of the suspect vessel, if known.")
    incident_id: str | None = Field(
        None, description="The catalogued incident this scenario replays."
    )
    narrative: str | None = Field(None, description="Demo-facing one-liner / hero-flow text.")
    held_out: bool = Field(
        False,
        description=(
            "True if this incident is held out of model training (frontend-plan §5 "
            "'aha': held-out incidents should still light up — generalization, not "
            "memorization)."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "eagle-s-2024-12-25",
                "name": "Eagle S / Estlink 2",
                "start": "2024-12-25T00:00:00Z",
                "end": "2024-12-26T00:00:00Z",
                "bbox": [25.5, 59.6, 27.0, 60.4],
                "suspect_mmsi": 372985000,
                "incident_id": "INC-2024-12-25",
                "narrative": "Eagle S slows over Estlink 2 on Christmas Eve; cable cut 14 min later.",
                "held_out": True,
            }
        }
    }
