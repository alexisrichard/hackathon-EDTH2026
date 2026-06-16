"""Behavioural feature extraction from AIS keyframe tracks.

Turns a vessel's own AIS history into the ``behavioral_history`` sub-signal that
`scoring.ship_trust.score_vessel_risk` consumes. The same machinery scores two
windows:

- the **long-run prior** — all day-records *before* ``t`` → "what is this
  vessel's track record?" (the reputation signal);
- the **live track** at ``t`` → "what is it doing right now?" (this feeds the
  ``unusual_movement`` factor in `scoring.score`).

Input is the committed keyframe corpus shape (``frontend/public/data/ais/
tracks_YYYY-MM-DD.json``): each vessel-day is ``{"date", "kf", "gaps"}`` where
``kf = [ts_epoch, lon, lat, sog_knots, cog_deg]`` and ``gaps = [[start, end], …]``.

This module is pure and dependency-free. Geometry (proximity to protected
infrastructure) is injected as a ``near_critical(lon, lat) -> bool`` predicate so
the scoring package stays free of geo dependencies; the backend wires in the
real cable layer. When no predicate is supplied, the criticality component is
simply marked unavailable rather than guessed.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

# Tunable, transparent thresholds (a defence audience can read every one).
SLOW_KNOTS = 3.0          # below this, a vessel is loitering, not transiting
DARK_GAP_SECONDS = 1800   # an AIS silence longer than 30 min is a "dark" event
SHARP_TURN_DEGREES = 60.0 # course change between keyframes that reads as erratic

# Sub-feature weights for the composite value (renormalized over whichever are
# available, so a missing component lowers the result, never inflates it).
FEATURE_WEIGHTS = {
    "dark_events": 0.30,
    "loiter": 0.30,
    "kinematics": 0.20,
    "critical_proximity": 0.20,
}

# Normalization scales: the per-day rate that maps to a full 1.0 on that feature.
_DARK_PER_DAY_FULL = 1.0      # ~1 long dark gap per observed day → maxed out
_SHARP_TURN_FRACTION_FULL = 0.20  # 20% of segments being sharp turns → maxed out


def _course_delta(a: float, b: float) -> float:
    """Smallest absolute angle between two compass courses, in degrees."""
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def _validate_day(raw: Any, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"vessel_days[{index}] must be an object")
    day_str = raw.get("date")
    try:
        day = date.fromisoformat(str(day_str))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"vessel_days[{index}].date must be an ISO date (YYYY-MM-DD)"
        ) from exc
    kf = raw.get("kf") or []
    gaps = raw.get("gaps") or []
    if not isinstance(kf, list) or not isinstance(gaps, list):
        raise ValueError(f"vessel_days[{index}].kf and .gaps must be lists")
    return {"date": day, "kf": kf, "gaps": gaps}


def behavioral_history(
    vessel_days: list[dict[str, Any]],
    as_of: str,
    near_critical: Callable[[float, float], bool] | None = None,
) -> dict[str, Any]:
    """Aggregate a vessel's behaviour over the supplied day-records.

    ``vessel_days`` are the per-day track records for ONE vessel. ``as_of`` is an
    ISO-8601 date or UTC timestamp; **every record must be dated strictly before
    it** — passing a day on/after ``as_of`` raises, so the prior can never peek at
    the present. ``near_critical`` is an optional geometry predicate.

    Returns a block shaped for ``score_vessel_risk``'s ``behavioral_history``
    input: ``{available, value, known_through, components}``.
    """
    if not isinstance(vessel_days, list):
        raise ValueError("vessel_days must be a list")
    as_of_day = date.fromisoformat(str(as_of)[:10])

    days = [_validate_day(raw, i) for i, raw in enumerate(vessel_days)]
    for day in days:
        if day["date"] >= as_of_day:
            raise ValueError(
                f"vessel_days contains {day['date']} which is not before "
                f"as_of {as_of_day} — that would be look-ahead"
            )

    observed_days = len(days)
    if observed_days == 0:
        return {
            "available": False,
            "value": 0.0,
            "known_through": None,
            "components": {
                "observed_days": 0,
                "total_keyframes": 0,
            },
        }

    total_kf = slow_kf = critical_slow_kf = 0
    sharp_turns = segments = 0
    long_dark_gaps = 0
    critical_eligible = near_critical is not None

    for day in days:
        kf = day["kf"]
        total_kf += len(kf)
        prev_cog = None
        for point in kf:
            # [ts, lon, lat, sog, cog]
            lon, lat, sog, cog = point[1], point[2], point[3], point[4]
            is_slow = sog < SLOW_KNOTS
            if is_slow:
                slow_kf += 1
                if critical_eligible and near_critical(lon, lat):
                    critical_slow_kf += 1
            if prev_cog is not None:
                segments += 1
                if _course_delta(prev_cog, cog) > SHARP_TURN_DEGREES:
                    sharp_turns += 1
            prev_cog = cog
        for gap in day["gaps"]:
            if len(gap) == 2 and (gap[1] - gap[0]) > DARK_GAP_SECONDS:
                long_dark_gaps += 1

    # Per-feature normalized values in [0, 1].
    dark_value = min(1.0, (long_dark_gaps / observed_days) / _DARK_PER_DAY_FULL)
    loiter_value = (slow_kf / total_kf) if total_kf else 0.0
    kinematics_value = (
        min(1.0, (sharp_turns / segments) / _SHARP_TURN_FRACTION_FULL)
        if segments
        else 0.0
    )
    components = {
        "observed_days": observed_days,
        "total_keyframes": total_kf,
        "long_dark_gaps": long_dark_gaps,
        "slow_keyframes": slow_kf,
        "sharp_turns": sharp_turns,
        "dark_events": round(dark_value, 4),
        "loiter": round(loiter_value, 4),
        "kinematics": round(kinematics_value, 4),
    }

    available_features = {
        "dark_events": dark_value,
        "loiter": loiter_value,
        "kinematics": kinematics_value,
    }
    if critical_eligible:
        critical_value = (critical_slow_kf / slow_kf) if slow_kf else 0.0
        components["critical_slow_keyframes"] = critical_slow_kf
        components["critical_proximity"] = round(critical_value, 4)
        available_features["critical_proximity"] = critical_value

    weight_sum = sum(FEATURE_WEIGHTS[name] for name in available_features)
    value = sum(
        FEATURE_WEIGHTS[name] / weight_sum * feature_value
        for name, feature_value in available_features.items()
    )

    known_through = max(day["date"] for day in days)
    return {
        "available": True,
        "value": round(value, 4),
        # Expose as a UTC instant so it slots straight into score_vessel_risk,
        # which requires known_through <= as_of.
        "known_through": f"{known_through.isoformat()}T23:59:59Z",
        "components": components,
    }
