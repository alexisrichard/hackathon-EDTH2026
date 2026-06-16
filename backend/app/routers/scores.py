"""`/scores` — per-vessel suspicion at instant t, with the interpretable breakdown."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.data import DataSource
from app.models.query import TimeQuery, time_params
from app.models.responses import ScoresResponse
from app.routers.deps import data_source

router = APIRouter(tags=["scores"])


@router.get("/scores", response_model=ScoresResponse, summary="Suspicion scores at instant t")
def get_scores(
    q: TimeQuery = Depends(time_params),
    ds: DataSource = Depends(data_source),
) -> ScoresResponse:
    """Return each vessel's five-factor collection priority + display hints at
    instant ``t`` (defaults to the demo instant), sorted highest-first."""
    scored = ds.scores_at(t=q.t, bbox=q.bbox)
    # Echo the instant the scores were actually evaluated at (the data source
    # resolves a None t to its demo instant), so the response t matches the
    # per-vessel t exactly.
    when = q.t or (scored[0].t if scored else None)
    return ScoresResponse(t=when, scores=scored)
