"""Shared enums for the maritime cueing-engine domain model.

These normalize the messy real-world AIS vocabulary (the Danish AIS parquet
``Ship type`` column is free-ish text like ``"Tanker"``, ``"Cargo"``,
``"Fishing"``, ``"Pleasure"``, ``"Tug"``, ``"Passenger"``, ``"Undefined"``…)
into a small, stable set the scoring engine and frontend can rely on.

The single source of truth for *display* encoding (shape/color) lives in
``shared/encoding/display_encoding.json`` and is keyed off :class:`ShipType`.
Keep the enum values in sync with that file.
"""

from __future__ import annotations

from enum import Enum


class ShipType(str, Enum):
    """Normalized vessel class.

    Values are lowercase snake_case and are the keys used by
    ``shared/encoding/display_encoding.json`` (``ship_type_to_shape``).
    Use :meth:`from_ais` to map a raw AIS ``Ship type`` string onto this enum.
    """

    TANKER = "tanker"
    CARGO = "cargo"
    FISHING = "fishing"
    PASSENGER = "passenger"
    ROPAX = "ropax"
    TUG = "tug"
    PLEASURE = "pleasure"
    HIGH_SPEED = "high_speed"
    MILITARY = "military"
    LAW_ENFORCEMENT = "law_enforcement"
    SEARCH_AND_RESCUE = "search_and_rescue"
    RESEARCH = "research"
    DREDGER = "dredger"
    PILOT = "pilot"
    PORT_TENDER = "port_tender"
    ANTI_POLLUTION = "anti_pollution"
    WING_IN_GROUND = "wing_in_ground"
    OTHER = "other"
    UNKNOWN = "unknown"

    @classmethod
    def from_ais(cls, raw: str | None) -> "ShipType":
        """Map a raw AIS ``Ship type`` string to a normalized :class:`ShipType`.

        The Danish AIS feed uses human-readable labels rather than the numeric
        AIS type codes, so we match case-insensitively on substrings. Anything
        unrecognized falls back to :attr:`UNKNOWN` (empty/None) or
        :attr:`OTHER` (present but unmapped).
        """
        if not raw:
            return cls.UNKNOWN
        s = raw.strip().lower()
        if not s or s in {"undefined", "unknown", "n/a", "na"}:
            return cls.UNKNOWN
        # Order matters: check more specific labels before generic ones.
        table: list[tuple[str, "ShipType"]] = [
            ("tanker", cls.TANKER),
            ("ropax", cls.ROPAX),
            ("ro-pax", cls.ROPAX),
            ("passenger", cls.PASSENGER),
            ("fishing", cls.FISHING),
            ("dredg", cls.DREDGER),
            ("tug", cls.TUG),
            ("pilot", cls.PILOT),
            ("port tender", cls.PORT_TENDER),
            ("anti-pollution", cls.ANTI_POLLUTION),
            ("pollution", cls.ANTI_POLLUTION),
            ("law enforcement", cls.LAW_ENFORCEMENT),
            ("military", cls.MILITARY),
            ("sar", cls.SEARCH_AND_RESCUE),
            ("search and rescue", cls.SEARCH_AND_RESCUE),
            ("high speed", cls.HIGH_SPEED),
            ("hsc", cls.HIGH_SPEED),
            ("wig", cls.WING_IN_GROUND),
            ("wing in ground", cls.WING_IN_GROUND),
            ("research", cls.RESEARCH),
            ("survey", cls.RESEARCH),
            ("pleasure", cls.PLEASURE),
            ("sailing", cls.PLEASURE),
            ("yacht", cls.PLEASURE),
            ("cargo", cls.CARGO),
        ]
        for needle, value in table:
            if needle in s:
                return value
        return cls.OTHER


class NavStatus(str, Enum):
    """Normalized navigational status.

    Maps from the AIS ``Navigational status`` column (free text in the Danish
    feed, e.g. ``"Under way using engine"``, ``"At anchor"``,
    ``"Engaged in fishing"``, ``"Moored"``, ``"Restricted maneuverability"``).
    """

    UNDER_WAY_ENGINE = "under_way_using_engine"
    UNDER_WAY_SAILING = "under_way_sailing"
    AT_ANCHOR = "at_anchor"
    MOORED = "moored"
    AGROUND = "aground"
    FISHING = "engaged_in_fishing"
    RESTRICTED_MANEUVERABILITY = "restricted_maneuverability"
    CONSTRAINED_BY_DRAUGHT = "constrained_by_draught"
    NOT_UNDER_COMMAND = "not_under_command"
    UNKNOWN = "unknown"

    @classmethod
    def from_ais(cls, raw: str | None) -> "NavStatus":
        """Map a raw AIS ``Navigational status`` string to :class:`NavStatus`."""
        if not raw:
            return cls.UNKNOWN
        s = raw.strip().lower()
        table: list[tuple[str, "NavStatus"]] = [
            ("under way using engine", cls.UNDER_WAY_ENGINE),
            ("under way sailing", cls.UNDER_WAY_SAILING),
            ("at anchor", cls.AT_ANCHOR),
            ("moored", cls.MOORED),
            ("aground", cls.AGROUND),
            ("fishing", cls.FISHING),
            ("restricted man", cls.RESTRICTED_MANEUVERABILITY),
            ("constrained by", cls.CONSTRAINED_BY_DRAUGHT),
            ("not under command", cls.NOT_UNDER_COMMAND),
        ]
        for needle, value in table:
            if needle in s:
                return value
        return cls.UNKNOWN


class SensorType(str, Enum):
    """ISR sensor a cue recommends tasking.

    Drives the cueing overlay color (``sensor_colors`` in the display encoding)
    and tells the operator *what* to point at the recommended box.
    """

    SAR = "SAR"          # Sentinel-1 / commercial SAR — all-weather, sees dark vessels
    OPTICAL = "optical"  # Sentinel-2 / commercial optical — cloud-limited
    AIS = "AIS"          # request a focused AIS re-check / persistent watch
    DAS = "DAS"          # distributed acoustic sensing on the cable (stretch)


class SuspicionBand(str, Enum):
    """Discrete suspicion bands for legends and alert-feed grouping.

    Thresholds are defined in ``shared/encoding/display_encoding.json``
    (``suspicion_bands``) and applied by
    :func:`backend.app.core.display.band_for_score`.
    """

    CALM = "calm"
    WATCH = "watch"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"
