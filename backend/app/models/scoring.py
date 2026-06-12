"""Suspicion-score models — the interpretable output of the scoring engine.

Mirrors PLAN.md §5.4 *exactly*::

    suspicion(vessel, t) = kinematic_anomaly(vessel, t)
                         × (1 − class_coherence(vessel, t))
                         × local_criticality(vessel.position)
                         × dark_modifier(vessel, t)

Every term is in [0, 1] and interpretable on its own, so the dashboard can show
the breakdown ("declared tanker, behaving incoherently, over Estlink 2, AIS
gap"). The composite ``suspicion`` is the product above, also clamped to [0, 1].

The scoring engine (``scoring/score.py``, the ML lane) is the real producer of
:class:`ScoreBreakdown`. The backend treats it as a contract: it asks the engine
(or the mock) for a breakdown and decorates it with display hints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, computed_field

from app.models.enums import SuspicionBand
from app.models.vessel import Vessel, VesselPosition


class ScoreBreakdown(BaseModel):
    """The four interpretable score terms plus the composite suspicion.

    The composite follows PLAN §5.4. Note the formula uses ``(1 − class_coherence)``:
    *high* coherence (vessel behaving normally for its class) *lowers* suspicion,
    so we store ``class_coherence`` itself (0 = totally incoherent, 1 = perfectly
    normal) and apply the inversion in :meth:`suspicion`.
    """

    kinematic_anomaly: float = Field(
        ..., ge=0, le=1,
        description="How anomalous the vessel's motion is (1 = very anomalous).",
    )
    class_coherence: float = Field(
        ..., ge=0, le=1,
        description=(
            "How coherent behavior is with the declared class "
            "(1 = perfectly normal, 0 = totally incoherent). "
            "The formula multiplies by (1 − this)."
        ),
    )
    local_criticality: float = Field(
        ..., ge=0, le=1,
        description="Strategic criticality of the vessel's location (1 = over a cable/base).",
    )
    dark_modifier: float = Field(
        1.0, ge=0, le=1,
        description=(
            "AIS-darkness multiplier in [0, 1]. 1.0 = nominal — applied to dark / "
            "AIS-dropout vessels and to anyone we cannot rule out (the suspicious "
            "default). Values <1 *downweight* a vessel that an independent sensor "
            "(e.g. Sentinel-1 SAR) has confidently confirmed as continuously, "
            "honestly lit. Since the four terms multiply, keeping the nominal at "
            "1.0 means darkness never discounts suspicion; only positive "
            "confirmation does."
        ),
    )
    why: str = Field(
        "",
        description="Human-readable one-line justification for the score.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def suspicion(self) -> float:
        """Composite suspicion per PLAN §5.4, clamped to [0, 1]."""
        raw = (
            self.kinematic_anomaly
            * (1.0 - self.class_coherence)
            * self.local_criticality
            * self.dark_modifier
        )
        return max(0.0, min(1.0, raw))


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
        """Convenience accessor for the composite suspicion."""
        return self.breakdown.suspicion
