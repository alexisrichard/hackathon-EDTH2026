"""Typed output of the transparent collection-priority scoring engine.

The real producer is :func:`scoring.score.score_observation`. Five interpretable
inputs are combined with visible weights: infrastructure proximity, unusual
movement, stale AIS, infrastructure importance, and satellite availability.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.enums import SuspicionBand
from app.models.vessel import Vessel, VesselPosition


class ScoreBreakdown(BaseModel):
    """Five factors, their weighted contributions, and a defensive explanation."""

    infrastructure_proximity: float = Field(..., ge=0, le=1)
    unusual_movement: float = Field(..., ge=0, le=1)
    ais_recency: float = Field(..., ge=0, le=1)
    infrastructure_importance: float = Field(..., ge=0, le=1)
    satellite_availability: float = Field(..., ge=0, le=1)
    contributions: dict[str, float] = Field(default_factory=dict)
    why: str = Field(
        "",
        description="Human-readable one-line justification for the score.",
    )
    disclaimer: str = Field(
        "",
        description="Defensive-use framing attached by the scoring engine.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def score(self) -> float:
        """Transparent weighted collection-priority score in [0, 1]."""
        raw = sum(self.contributions.values())
        if not self.contributions:
            raw = (
                0.30 * self.infrastructure_proximity
                + 0.25 * self.unusual_movement
                + 0.15 * (1.0 - self.ais_recency)
                + 0.20 * self.infrastructure_importance
                + 0.10 * self.satellite_availability
            )
        return max(0.0, min(1.0, raw))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def suspicion(self) -> float:
        """Backward-compatible alias for clients using the original field name."""
        return self.score


class DisplayHints(BaseModel):
    """Pre-computed rendering hints so the frontend can render with no logic.

    Filled by the backend from the shared display encoding
    (``shared/encoding/display_encoding.json``). The frontend may also recompute
    these client-side from the mirrored encoding — they will agree by construction.
    """

    shape: str = Field(..., description="deck.gl shape key derived from ship_type.")
    color: list[int] = Field(
        ..., min_length=3, max_length=3,
        description="RGB color [r, g, b] derived from the suspicion score.",
    )
    color_hex: str = Field(..., description="Same color as a #rrggbb string.")
    band: SuspicionBand = Field(..., description="Discrete suspicion band for legends.")


class ScoredVessel(BaseModel):
    """A vessel at a moment in time, with its score breakdown and display hints.

    This is what the ``/scores`` endpoint returns per vessel: enough to plot the
    vessel (position + shape + color) and to explain it (the breakdown + ``why``).
    """

    vessel: Vessel = Field(..., description="Static identity.")
    t: datetime = Field(..., description="Time the score is evaluated at (UTC).")
    position: VesselPosition = Field(
        ..., description="Vessel position at (or interpolated to) time t."
    )
    breakdown: ScoreBreakdown = Field(..., description="Interpretable score terms.")
    display: DisplayHints = Field(..., description="Shape/color rendering hints.")

    @property
    def suspicion(self) -> float:
        """Backward-compatible accessor for the collection-priority score."""
        return self.breakdown.suspicion

    @property
    def score(self) -> float:
        """Preferred accessor for the collection-priority score."""
        return self.breakdown.score
