"""`/scenarios` and `/incidents` — demo replays + the ground-truth catalogue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.data import DataSource
from app.models.responses import IncidentsResponse, ScenariosResponse
from app.models.scenario import Scenario
from app.routers.deps import data_source

router = APIRouter(tags=["scenarios"])


@router.get("/scenarios", response_model=ScenariosResponse, summary="Named demo replays")
def get_scenarios(ds: DataSource = Depends(data_source)) -> ScenariosResponse:
    """Return the named incident-replay scenarios (mirrors shared/scenarios.json)."""
    return ScenariosResponse(scenarios=ds.scenarios())


@router.get("/scenarios/{scenario_id}", response_model=Scenario, summary="One scenario by id")
def get_scenario(scenario_id: str, ds: DataSource = Depends(data_source)) -> Scenario:
    """Return a single scenario by its slug id, or 404 if unknown."""
    for s in ds.scenarios():
        if s.id == scenario_id:
            return s
    raise HTTPException(status_code=404, detail=f"scenario '{scenario_id}' not found")


@router.get("/incidents", response_model=IncidentsResponse, summary="Ground-truth incident timeline")
def get_incidents(ds: DataSource = Depends(data_source)) -> IncidentsResponse:
    """Return the catalogued real incidents from data/reference/incidents.csv."""
    return IncidentsResponse(incidents=ds.incidents())
