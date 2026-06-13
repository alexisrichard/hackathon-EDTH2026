"""Point-in-time vessel-risk prior — how "shady" a ship looks as of a date.

This is the per-vessel reputation signal that feeds the collection-priority
score (`scoring.score`) as the ``vessel_risk`` factor. It answers: *given only
what was knowable about this vessel at time ``t``, how much prior reason is
there to distrust it?*

Three interpretable sub-signals, each usable only if it was known by ``t``:

- ``behavioral_history`` — derived from the vessel's own AIS track *before* ``t``
  (prior loiters/slow-downs over cables, dark-gaps, kinematic-anomaly rate,
  repeat presence in critical zones). The base signal; it can flag a vessel on
  its own, with no watchlist hit.
- ``identity_risk`` — registry/Equasis facts (flag-of-convenience, flag/name/MMSI
  churn, hull age, owner opacity). An optional on-demand enrichment tier.
- ``watchlist`` — sanctions / shadow-fleet hits. **Fail-closed and point-in-time:**
  a hit counts only if its ``listed_date`` is on or before ``t``. A valid hit
  *floors* the risk high so a real listing can never be averaged away; hits dated
  after ``t`` are reported separately as excluded — the no-look-ahead guarantee.

Like `scoring.score`, this module is pure: the backend computes the sub-signal
values from real data and passes them in. Higher risk = more reason to collect;
this is a defensive cue, not an assessment of intent.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

# Base sub-signal weights (renormalized over whichever signals are available, so
# a missing signal lowers confidence without inventing priority). Watchlist is
# not in here: a valid hit acts as a floor on top of this base, never an average.
BASE_WEIGHTS = {
    "behavioral_history": 0.70,
    "identity_risk": 0.30,
}

# How much each present signal contributes to confidence (input completeness).
# Watchlist is always "checked", so having checked it and found nothing is
# high-confidence information, not missing information.
CONFIDENCE_WEIGHTS = {
    "behavioral_history": 0.60,
    "identity_risk": 0.25,
    "watchlist": 0.15,
}

RISK_DISCLAIMER = (
    "Defensive vessel-risk prior only; reflects information knowable as of the "
    "evaluation time and does not assess hostile intent."
)


def _parse_instant(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC string")
    if not value.endswith("Z"):
        raise ValueError(f"{field_name} must use UTC and end with 'Z'")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp") from exc


def _parse_day(value: Any, field_name: str) -> date:
    """Accept a calendar date ("2025-01-10") or a UTC timestamp; compare at day
    granularity. Sanctions are designated by date, so day-level is the honest
    resolution for the look-ahead check."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be an ISO-8601 date or UTC timestamp")
    text = value.strip()
    try:
        if "T" in text:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 date") from exc


def _unit_value(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number from 0.0 to 1.0")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be a finite number from 0.0 to 1.0")
    return numeric


def _validate_subsignal(
    raw: Any, field_name: str, as_of: datetime
) -> tuple[float, bool, dict[str, Any]]:
    """Validate an optional sub-signal block. Returns (value, available, components).

    Unavailable (absent, or ``available: false``) returns ``(0.0, False, {})`` —
    missing data reduces confidence, it never raises risk. A signal whose
    ``known_through`` is after ``as_of`` is rejected: it would be look-ahead.
    ``components`` is the block's descriptive breakdown (used to explain *why*).
    """
    if raw is None:
        return 0.0, False, {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object")
    if raw.get("available") is False:
        return 0.0, False, {}

    known_through = raw.get("known_through")
    if known_through is None:
        raise ValueError(
            f"{field_name}.known_through is required (the date this signal was knowable)"
        )
    if _parse_instant(known_through, f"{field_name}.known_through") > as_of:
        raise ValueError(
            f"{field_name}.known_through is after as_of — that would be look-ahead"
        )
    components = raw.get("components")
    return (
        _unit_value(raw.get("value"), f"{field_name}.value"),
        True,
        components if isinstance(components, dict) else {},
    )


def _evaluate_watchlist(
    raw: Any, as_of: datetime
) -> tuple[float, list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (floor, applied_hits, excluded_future_hits).

    Only hits with ``listed_date <= as_of`` apply; the floor is the strongest
    such hit's severity. Hits dated after ``as_of`` are returned separately so
    the demo can show *what we deliberately did not use*.
    """
    if raw is None:
        return 0.0, [], []
    if not isinstance(raw, list):
        raise ValueError("watchlist must be a list of hits")

    as_of_day = as_of.date()
    applied: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for index, hit in enumerate(raw):
        prefix = f"watchlist[{index}]"
        if not isinstance(hit, dict):
            raise ValueError(f"{prefix} must be an object")
        listed = _parse_day(hit.get("listed_date"), f"{prefix}.listed_date")
        severity = _unit_value(hit.get("severity"), f"{prefix}.severity")
        source = hit.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"{prefix}.source must be a non-empty string")
        record = {
            "source": source.strip(),
            "listed_date": hit.get("listed_date"),
            "severity": severity,
            "match": hit.get("match"),
        }
        if listed <= as_of_day:
            applied.append(record)
        else:
            excluded.append(record)

    floor = max((hit["severity"] for hit in applied), default=0.0)
    return floor, applied, excluded


def _risk_label(risk: float) -> str:
    if risk >= 0.75:
        return "High"
    if risk >= 0.50:
        return "Elevated"
    if risk >= 0.25:
        return "Moderate"
    return "Low"


# Human phrasing for the strongest behavioural component driving a prior.
_BEHAVIORAL_PHRASES = {
    "dark_events": "it ran dark (long AIS gaps) in the lead-up",
    "loiter": "it loitered at low speed",
    "kinematics": "its course was erratic",
    "critical_proximity": "it lingered near protected infrastructure",
}


def _top_behavioral_phrase(components: dict[str, Any]) -> str:
    """Name the strongest detected behavioural component, so a moderate
    composite with one maxed component still explains itself honestly."""
    ranked = [
        (components.get(name), phrase)
        for name, phrase in _BEHAVIORAL_PHRASES.items()
        if isinstance(components.get(name), (int, float))
    ]
    ranked = [(value, phrase) for value, phrase in ranked if value and value > 0.0]
    if ranked:
        return max(ranked, key=lambda item: item[0])[1]
    return "its prior AIS behaviour is anomalous"


def _explanation(
    risk: float,
    contributions: dict[str, float],
    behavioral_available: bool,
    behavioral_components: dict[str, Any],
    identity_available: bool,
    applied_hits: list[dict[str, Any]],
    excluded_hits: list[dict[str, Any]],
    as_of: str,
) -> str:
    label = _risk_label(risk)
    reasons: list[str] = []
    if applied_hits:
        strongest = max(applied_hits, key=lambda hit: hit["severity"])
        reasons.append(
            f"an active {strongest['source']} listing effective {strongest['listed_date']} "
            f"applies as of {as_of}"
        )

    # Name the dominant base contributor by its actual weight in the score —
    # not a fixed threshold — so a maxed component under a moderate composite is
    # still surfaced as the reason rather than dismissed as "limited".
    base = {k: v for k, v in contributions.items() if v > 0.0}
    if base:
        top = max(base, key=lambda k: base[k])
        if base[top] >= 0.10:
            if top == "behavioral_history":
                reasons.append(_top_behavioral_phrase(behavioral_components))
            elif top == "identity_risk":
                reasons.append("its registered identity carries risk markers")

    if not reasons:
        if behavioral_available or identity_available:
            reasons.append("the known signals are limited")
        else:
            reasons.append("no prior signal was available for this vessel")

    text = f"{label} vessel risk because {', '.join(reasons[:3])}."
    if excluded_hits:
        one = len(excluded_hits) == 1
        text += (
            f" {len(excluded_hits)} watchlist entr{'y' if one else 'ies'} dated "
            f"after {as_of} {'was' if one else 'were'} excluded (no look-ahead)."
        )
    return text


def score_vessel_risk(profile: dict[str, Any]) -> dict[str, Any]:
    """Score one vessel's point-in-time risk prior with transparent rules.

    Input shape (see ``scoring/CONTRACT.md``)::

        {
          "vessel_id": "MMSI:412345678",
          "vessel_name": "Yi Peng 3",          # optional, descriptive
          "is_synthetic": false,
          "as_of": "2024-11-18T00:00:00Z",      # the evaluation instant t
          "behavioral_history": {               # optional sub-signal block
             "available": true,
             "known_through": "2024-11-17T23:59:59Z",   # must be <= as_of
             "value": 0.82,
             "components": {...}                # optional, for the explanation
          },
          "identity_risk": { ... same shape ... },        # optional
          "watchlist": [                                   # optional
             {"source": "OFAC_SDN", "listed_date": "2025-01-10",
              "severity": 0.9, "match": "imo:9224984"}
          ]
        }

    Returns a 0–1 ``risk`` (higher = shadier), the per-signal ``contributions``
    to the base, any ``watchlist`` hits applied vs. excluded, a ``confidence``
    reflecting input completeness, and a human ``explanation``.
    """
    if not isinstance(profile, dict):
        raise ValueError("profile must be an object")

    vessel_id = profile.get("vessel_id")
    if not isinstance(vessel_id, str) or not vessel_id.strip():
        raise ValueError("vessel_id must be a non-empty string")
    if not isinstance(profile.get("is_synthetic"), bool):
        raise ValueError("is_synthetic must be true or false")

    as_of_raw = profile.get("as_of")
    as_of = _parse_instant(as_of_raw, "as_of")

    behavioral_value, behavioral_available, behavioral_components = _validate_subsignal(
        profile.get("behavioral_history"), "behavioral_history", as_of
    )
    identity_value, identity_available, _identity_components = _validate_subsignal(
        profile.get("identity_risk"), "identity_risk", as_of
    )
    floor, applied_hits, excluded_hits = _evaluate_watchlist(
        profile.get("watchlist"), as_of
    )

    # Base = weighted mean over whichever of {behavioral, identity} we have,
    # renormalized so a missing signal cannot inflate or deflate the others.
    available_values = {
        "behavioral_history": (behavioral_value, behavioral_available),
        "identity_risk": (identity_value, identity_available),
    }
    weight_sum = sum(
        BASE_WEIGHTS[name]
        for name, (_value, available) in available_values.items()
        if available
    )
    contributions: dict[str, float] = {}
    if weight_sum > 0.0:
        for name, (value, available) in available_values.items():
            share = (BASE_WEIGHTS[name] / weight_sum) if available else 0.0
            contributions[name] = round(value * share, 4)
        base = sum(contributions.values())
    else:
        contributions = {name: 0.0 for name in BASE_WEIGHTS}
        base = 0.0

    # A valid point-in-time watchlist hit floors the risk; benign behaviour can
    # never average a real listing back down.
    risk = round(min(1.0, max(base, floor)), 4)

    confidence = round(
        CONFIDENCE_WEIGHTS["behavioral_history"] * behavioral_available
        + CONFIDENCE_WEIGHTS["identity_risk"] * identity_available
        + CONFIDENCE_WEIGHTS["watchlist"],  # the watchlist is always checked
        4,
    )

    return {
        "vessel_id": vessel_id.strip(),
        "vessel_name": profile.get("vessel_name"),
        "is_synthetic": profile["is_synthetic"],
        "as_of": as_of_raw,
        "risk": risk,
        "trust": round(1.0 - risk, 4),
        "confidence": confidence,
        "contributions": contributions,
        "watchlist_floor": round(floor, 4),
        "watchlist_floor_applied": floor > base,
        "applied_watchlist_hits": applied_hits,
        "excluded_future_hits": excluded_hits,
        "signals_available": {
            "behavioral_history": behavioral_available,
            "identity_risk": identity_available,
            "watchlist_checked": True,
        },
        "explanation": _explanation(
            risk,
            contributions,
            behavioral_available,
            behavioral_components,
            identity_available,
            applied_hits,
            excluded_hits,
            as_of_raw,
        ),
        "disclaimer": RISK_DISCLAIMER,
    }
