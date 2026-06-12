"""Synthetic-but-realistic Eagle S scenario — the heart of the mock data.

Recreates the **Estlink 2 / Eagle S** incident (25 Dec 2024, Gulf of Finland)
densely enough to actually render and demo:

* **EAGLE S** (suspect tanker) enters from the east and *slows to a crawl
  directly over the Estlink 2 power cable*, dragging its anchor. Its suspicion
  climbs over the replay window as it loiters over the cable and its AIS goes
  intermittent — exactly the behavioral pattern the engine should catch.
* A handful of **normal** vessels behave coherently: a Helsinki–Tallinn RoPax
  ferry, a westbound container ship, an anchored bulk carrier, a coastal fishing
  vessel. Their suspicion stays low.

Geometry is anchored to the *real* Estlink 2 cable route (from
``data/geo/submarine_power_cables.geojson``) so positions sit on the actual
cable. The cable crossing near the Finnish side is ~``[26.40, 59.90]``; the
catalogued incident point (``scripts/common/bbox.py``) is ``[26.5, 60.0]``.

Everything is a pure function of a UTC instant ``t`` within the demo window, so
``/scores`` and ``/cues`` re-rank live as the frontend scrubs the clock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.models.enums import NavStatus, ShipType
from app.models.vessel import Vessel, VesselPosition

# --- Demo window -----------------------------------------------------------------
# Christmas Eve 2024, Gulf of Finland. The cable was cut ~12:30 UTC; we run a
# four-hour window so the suspicion arc has room to build and the cue to fire
# *before* the cut.
DEMO_START = datetime(2024, 12, 25, 12, 0, tzinfo=timezone.utc)
DEMO_CUT = datetime(2024, 12, 25, 14, 0, tzinfo=timezone.utc)  # cable goes red
DEMO_END = datetime(2024, 12, 25, 16, 0, tzinfo=timezone.utc)
DEMO_INSTANT = datetime(2024, 12, 25, 13, 50, tzinfo=timezone.utc)  # default "now"

# Estlink 2 anchor points (lon, lat), sampled from the real cable geometry.
ESTLINK2_FINNISH_END = (25.5280455, 60.292964)
ESTLINK2_CROSSING = (26.40, 59.90)  # where the suspect loiters; near incident point
ESTLINK2_ESTONIAN_END = (26.9451001, 59.4372531)

DEMO_BBOX: tuple[float, float, float, float] = (25.4, 59.5, 27.1, 60.45)

SUSPECT_MMSI = 372985000  # EAGLE S (illustrative; real Eagle S MMSI differs)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _frac(t: datetime) -> float:
    """Fraction in [0, 1] of the demo window elapsed at ``t`` (clamped)."""
    span = (DEMO_END - DEMO_START).total_seconds()
    return _clamp((t - DEMO_START).total_seconds() / span)


def _bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Approximate forward azimuth a->b in degrees (small-area flat-earth)."""
    dlon = math.radians(b[0] - a[0])
    lat1, lat2 = math.radians(a[1]), math.radians(b[1])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _lerp_pt(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    f = _clamp(f)
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


@dataclass
class MockVessel:
    """A scripted mock vessel: identity + a position(t) function + score(t) terms."""

    vessel: Vessel
    is_suspect: bool = False
    # Coarse waypoints the vessel interpolates across the *whole* demo window.
    waypoints: list[tuple[float, float]] = field(default_factory=list)

    def position_at(self, t: datetime) -> VesselPosition:
        raise NotImplementedError

    def terms_at(self, t: datetime) -> dict:
        """Return the four score terms + a `why` string at instant ``t``."""
        raise NotImplementedError


def _interp_waypoints(
    waypoints: list[tuple[float, float]], f: float
) -> tuple[tuple[float, float], float]:
    """Position along a polyline at fraction f in [0,1]; returns (point, heading)."""
    if len(waypoints) == 1:
        return waypoints[0], 0.0
    n = len(waypoints) - 1
    scaled = _clamp(f) * n
    i = min(int(scaled), n - 1)
    local = scaled - i
    pt = _lerp_pt(waypoints[i], waypoints[i + 1], local)
    hdg = _bearing(waypoints[i], waypoints[i + 1])
    return pt, hdg


class _SuspectEagleS(MockVessel):
    """EAGLE S — enters from the east, slows over Estlink 2, anchor-drags, AIS gaps.

    The motion profile is tuned so the vessel is parked over the cable and clearly
    "hot" *before* the 14:00 cut, matching the hero narrative ("watch the engine
    recommend tasking this box — the cable goes down 14 minutes later"):
    transit at ~10 kn until ~12:53 (f≈0.22), decelerate onto the cable crossing by
    ~13:24 (f≈0.35), then loiter / anchor-drag at ~1–2 kn through the cut and after.
    Suspicion is built from the four interpretable terms and climbs as the vessel
    parks on the cable and its AIS reports thin out.
    """

    # Phase boundaries as fractions of the demo window (12:00–16:00):
    #   f=0.22 -> ~12:53, f=0.35 -> ~13:24, cut at f=0.50 (14:00).
    _F_TRANSIT_END = 0.22
    _F_DECEL_END = 0.35

    def position_at(self, t: datetime) -> VesselPosition:
        f = _frac(t)
        # Path: come in from the east, converge on the cable crossing, then sit.
        entry = (26.95, 59.98)
        approach = (26.62, 59.93)
        if f < self._F_TRANSIT_END:
            pt = _lerp_pt(entry, approach, f / self._F_TRANSIT_END)
            sog = 10.5
            hdg = _bearing(entry, approach)
            nav = NavStatus.UNDER_WAY_ENGINE
        elif f < self._F_DECEL_END:
            # Decelerating onto the cable crossing.
            local = (f - self._F_TRANSIT_END) / (self._F_DECEL_END - self._F_TRANSIT_END)
            pt = _lerp_pt(approach, ESTLINK2_CROSSING, local)
            sog = 10.5 - local * 8.5  # 10.5 -> ~2 kn
            hdg = _bearing(approach, ESTLINK2_CROSSING)
            nav = NavStatus.UNDER_WAY_ENGINE
        else:
            # Loitering / anchor-dragging: tiny wander around the crossing.
            wander = (f - self._F_DECEL_END) * 0.06
            pt = (ESTLINK2_CROSSING[0] - wander, ESTLINK2_CROSSING[1] + wander * 0.5)
            sog = 1.6
            hdg = 250.0
            nav = NavStatus.UNDER_WAY_ENGINE  # *claims* under way, but barely moving
        return VesselPosition(
            t=t,
            lon=round(pt[0], 5),
            lat=round(pt[1], 5),
            sog=round(sog, 1),
            cog=round(hdg, 0),
            heading=round(hdg, 0),
            nav_status=nav,
        )

    def terms_at(self, t: datetime) -> dict:
        f = _frac(t)
        # Kinematic anomaly: low while transiting, spikes once it decelerates and
        # parks at ~2 kn over the cable (deceleration starts at f=0.22).
        if f < self._F_TRANSIT_END:
            kin = 0.15 + f * 0.5
        else:
            kin = _clamp(0.3 + (f - self._F_TRANSIT_END) * 3.0)  # ramps toward ~1.0
        # Class coherence: a tanker loitering over a cable is *incoherent* (low).
        # Drops sharply once it starts braking onto the crossing.
        coherence = _clamp(0.88 - max(0.0, f - self._F_TRANSIT_END) * 3.0)
        # Local criticality: rises as it converges on the cable crossing, peaking
        # once it's over Estlink 2.
        crit = min(0.95, _clamp(0.3 + f * 1.6))
        # Dark modifier: nominal 1.0; stays 1.0 (intermittent AIS, never confirmed lit).
        dark = 1.0
        # AIS gap minutes grow as it loiters (for the narrative string).
        gap_min = int(max(0.0, f - self._F_DECEL_END) * 120)
        sog = self.position_at(t).sog or 0.0
        why = (
            f"Declared tanker behaving like a loiterer: slowed to {sog:.0f} kn directly "
            f"over Estlink 2 (criticality {crit:.2f}), class-coherence {coherence:.2f}"
        )
        if gap_min > 0:
            why += f", AIS gap {gap_min} min"
        why += "."
        return {
            "kinematic_anomaly": round(kin, 3),
            "class_coherence": round(coherence, 3),
            "local_criticality": round(crit, 3),
            "dark_modifier": round(dark, 3),
            "why": why,
        }


class _NormalTransit(MockVessel):
    """A coherent vessel that just transits along its waypoints at steady speed."""

    sog_kn: float = 14.0
    crit_base: float = 0.2

    def __init__(self, *args, sog_kn: float = 14.0, crit_base: float = 0.2, **kwargs):
        super().__init__(*args, **kwargs)
        self.sog_kn = sog_kn
        self.crit_base = crit_base

    def position_at(self, t: datetime) -> VesselPosition:
        f = _frac(t)
        pt, hdg = _interp_waypoints(self.waypoints, f)
        return VesselPosition(
            t=t,
            lon=round(pt[0], 5),
            lat=round(pt[1], 5),
            sog=self.sog_kn,
            cog=round(hdg, 0),
            heading=round(hdg, 0),
            nav_status=NavStatus.UNDER_WAY_ENGINE,
        )

    def terms_at(self, t: datetime) -> dict:
        # Coherent behavior: low kinematic anomaly, high coherence, modest criticality.
        return {
            "kinematic_anomaly": 0.12,
            "class_coherence": 0.9,
            "local_criticality": round(self.crit_base, 3),
            "dark_modifier": 1.0,
            "why": (
                f"Declared {self.vessel.ship_type.value} transiting normally "
                f"(~{self.sog_kn:.0f} kn), behavior coherent with class."
            ),
        }


class _AnchoredBulker(MockVessel):
    """A bulk carrier legitimately at anchor in a designated anchorage — coherent."""

    def position_at(self, t: datetime) -> VesselPosition:
        # Tiny swing around its anchor point.
        f = _frac(t)
        base = self.waypoints[0]
        swing = 0.004 * math.sin(f * math.tau)
        return VesselPosition(
            t=t,
            lon=round(base[0] + swing, 5),
            lat=round(base[1] + swing * 0.4, 5),
            sog=0.1,
            cog=0.0,
            heading=round((f * 360.0) % 360.0, 0),
            nav_status=NavStatus.AT_ANCHOR,
        )

    def terms_at(self, t: datetime) -> dict:
        # At anchor in an anchorage is normal -> very low suspicion despite low SOG,
        # because criticality at the anchorage is low and coherence is high.
        return {
            "kinematic_anomaly": 0.2,
            "class_coherence": 0.88,
            "local_criticality": 0.08,
            "dark_modifier": 1.0,
            "why": "At anchor in a designated anchorage; nav status 'at anchor', coherent.",
        }


def _mk(
    mmsi: int,
    name: str,
    ship_type: ShipType,
    *,
    imo: int | None = None,
    callsign: str | None = None,
    length: float | None = None,
    width: float | None = None,
    draught: float | None = None,
    flag: str | None = None,
    destination: str | None = None,
) -> Vessel:
    return Vessel(
        mmsi=mmsi,
        name=name,
        imo=imo,
        callsign=callsign,
        ship_type=ship_type,
        length=length,
        width=width,
        draught=draught,
        flag=flag,
        destination=destination,
    )


def build_mock_fleet() -> list[MockVessel]:
    """Construct the scripted fleet for the Eagle S demo scenario."""
    fleet: list[MockVessel] = []

    # 1) The suspect — EAGLE S.
    fleet.append(
        _SuspectEagleS(
            vessel=_mk(
                SUSPECT_MMSI, "EAGLE S", ShipType.TANKER,
                imo=9329760, callsign="5BWC3",
                length=228.0, width=32.0, draught=8.4,
                flag="Cook Islands", destination="PORT SAID",
            ),
            is_suspect=True,
        )
    )

    # 2) Helsinki <-> Tallinn RoPax ferry (busy, coherent route across the gulf).
    fleet.append(
        _NormalTransit(
            vessel=_mk(
                230123000, "MEGASTAR", ShipType.ROPAX,
                imo=9773064, callsign="OJ KA",
                length=212.0, width=30.6, draught=7.1,
                flag="Finland", destination="TALLINN",
            ),
            waypoints=[(24.95, 60.15), (24.78, 59.44)],  # Helsinki -> Tallinn
            sog_kn=22.0,
            crit_base=0.28,
        )
    )

    # 3) Westbound container ship transiting the gulf.
    fleet.append(
        _NormalTransit(
            vessel=_mk(
                477553000, "EVER GIVEN II", ShipType.CARGO,
                imo=9811000, callsign="VRPQ7",
                length=190.0, width=29.0, draught=10.5,
                flag="Hong Kong", destination="ROTTERDAM",
            ),
            waypoints=[(27.0, 60.05), (25.4, 59.95)],  # E -> W across the gulf
            sog_kn=15.0,
            crit_base=0.3,
        )
    )

    # 4) Coastal fishing vessel working a normal pattern near the Finnish coast.
    fleet.append(
        _NormalTransit(
            vessel=_mk(
                230456000, "SAARISTO", ShipType.FISHING,
                imo=None, callsign="OG KB",
                length=18.0, width=6.0, draught=2.5,
                flag="Finland", destination="FISHING",
            ),
            waypoints=[(25.9, 60.25), (26.1, 60.32), (25.85, 60.28), (26.0, 60.22)],
            sog_kn=5.0,
            crit_base=0.15,
        )
    )

    # 5) Bulk carrier at anchor in the Porvoo/Sköldvik anchorage — coherent.
    fleet.append(
        _AnchoredBulker(
            vessel=_mk(
                636092000, "PACIFIC ORE", ShipType.CARGO,
                imo=9456789, callsign="A8XY2",
                length=180.0, width=28.0, draught=11.0,
                flag="Liberia", destination="SKOLDVIK",
            ),
            waypoints=[(25.55, 60.18)],
        )
    )

    return fleet


def track_times(
    start: datetime | None = None,
    end: datetime | None = None,
    step: timedelta = timedelta(minutes=5),
) -> list[datetime]:
    """Time samples for building tracks, clamped to the demo window."""
    s = max(start or DEMO_START, DEMO_START)
    e = min(end or DEMO_END, DEMO_END)
    if e < s:
        s, e = DEMO_START, DEMO_END
    out: list[datetime] = []
    cur = s
    while cur <= e:
        out.append(cur)
        cur += step
    if not out:
        out = [DEMO_INSTANT]
    return out
