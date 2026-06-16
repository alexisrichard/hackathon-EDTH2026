"""The :class:`DataSource` interface — the seam every endpoint depends on.

Two implementations satisfy it:

* :class:`~app.data.mock.MockDataSource` — synthetic but realistic data, zero
  external dependencies (the default).
* :class:`~app.data.duckdb_source.DuckDBDataSource` — reads AIS parquet via DuckDB
  from a configurable root (``data/ais/parquet/`` locally by default; the
  ``edth2026-baltic`` S3 bucket is retired).

Routers receive a ``DataSource`` via dependency injection and never know which
implementation they got. Switch with the ``DATA_SOURCE`` env var.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.models.geo import BBox, CriticalityGrid, CueRecommendation
from app.models.scenario import Incident, Scenario
from app.models.scoring import ScoredVessel
from app.models.vessel import VesselTrack


class DataSource(ABC):
    """Abstract data provider for the cueing-engine API.

    All methods are read-only. ``bbox`` is ``[min_lon, min_lat, max_lon, max_lat]``
    (EPSG:4326); ``None`` means "no spatial filter". Times are timezone-aware UTC
    ``datetime``; ``None`` means "use a sensible default (the demo instant)".
    """

    name: str = "abstract"

    @abstractmethod
    def vessel_tracks(
        self,
        bbox: BBox | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[VesselTrack]:
        """Return vessel tracks within ``bbox`` and the ``[start, end]`` window."""

    @abstractmethod
    def scores_at(
        self,
        t: datetime | None = None,
        bbox: BBox | None = None,
    ) -> list[ScoredVessel]:
        """Return per-vessel suspicion scores (with breakdown) at instant ``t``."""

    @abstractmethod
    def cues_at(
        self,
        t: datetime | None = None,
        top: int = 5,
        bbox: BBox | None = None,
    ) -> list[CueRecommendation]:
        """Return the top-``top`` ranked task-next recommendations at ``t``."""

    @abstractmethod
    def criticality_grid(
        self,
        t: datetime | None = None,
        bbox: BBox | None = None,
    ) -> CriticalityGrid:
        """Return the criticality + cueing grid at instant ``t``."""

    @abstractmethod
    def scenarios(self) -> list[Scenario]:
        """Return the named demo scenarios."""

    @abstractmethod
    def incidents(self) -> list[Incident]:
        """Return the catalogued ground-truth incident timeline."""

    def close(self) -> None:
        """Release any held resources (DB connections). No-op by default."""
        return None
