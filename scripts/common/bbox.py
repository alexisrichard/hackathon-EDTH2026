"""Baltic Sea bounding box and incident windows shared across scripts."""

from datetime import date

BALTIC_BBOX = {
    "min_lat": 52.0,
    "max_lat": 66.0,
    "min_lon": 9.0,
    "max_lon": 30.0,
}

BALTIC_BBOX_WKT = (
    "POLYGON((9.0 52.0, 30.0 52.0, 30.0 66.0, 9.0 66.0, 9.0 52.0))"
)

S3_BUCKET = "edth2026-baltic"
S3_REGION = "eu-west-3"

INCIDENTS = [
    ("2022-09-26", "Nord Stream 1+2 explosions", 55.5, 15.7),
    ("2023-10-08", "Balticconnector + EE-FI telecom cable (Newnew Polar Bear)", 59.9, 23.3),
    ("2024-11-17", "C-Lion1 + BCS East-West (Yi Peng 3)", 55.3, 16.0),
    ("2024-12-25", "Estlink 2 + 4 telecom cables (Eagle S)", 60.0, 26.5),
    ("2025-01-26", "Latvia-Sweden cable", 57.8, 19.5),
]
