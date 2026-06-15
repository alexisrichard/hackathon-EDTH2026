"""Vessel identity, position, and track models.

These map directly onto the Danish AIS parquet schema in the local dataset
(``data/ais/parquet/source=danish/...``; the ``edth2026-baltic`` S3 bucket is
retired). The relevant columns are::

    Timestamp, Type of mobile, MMSI, Latitude, Longitude, Navigational status,
    ROT, SOG, COG, Heading, IMO, Callsign, Name, Ship type, Cargo type,
    Width, Length, Type of position fixing device, Draught, Destination, ETA,
    A, B, C, D, ts, day, month, source, year

We keep the *normalized* domain fields here (snake_case, typed, enums) and leave
the raw-column mapping to the data-access layer.

Conventions (AGENTS.md §2): coordinates are ``[lon, lat]`` EPSG:4326, times are
ISO-8601 UTC.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import NavStatus, ShipType


class Vessel(BaseModel):
    """Static / semi-static vessel identity, derived from AIS class-A/B reports.

    A vessel is keyed by its MMSI. IMO, callsign, dimensions, and draught come
    from the (less frequent) static AIS message; they may be missing for class-B
    or partially reporting vessels.
    """

    mmsi: int = Field(..., description="Maritime Mobile Service Identity (9 digits).")
    name: str | None = Field(None, description="Vessel name from AIS static data.")
    imo: int | None = Field(None, description="IMO number, if broadcast.")
    callsign: str | None = Field(None, description="Radio callsign, if broadcast.")
    ship_type: ShipType = Field(
        ShipType.UNKNOWN,
        description="Normalized declared vessel class (from AIS 'Ship type').",
    )
    cargo_type: str | None = Field(
        None, description="Declared cargo category, if broadcast (AIS 'Cargo type')."
    )
    length: float | None = Field(None, description="Overall length in metres (A+B).")
    width: float | None = Field(None, description="Overall beam in metres (C+D).")
    draught: float | None = Field(None, description="Reported draught in metres.")
    flag: str | None = Field(
        None,
        description=(
            "Flag state. Not in the AIS feed directly; derived from the MMSI MID "
            "(first 3 digits) or a registry join. May be None when unresolved."
        ),
    )
    destination: str | None = Field(
        None, description="Declared destination (free text, often noisy)."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "mmsi": 372985000,
                "name": "EAGLE S",
                "imo": 9329760,
                "callsign": "5BWC3",
                "ship_type": "tanker",
                "cargo_type": None,
                "length": 228.0,
                "width": 32.0,
                "draught": 8.4,
                "flag": "Cook Islands",
                "destination": "PORT SAID",
            }
        }
    }


class VesselPosition(BaseModel):
    """A single time-stamped kinematic AIS report for a vessel.

    Maps to one AIS position message: ``Timestamp`` -> ``t``,
    ``Longitude/Latitude`` -> ``lon/lat``, ``SOG/COG/Heading`` -> same,
    ``Navigational status`` -> ``nav_status``.
    """

    t: datetime = Field(..., description="Report time, ISO-8601 UTC.")
    lon: float = Field(..., ge=-180, le=180, description="Longitude, EPSG:4326.")
    lat: float = Field(..., ge=-90, le=90, description="Latitude, EPSG:4326.")
    sog: float | None = Field(None, ge=0, description="Speed over ground, knots.")
    cog: float | None = Field(
        None, ge=0, le=360, description="Course over ground, degrees true."
    )
    heading: float | None = Field(
        None, ge=0, le=511, description="True heading, degrees (511 = not available)."
    )
    nav_status: NavStatus = Field(
        NavStatus.UNKNOWN, description="Normalized navigational status."
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "t": "2024-12-25T14:00:00Z",
                "lon": 26.4,
                "lat": 60.0,
                "sog": 2.1,
                "cog": 92.0,
                "heading": 95.0,
                "nav_status": "under_way_using_engine",
            }
        }
    }


class VesselTrack(BaseModel):
    """A vessel plus its ordered sequence of positions over a time window."""

    vessel: Vessel = Field(..., description="Static identity for this track.")
    track: list[VesselPosition] = Field(
        default_factory=list,
        description="Positions ordered ascending by time (UTC).",
    )

    @property
    def mmsi(self) -> int:
        """Convenience accessor matching the flat API contract shape."""
        return self.vessel.mmsi
