"""Display-encoding helpers — the backend half of the shared shape/color contract.

These functions read ``shared/encoding/display_encoding.json`` (the single
source of truth) and turn a :class:`ShipType` into a shape key and a suspicion
score into an RGB color + band. The frontend mirrors the *same* JSON in
``frontend/src/types/encoding.ts``, so backend display hints and frontend
rendering never drift.

The backend fills these hints into :class:`~backend.app.models.scoring.ScoredVessel`
so the frontend can render with zero scoring knowledge if it wants — but the raw
encoding is also exported to the frontend, which can recompute client-side.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.models.enums import ShipType, SuspicionBand

# shared/encoding/display_encoding.json, resolved relative to the repo root.
# backend/app/core/display.py -> parents[3] == repo root.
_ENCODING_PATH = (
    Path(__file__).resolve().parents[3] / "shared" / "encoding" / "display_encoding.json"
)

RGB = tuple[int, int, int]


@lru_cache(maxsize=1)
def _encoding() -> dict:
    """Load and cache the shared display-encoding JSON."""
    with _ENCODING_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def shape_for_ship_type(ship_type: ShipType) -> str:
    """Return the deck.gl shape key for a normalized vessel class."""
    table = _encoding()["ship_type_to_shape"]
    return table.get(ship_type.value, table.get("unknown", "circle"))


def color_for_suspicion(score: float) -> RGB:
    """Interpolate the suspicion color ramp at ``score`` in [0, 1] -> RGB.

    Piecewise-linear between the stops defined in the shared JSON. Scores are
    clamped to [0, 1] so callers never have to pre-clamp.
    """
    s = max(0.0, min(1.0, float(score)))
    stops = _encoding()["suspicion_color_stops"]["stops"]
    # stops are sorted ascending by score; find the bracketing pair.
    prev_pos, prev_rgb = stops[0]
    for pos, rgb in stops:
        if s <= pos:
            if pos == prev_pos:
                return tuple(int(round(c)) for c in rgb)  # type: ignore[return-value]
            frac = (s - prev_pos) / (pos - prev_pos)
            return tuple(  # type: ignore[return-value]
                int(round(prev_rgb[i] + frac * (rgb[i] - prev_rgb[i]))) for i in range(3)
            )
        prev_pos, prev_rgb = pos, rgb
    return tuple(int(round(c)) for c in stops[-1][1])  # type: ignore[return-value]


def color_hex_for_suspicion(score: float) -> str:
    """Same as :func:`color_for_suspicion` but as a ``#rrggbb`` hex string."""
    r, g, b = color_for_suspicion(score)
    return f"#{r:02x}{g:02x}{b:02x}"


def band_for_score(score: float) -> SuspicionBand:
    """Bucket a suspicion score into a discrete :class:`SuspicionBand`."""
    s = max(0.0, min(1.0, float(score)))
    bands = _encoding()["suspicion_bands"]
    for name, rng in bands.items():
        if name.startswith("_"):
            continue
        lo, hi = rng
        if lo <= s < hi:
            return SuspicionBand(name)
    return SuspicionBand.CRITICAL
