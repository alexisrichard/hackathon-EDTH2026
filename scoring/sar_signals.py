"""Load Signal Brick `vessel_signals` (real if present, else the mock) and shape
it for the ship scorer (per-vessel) and the zone engine (dark-vessel density).

Resolution order — drop the real `vessel_signals.csv` anywhere below and it wins:
  vessel_signals.csv (repo root) · scoring/vessel_signals.csv ·
  data/reference/vessel_signals.csv · data/reference/vessel_signals.mock.csv
"""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
_CANDIDATES = [
    ROOT / "vessel_signals.csv",
    ROOT / "scoring" / "vessel_signals.csv",
    ROOT / "data" / "reference" / "vessel_signals.csv",
    ROOT / "data" / "reference" / "vessel_signals.mock.csv",
]
PER_VESSEL_TYPES = {"ais_dark_approach", "ais_blackout"}


def source_path() -> Path | None:
    return next((p for p in _CANDIDATES if p.exists()), None)


def load_rows() -> list[dict[str, Any]]:
    p = source_path()
    if not p:
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def per_vessel(rows: list[dict[str, Any]] | None = None) -> dict[int, list[dict[str, Any]]]:
    """mmsi -> [{signal_type, signal_date, gap_hours}] ready for
    `score_vessel_risk(...)['sar_signals']` (point-in-time filtering happens there)."""
    if rows is None:
        rows = load_rows()
    out: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("signal_type") not in PER_VESSEL_TYPES:
            continue
        mmsi = r.get("vessel_mmsi")
        if not mmsi or str(mmsi).strip() in ("", "null", "None"):
            continue
        out[int(float(mmsi))].append(
            {
                "signal_type": r["signal_type"],
                "signal_date": r.get("signal_date_utc") or r.get("signal_date"),
                "gap_hours": _num(r.get("gap_hours")),
            }
        )
    return dict(out)


def dark_vessels(rows: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The no-MMSI SAR detections (identity unknown) — feed the ZONE score, not the
    per-vessel score. Returns [{incident_id, lat, lon, sar_confidence, signal_date}]."""
    if rows is None:
        rows = load_rows()
    out = []
    for r in rows:
        if r.get("signal_type") != "dark_vessel":
            continue
        lat, lon = _num(r.get("lat")), _num(r.get("lon"))
        if lat is None or lon is None:
            continue
        out.append(
            {
                "incident_id": r.get("incident_id"),
                "lat": lat,
                "lon": lon,
                "sar_confidence": _num(r.get("sar_confidence")),
                "signal_date": r.get("signal_date_utc") or r.get("signal_date"),
            }
        )
    return out
