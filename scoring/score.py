"""Explainable, rule-based scoring for defensive maritime collection cues."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any

BALTIC_BBOX = {
    "min_lat": 52.0,
    "max_lat": 66.0,
    "min_lon": 9.0,
    "max_lon": 30.0,
}

GRID_SIZE_KM = 50.0
KM_PER_DEGREE_LAT = 111.32

WEIGHTS = {
    "infrastructure_proximity": 0.30,
    "unusual_movement": 0.25,
    "ais_staleness": 0.15,
    "infrastructure_importance": 0.20,
    "satellite_availability": 0.10,
}

SCORE_DISCLAIMER = (
    "Defensive collection cue only; this score does not assess hostile intent."
)
TASKING_DISCLAIMER = (
    "Defensive collection cue only; this recommendation is not for targeting."
)

_REQUIRED_FACTORS = {
    "infrastructure_proximity",
    "unusual_movement",
    "ais_recency",
    "infrastructure_importance",
}


def _parse_timestamp(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be an ISO-8601 UTC string")
    if not value.endswith("Z"):
        raise ValueError(f"{field_name} must use UTC and end with 'Z'")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field_name} is not a valid ISO-8601 timestamp") from exc
    return parsed


def _unit_value(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number from 0.0 to 1.0")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise ValueError(f"{field_name} must be a finite number from 0.0 to 1.0")
    return numeric


def _validate_position(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("position must be [longitude, latitude]")
    lon, lat = value
    if (
        isinstance(lon, bool)
        or isinstance(lat, bool)
        or not isinstance(lon, (int, float))
        or not isinstance(lat, (int, float))
    ):
        raise ValueError("position coordinates must be finite numbers")
    lon, lat = float(lon), float(lat)
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError("position coordinates must be finite numbers")
    if not (
        BALTIC_BBOX["min_lon"] <= lon <= BALTIC_BBOX["max_lon"]
        and BALTIC_BBOX["min_lat"] <= lat <= BALTIC_BBOX["max_lat"]
    ):
        raise ValueError("position must be inside the project Baltic bounding box")
    return lon, lat


def _validated_windows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("satellite_windows must be a list")

    windows = []
    for index, raw_window in enumerate(value):
        prefix = f"satellite_windows[{index}]"
        if not isinstance(raw_window, dict):
            raise ValueError(f"{prefix} must be an object")
        start = _parse_timestamp(raw_window.get("start"), f"{prefix}.start")
        end = _parse_timestamp(raw_window.get("end"), f"{prefix}.end")
        if end <= start:
            raise ValueError(f"{prefix}.end must be after its start")
        sensor = raw_window.get("sensor")
        if not isinstance(sensor, str) or not sensor.strip():
            raise ValueError(f"{prefix}.sensor must be a non-empty string")
        if not isinstance(raw_window.get("is_synthetic"), bool):
            raise ValueError(f"{prefix}.is_synthetic must be true or false")
        windows.append(
            {
                "start": raw_window["start"],
                "end": raw_window["end"],
                "sensor": sensor.strip(),
                "availability": _unit_value(
                    raw_window.get("availability"), f"{prefix}.availability"
                ),
                "is_synthetic": raw_window["is_synthetic"],
            }
        )
    return windows


def _validate_observation(observation: Any) -> dict[str, Any]:
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")

    vessel_id = observation.get("vessel_id")
    if not isinstance(vessel_id, str) or not vessel_id.strip():
        raise ValueError("vessel_id must be a non-empty string")
    if not isinstance(observation.get("is_synthetic"), bool):
        raise ValueError("is_synthetic must be true or false")

    observed_at = _parse_timestamp(observation.get("observed_at"), "observed_at")
    position = _validate_position(observation.get("position"))

    raw_factors = observation.get("factors")
    if not isinstance(raw_factors, dict):
        raise ValueError("factors must be an object")
    missing = _REQUIRED_FACTORS - set(raw_factors)
    if missing:
        raise ValueError(f"missing required factors: {', '.join(sorted(missing))}")
    factors = {
        name: _unit_value(raw_factors[name], f"factors.{name}")
        for name in sorted(_REQUIRED_FACTORS)
    }

    windows = _validated_windows(observation.get("satellite_windows"))
    return {
        "vessel_id": vessel_id.strip(),
        "vessel_name": observation.get("vessel_name"),
        "is_synthetic": observation["is_synthetic"],
        "observed_at": observation["observed_at"],
        "observed_at_parsed": observed_at,
        "position": position,
        "factors": factors,
        "infrastructure": observation.get("infrastructure"),
        "satellite_windows": windows,
    }


def _best_window(
    windows: list[dict[str, Any]], observed_at: datetime
) -> dict[str, Any] | None:
    current_or_future = [
        window
        for window in windows
        if window["availability"] > 0.0
        and _parse_timestamp(window["end"], "satellite window end") > observed_at
    ]
    if not current_or_future:
        return None
    return sorted(
        current_or_future,
        key=lambda window: (
            -window["availability"],
            window["start"],
            window["sensor"],
        ),
    )[0]


def _priority_label(score: float) -> str:
    if score >= 0.75:
        return "High"
    if score >= 0.50:
        return "Medium"
    return "Low"


def _observation_explanation(
    factors: dict[str, float], best_window: dict[str, Any] | None, score: float
) -> str:
    reasons: list[tuple[float, str]] = [
        (
            factors["infrastructure_proximity"],
            "the vessel is close to protected infrastructure",
        ),
        (
            factors["unusual_movement"],
            "its movement is unusual",
        ),
        (
            1.0 - factors["ais_recency"],
            "its latest AIS position is becoming stale",
        ),
        (
            factors["infrastructure_importance"],
            "the nearby infrastructure has high strategic importance",
        ),
    ]
    selected = [text for value, text in sorted(reasons, reverse=True) if value >= 0.60]

    if best_window and best_window["availability"] >= 0.60:
        selected.append(f"a {best_window['sensor']} collection window is available")
    if not selected:
        selected.append("the combined indicators are limited")

    reason_text = ", ".join(selected[:3])
    return f"{_priority_label(score)} observation priority because {reason_text}."


def score_observation(observation: dict[str, Any]) -> dict[str, Any]:
    """Validate and score one vessel observation with transparent weighted rules."""

    validated = _validate_observation(observation)
    factors = validated["factors"]
    best_window = _best_window(
        validated["satellite_windows"], validated["observed_at_parsed"]
    )
    satellite_availability = best_window["availability"] if best_window else 0.0
    ais_staleness = 1.0 - factors["ais_recency"]

    contributions = {
        "infrastructure_proximity": (
            factors["infrastructure_proximity"]
            * WEIGHTS["infrastructure_proximity"]
        ),
        "unusual_movement": (
            factors["unusual_movement"] * WEIGHTS["unusual_movement"]
        ),
        "ais_staleness": ais_staleness * WEIGHTS["ais_staleness"],
        "infrastructure_importance": (
            factors["infrastructure_importance"]
            * WEIGHTS["infrastructure_importance"]
        ),
        "satellite_availability": (
            satellite_availability * WEIGHTS["satellite_availability"]
        ),
    }
    score = round(sum(contributions.values()), 4)

    return {
        "vessel_id": validated["vessel_id"],
        "score": score,
        "confidence": 1.0,
        "factors": {
            **factors,
            "satellite_availability": satellite_availability,
        },
        "contributions": {
            name: round(value, 4) for name, value in contributions.items()
        },
        "explanation": _observation_explanation(factors, best_window, score),
        "disclaimer": SCORE_DISCLAIMER,
    }


def _grid_box(position: tuple[float, float]) -> tuple[str, list[float]]:
    lon, lat = position
    lat_step = GRID_SIZE_KM / KM_PER_DEGREE_LAT
    lat_index = math.floor((lat - BALTIC_BBOX["min_lat"]) / lat_step)
    min_lat = BALTIC_BBOX["min_lat"] + lat_index * lat_step
    max_lat = min(min_lat + lat_step, BALTIC_BBOX["max_lat"])

    center_lat = (min_lat + max_lat) / 2.0
    km_per_degree_lon = KM_PER_DEGREE_LAT * math.cos(math.radians(center_lat))
    lon_step = GRID_SIZE_KM / km_per_degree_lon
    lon_index = math.floor((lon - BALTIC_BBOX["min_lon"]) / lon_step)
    min_lon = BALTIC_BBOX["min_lon"] + lon_index * lon_step
    max_lon = min(min_lon + lon_step, BALTIC_BBOX["max_lon"])

    grid_id = f"baltic-50km-{lat_index:02d}-{lon_index:02d}"
    bbox = [round(min_lon, 5), round(min_lat, 5), round(max_lon, 5), round(max_lat, 5)]
    return grid_id, bbox


def _aggregate_scores(scores: list[float]) -> float:
    ordered = sorted(scores, reverse=True)
    if not ordered:
        return 0.0
    # The strongest observation drives the box; additional observations add
    # limited corroboration without allowing a busy area to dominate.
    return round(min(1.0, ordered[0] + 0.10 * sum(ordered[1:])), 4)


def rank_tasking(
    observations: list[dict[str, Any]], top_n: int = 5
) -> list[dict[str, Any]]:
    """Return the highest-priority 50 km boxes that have collection windows."""

    if not isinstance(observations, list):
        raise ValueError("observations must be a list")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 0:
        raise ValueError("top_n must be a non-negative integer")
    if top_n == 0 or not observations:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    boxes: dict[str, list[float]] = {}

    for observation in observations:
        validated = _validate_observation(observation)
        best_window = _best_window(
            validated["satellite_windows"], validated["observed_at_parsed"]
        )
        if best_window is None:
            continue
        scored = score_observation(observation)
        grid_id, bbox = _grid_box(validated["position"])
        boxes[grid_id] = bbox
        grouped[grid_id].append(
            {
                "validated": validated,
                "scored": scored,
                "window": best_window,
            }
        )

    candidates = []
    for grid_id, entries in grouped.items():
        entries.sort(
            key=lambda entry: (
                -entry["scored"]["score"],
                entry["validated"]["vessel_id"],
            )
        )
        selected_window = sorted(
            (entry["window"] for entry in entries),
            key=lambda window: (
                -window["availability"],
                window["start"],
                window["sensor"],
            ),
        )[0]
        drivers = sorted(entry["validated"]["vessel_id"] for entry in entries)
        box_score = _aggregate_scores(
            [entry["scored"]["score"] for entry in entries]
        )
        lead = entries[0]
        infrastructure = lead["validated"].get("infrastructure") or {}
        infrastructure_name = infrastructure.get(
            "name", "protected maritime infrastructure"
        )
        driver_word = "observation" if len(drivers) == 1 else "observations"
        candidates.append(
            {
                "grid_id": grid_id,
                "bbox": boxes[grid_id],
                "score": box_score,
                "recommended_window": {
                    "start": selected_window["start"],
                    "end": selected_window["end"],
                    "sensor": selected_window["sensor"],
                },
                "drivers": drivers,
                "explanation": (
                    f"{len(drivers)} synthetic vessel {driver_word} near "
                    f"{infrastructure_name}; {selected_window['sensor']} "
                    "collection is available in the supplied demo schedule."
                ),
                "is_synthetic": any(
                    entry["validated"]["is_synthetic"]
                    or entry["window"]["is_synthetic"]
                    for entry in entries
                ),
                "disclaimer": TASKING_DISCLAIMER,
            }
        )

    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["grid_id"]))
    ranked = candidates[:top_n]
    for index, candidate in enumerate(ranked, start=1):
        candidate["rank"] = index
    return ranked
