"""DuckDBDataSource — reads AIS parquet from a configurable root.

This is the *real* data path (``DATA_SOURCE=duckdb``). The parquet root is
``Settings.ais_parquet_root`` — **LOCAL by default** (``data/ais/parquet/``,
produced by ``scripts/ingest/danish_ais.py``); the S3 bucket
(``edth2026-baltic``) is **retired**. For a local root, DuckDB reads the parquet
globs straight from the filesystem with no ``httpfs`` / AWS setup. Only when the
root is an ``s3://...`` path do we ``LOAD httpfs`` and create an S3 secret (via
``scripts/common/duck.py``).

Status: **skeleton with one working example query** (``count_positions`` /
``positions_for_day``). The scoring-dependent methods (``scores_at``,
``cues_at``, ``criticality_grid``) are TODO stubs that currently delegate to the
mock so the API still returns sensible JSON in either mode — they should be
filled in as the scoring engine (``scoring.score``) and the criticality grid
(Gabriel's lane) land. ``vessel_tracks`` has a real DuckDB implementation.

Real AIS columns (Danish parquet)::

    Timestamp, MMSI, Latitude, Longitude, SOG, COG, Heading,
    "Navigational status", Name, "Ship type", IMO, Callsign, Length, Width,
    Draught, Destination, ...
"""

from __future__ import annotations

from datetime import datetime, timezone

import app.core.paths  # noqa: F401  (repo root on sys.path)
from app.core.config import get_settings
from app.data.base import DataSource
from app.data.mock import MockDataSource
from app.models.enums import NavStatus, ShipType
from app.models.geo import BBox, CriticalityGrid, CueRecommendation
from app.models.scenario import Incident, Scenario
from app.models.scoring import ScoredVessel
from app.models.vessel import Vessel, VesselPosition, VesselTrack


class DuckDBDataSource(DataSource):
    """DuckDB-backed data source over local (default) or s3:// AIS parquet.

    Real AIS; scoring stubs delegate to mock.
    """

    name = "duckdb"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._con = None
        # Reuse the mock for the not-yet-implemented, scoring-dependent endpoints
        # so the API stays fully functional while the real queries are built out.
        self._mock_fallback = MockDataSource()

    # -- connection ---------------------------------------------------------------

    def _conn(self):
        """Lazily open a DuckDB connection sized to the configured parquet root.

        Local root (default): a plain DuckDB connection that reads parquet from
        the filesystem — no ``httpfs``, no AWS credentials required. ``s3://``
        root: reuse the shared helper (``scripts/common/duck.py``), which loads
        ``httpfs`` and creates an S3 secret from ``~/.aws/credentials``.
        """
        if self._con is None:
            if self._settings.is_s3_root:
                from scripts.common.duck import connect

                self._con = connect()
            else:
                import duckdb

                con = duckdb.connect()
                # Progress bar spams stdout; disable it (mirrors duck.connect()).
                con.execute("SET enable_progress_bar = false;")
                self._con = con
        return self._con

    # -- working example query ----------------------------------------------------

    def count_positions(self, year: int, month: int, day: int) -> int:
        """Example working query: count AIS position rows for one day.

        Reads from the configured parquet root (local by default; S3 retired).
        Mirrors the smoke-test in AGENTS.md §3. Proves the parquet read path works.
        """
        glob = self._settings.ais_day_glob(year, month, day)
        sql = "SELECT COUNT(*) AS n FROM read_parquet(?)"
        row = self._conn().execute(sql, [glob]).fetchone()
        return int(row[0]) if row else 0

    # -- DataSource API -----------------------------------------------------------

    def vessel_tracks(
        self,
        bbox: BBox | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[VesselTrack]:
        """Read vessel tracks from AIS parquet over the [start, end] window + bbox.

        Queries the day partitions spanning [start, end]. Requires ``start`` (and
        ideally ``end``) — without a time window we cannot pick partitions, so we
        fall back to the mock.
        """
        if start is None:
            return self._mock_fallback.vessel_tracks(bbox, start, end, limit)
        start = _utc(start)
        end = _utc(end) if end else start

        globs = [
            self._settings.ais_day_glob(d.year, d.month, d.day)
            for d in _days(start, end)
        ]
        if not globs:
            return []

        # bbox filter (coords are [lon, lat]).
        where = ['"Timestamp" BETWEEN ? AND ?']
        params: list = [start, end]
        if bbox is not None:
            where.append("Longitude BETWEEN ? AND ? AND Latitude BETWEEN ? AND ?")
            params += [bbox[0], bbox[2], bbox[1], bbox[3]]

        # NOTE: column names in the Danish feed contain spaces — quote them.
        sql = f"""
            WITH ranked AS (
                SELECT MMSI,
                       "Timestamp"           AS ts,
                       Longitude             AS lon,
                       Latitude              AS lat,
                       SOG                   AS sog,
                       COG                   AS cog,
                       Heading               AS heading,
                       "Navigational status" AS nav,
                       Name                  AS name,
                       "Ship type"           AS ship_type,
                       IMO                   AS imo,
                       Callsign              AS callsign,
                       Length                AS length,
                       Width                 AS width,
                       Draught               AS draught,
                       Destination           AS destination
                FROM read_parquet({_sql_list(globs)})
                WHERE {' AND '.join(where)}
            )
            SELECT * FROM ranked
            WHERE MMSI IN (
                SELECT MMSI FROM ranked GROUP BY MMSI ORDER BY COUNT(*) DESC LIMIT {int(limit)}
            )
            ORDER BY MMSI, ts
        """
        df = self._conn().execute(sql, params).df()
        return _df_to_tracks(df)

    def scores_at(
        self, t: datetime | None = None, bbox: BBox | None = None
    ) -> list[ScoredVessel]:
        # TODO(scoring): pull positions at t, call scoring.score.suspicion(track, t),
        # decorate with display hints. Until the scoring engine lands, delegate.
        return self._mock_fallback.scores_at(t, bbox)

    def cues_at(
        self, t: datetime | None = None, top: int = 5, bbox: BBox | None = None
    ) -> list[CueRecommendation]:
        # TODO(grid+scoring): aggregate per-cell scores over the criticality grid
        # and rank. Delegate for now.
        return self._mock_fallback.cues_at(t, top, bbox)

    def criticality_grid(
        self, t: datetime | None = None, bbox: BBox | None = None
    ) -> CriticalityGrid:
        # TODO(geo): build the static criticality surface from data/geo/*.geojson
        # (cables, naval bases, ...) and blend with live in-cell suspicion.
        return self._mock_fallback.criticality_grid(t, bbox)

    def scenarios(self) -> list[Scenario]:
        # Scenarios are curated demo metadata, identical regardless of backend.
        return self._mock_fallback.scenarios()

    def incidents(self) -> list[Incident]:
        # Real incidents come from the committed CSV; the mock already reads it.
        return self._mock_fallback.incidents()

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None


# -- helpers ----------------------------------------------------------------------


def _utc(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _days(start: datetime, end: datetime):
    """Yield each calendar day (UTC date) in the inclusive [start, end] range."""
    from datetime import timedelta

    d = start.date()
    last = end.date()
    while d <= last:
        yield d
        d += timedelta(days=1)


def _sql_list(globs: list[str]) -> str:
    """Render a Python list of globs as a DuckDB SQL array literal (read_parquet)."""
    escaped = ", ".join("'" + g.replace("'", "''") + "'" for g in globs)
    return f"[{escaped}]"


def _df_to_tracks(df) -> list[VesselTrack]:
    """Group a positions dataframe (sorted by MMSI, ts) into VesselTrack models."""
    tracks: list[VesselTrack] = []
    if df is None or df.empty:
        return tracks
    for mmsi, grp in df.groupby("MMSI", sort=False):
        head = grp.iloc[0]
        vessel = Vessel(
            mmsi=int(mmsi),
            name=_s(head.get("name")),
            imo=_i(head.get("imo")),
            callsign=_s(head.get("callsign")),
            ship_type=ShipType.from_ais(_s(head.get("ship_type"))),
            length=_f(head.get("length")),
            width=_f(head.get("width")),
            draught=_f(head.get("draught")),
            destination=_s(head.get("destination")),
        )
        positions = [
            VesselPosition(
                t=_utc(row.ts.to_pydatetime() if hasattr(row.ts, "to_pydatetime") else row.ts),
                lon=float(row.lon),
                lat=float(row.lat),
                sog=_f(row.sog),
                cog=_f(row.cog),
                heading=_f(row.heading),
                nav_status=NavStatus.from_ais(_s(row.nav)),
            )
            for row in grp.itertuples(index=False)
        ]
        tracks.append(VesselTrack(vessel=vessel, track=positions))
    return tracks


def _s(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _i(v):
    try:
        return int(v) if v is not None and str(v).strip() not in {"", "nan"} else None
    except (ValueError, TypeError):
        return None


def _f(v):
    try:
        f = float(v)
        return f if f == f else None  # NaN guard
    except (ValueError, TypeError):
        return None
