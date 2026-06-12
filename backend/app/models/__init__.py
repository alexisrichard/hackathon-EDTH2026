"""Domain models — the single source of truth for the cueing-engine data layer.

All models are pydantic v2. Conventions (AGENTS.md §2): coordinates ``[lon, lat]``
EPSG:4326, times ISO-8601 UTC. Re-exported here for convenient imports::

    from app.models import Vessel, ScoredVessel, CueRecommendation
"""

from app.models.enums import (
    NavStatus,
    SensorType,
    ShipType,
    SuspicionBand,
)
from app.models.geo import BBox, CriticalityGrid, CueRecommendation, GridCell
from app.models.query import (
    TimeQuery,
    TimeWindowQuery,
    parse_bbox,
    time_params,
    time_window_params,
)
from app.models.responses import (
    CuesResponse,
    GeoResponse,
    HealthResponse,
    IncidentsResponse,
    ScenariosResponse,
    ScoresResponse,
    VesselsResponse,
)
from app.models.scenario import Incident, Scenario
from app.models.scoring import DisplayHints, ScoreBreakdown, ScoredVessel
from app.models.vessel import Vessel, VesselPosition, VesselTrack

__all__ = [
    # enums
    "ShipType",
    "NavStatus",
    "SensorType",
    "SuspicionBand",
    # vessel
    "Vessel",
    "VesselPosition",
    "VesselTrack",
    # scoring
    "ScoreBreakdown",
    "ScoredVessel",
    "DisplayHints",
    # geo
    "BBox",
    "GridCell",
    "CueRecommendation",
    "CriticalityGrid",
    # scenario
    "Incident",
    "Scenario",
    # query
    "TimeQuery",
    "TimeWindowQuery",
    "parse_bbox",
    "time_params",
    "time_window_params",
    # responses
    "VesselsResponse",
    "ScoresResponse",
    "CuesResponse",
    "ScenariosResponse",
    "IncidentsResponse",
    "GeoResponse",
    "HealthResponse",
]
