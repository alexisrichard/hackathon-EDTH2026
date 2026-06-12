"""MockDataSource — realistic synthetic data so the frontend works with no backend.

Assembles the scripted Eagle S fleet (``mock_scenario.py``) into the domain
models the API serves: tracks, time-sliced scored vessels, a criticality grid
with a hotspot over Estlink 2, ranked cues pointing at that hotspot, the demo
scenarios, and the real incident catalogue (read from
``data/reference/incidents.csv``).

This is the default data source (``DATA_SOURCE=mock``). Everything is a pure
function of the requested instant ``t`` so the demo re-ranks live as the clock
scrubs.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from app.core.display import band_for_score, color_for_suspicion, color_hex_for_suspicion, shape_for_ship_type
from app.data import mock_scenario as ms
from app.data.base import DataSource
from app.models.enums import SensorType
from app.models.geo import BBox, CriticalityGrid, CueRecommendation, GridCell
from app.models.scenario import Incident, Scenario
from app.models.scoring import DisplayHints, ScoreBreakdown, ScoredVessel
from app.models.vessel import VesselTrack

# data/reference/incidents.csv, resolved from repo root.
# backend/app/data/mock.py -> parents[3] == repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_INCIDENTS_CSV = _REPO_ROOT / "data" / "reference" / "incidents.csv"


def _in_bbox(lon: float, lat: float, bbox: BBox | None) -> bool:
    if bbox is None:
        return True
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _bboxes_overlap(a: BBox, b: BBox) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


class MockDataSource(DataSource):
    """Synthetic data source backed by the scripted Eagle S scenario."""

    name = "mock"

    def __init__(self) -> None:
        self._fleet = ms.build_mock_fleet()

    # -- helpers ------------------------------------------------------------------

    @staticmethod
    def _resolve_t(t: datetime | None) -> datetime:
        """Default to the demo instant; ensure tz-aware UTC."""
        if t is None:
            return ms.DEMO_INSTANT
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)

    @staticmethod
    def _display_for(ship_type, suspicion: float) -> DisplayHints:
        return DisplayHints(
            shape=shape_for_ship_type(ship_type),
            color=list(color_for_suspicion(suspicion)),
            color_hex=color_hex_for_suspicion(suspicion),
            band=band_for_score(suspicion),
        )

    def _scored_at(self, mv: ms.MockVessel, t: datetime) -> ScoredVessel:
        pos = mv.position_at(t)
        terms = mv.terms_at(t)
        breakdown = ScoreBreakdown(**terms)
        return ScoredVessel(
            vessel=mv.vessel,
            t=t,
            position=pos,
            breakdown=breakdown,
            display=self._display_for(mv.vessel.ship_type, breakdown.suspicion),
        )

    # -- DataSource API -----------------------------------------------------------

    def vessel_tracks(
        self,
        bbox: BBox | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[VesselTrack]:
        times = ms.track_times(start, end)
        out: list[VesselTrack] = []
        for mv in self._fleet[:limit]:
            positions = [mv.position_at(t) for t in times]
            if bbox is not None and not any(
                _in_bbox(p.lon, p.lat, bbox) for p in positions
            ):
                continue  # track never enters the requested bbox
            out.append(VesselTrack(vessel=mv.vessel, track=positions))
        return out

    def scores_at(
        self,
        t: datetime | None = None,
        bbox: BBox | None = None,
    ) -> list[ScoredVessel]:
        when = self._resolve_t(t)
        scored = [self._scored_at(mv, when) for mv in self._fleet]
        if bbox is not None:
            scored = [
                s for s in scored if _in_bbox(s.position.lon, s.position.lat, bbox)
            ]
        scored.sort(key=lambda s: s.suspicion, reverse=True)
        return scored

    def criticality_grid(
        self,
        t: datetime | None = None,
        bbox: BBox | None = None,
    ) -> CriticalityGrid:
        """A small synthetic grid over the gulf with a hotspot on Estlink 2.

        Built as a coarse lon/lat lattice (≈0.17° cells) over the demo bbox. Each
        cell's static ``criticality`` falls off with distance from the Estlink 2
        crossing; ``cue_score`` then blends that criticality with the max
        suspicion of any scored vessel currently inside the cell.
        """
        when = self._resolve_t(t)
        scored = self.scores_at(when)  # already sorted desc
        full = ms.DEMO_BBOX
        min_lon, min_lat, max_lon, max_lat = full
        nx, ny = 10, 6
        dx = (max_lon - min_lon) / nx
        dy = (max_lat - min_lat) / ny
        hot_lon, hot_lat = ms.ESTLINK2_CROSSING

        cells: list[GridCell] = []
        for r in range(ny):
            for c in range(nx):
                cell_min_lon = min_lon + c * dx
                cell_min_lat = min_lat + r * dy
                cell_bbox: BBox = (
                    round(cell_min_lon, 4),
                    round(cell_min_lat, 4),
                    round(cell_min_lon + dx, 4),
                    round(cell_min_lat + dy, 4),
                )
                if bbox is not None and not _bboxes_overlap(cell_bbox, bbox):
                    continue
                cx = cell_min_lon + dx / 2
                cy = cell_min_lat + dy / 2
                # Distance (deg) to the cable crossing -> criticality falloff.
                d = ((cx - hot_lon) ** 2 + (cy - hot_lat) ** 2) ** 0.5
                criticality = max(0.05, min(0.95, 0.95 * (1.0 - d / 0.9)))
                # In-cell vessel suspicion.
                drivers = [
                    s for s in scored if _in_bbox(s.position.lon, s.position.lat, cell_bbox)
                ]
                max_susp = max((s.suspicion for s in drivers), default=0.0)
                cue_score = round(min(1.0, 0.55 * criticality + 0.45 * max_susp + 0.4 * max_susp * criticality), 3)
                cells.append(
                    GridCell(
                        cell_id=f"r{r}c{c}",
                        bbox=cell_bbox,
                        h3=None,
                        criticality=round(criticality, 3),
                        cue_score=cue_score,
                        driver_mmsis=[s.vessel.mmsi for s in drivers],
                    )
                )
        return CriticalityGrid(t=when, bbox=full, cells=cells)

    def cues_at(
        self,
        t: datetime | None = None,
        top: int = 5,
        bbox: BBox | None = None,
    ) -> list[CueRecommendation]:
        when = self._resolve_t(t)
        grid = self.criticality_grid(when, bbox)
        scored_by_mmsi = {s.vessel.mmsi: s for s in self.scores_at(when)}
        ranked = sorted(grid.cells, key=lambda cell: cell.cue_score, reverse=True)
        ranked = [c for c in ranked if c.cue_score > 0.1][:top]

        cues: list[CueRecommendation] = []
        for i, cell in enumerate(ranked, start=1):
            # Sensor choice: a slow/loitering or AIS-dark driver -> SAR (all-weather,
            # sees dark vessels); otherwise an optical confirmation pass.
            drivers = [scored_by_mmsi[m] for m in cell.driver_mmsis if m in scored_by_mmsi]
            top_driver = max(drivers, key=lambda s: s.suspicion, default=None)
            sensor = SensorType.SAR if (top_driver and top_driver.suspicion >= 0.4) else SensorType.OPTICAL
            if top_driver is not None and top_driver.suspicion >= 0.2:
                why = (
                    f"{top_driver.vessel.name or top_driver.vessel.mmsi}: "
                    f"{top_driver.breakdown.why} Recommend a {sensor.value} pass."
                )
            else:
                why = (
                    f"High strategic criticality ({cell.criticality:.2f}); "
                    f"persistent watch recommended ({sensor.value})."
                )
            cues.append(
                CueRecommendation(
                    rank=i,
                    cell_id=cell.cell_id,
                    bbox=cell.bbox,
                    t=when,
                    sensor=sensor,
                    score=cell.cue_score,
                    driver_mmsis=cell.driver_mmsis,
                    why=why,
                )
            )
        return cues

    def scenarios(self) -> list[Scenario]:
        """The demo scenarios. Eagle S is the fully-fleshed hero; others reference
        the catalogue so the frontend can list them even before tracks exist."""
        return [
            Scenario(
                id="eagle-s-2024-12-25",
                name="Eagle S / Estlink 2",
                start=ms.DEMO_START,
                end=ms.DEMO_END,
                bbox=ms.DEMO_BBOX,
                suspect_mmsi=ms.SUSPECT_MMSI,
                incident_id="INC-2024-12-25",
                narrative=(
                    "Christmas Eve 2024: the tanker EAGLE S slows over Estlink 2, the "
                    "engine flags it and recommends a SAR pass on the crossing — the "
                    "cable is cut ~14 minutes later. Held out of training."
                ),
                held_out=True,
            ),
            Scenario(
                id="yi-peng-3-2024-11-17",
                name="Yi Peng 3 / BCS East-West + C-Lion1",
                start=datetime(2024, 11, 17, 0, 0, tzinfo=timezone.utc),
                end=datetime(2024, 11, 19, 0, 0, tzinfo=timezone.utc),
                bbox=(15.0, 54.8, 18.5, 56.0),
                suspect_mmsi=None,
                incident_id="INC-2024-11-17",
                narrative="Bulk carrier Yi Peng 3 cuts two cables on consecutive days south of Sweden.",
                held_out=False,
            ),
            Scenario(
                id="newnew-polar-bear-2023-10-08",
                name="Newnew Polar Bear / Balticconnector",
                start=datetime(2023, 10, 7, 0, 0, tzinfo=timezone.utc),
                end=datetime(2023, 10, 9, 0, 0, tzinfo=timezone.utc),
                bbox=(22.5, 59.4, 24.5, 60.3),
                suspect_mmsi=None,
                incident_id="INC-2023-10-08",
                narrative="Container ship drags anchor across the Balticconnector pipeline + telecom cables.",
                held_out=False,
            ),
        ]

    def incidents(self) -> list[Incident]:
        """Load the real catalogued incidents from data/reference/incidents.csv."""
        return load_incidents()

    def close(self) -> None:
        return None


def load_incidents() -> list[Incident]:
    """Parse ``data/reference/incidents.csv`` into :class:`Incident` models.

    Robust to a missing file (returns the bbox.py seed list instead) so the mock
    never hard-fails on a fresh / partial checkout.
    """
    if not _INCIDENTS_CSV.exists():
        return _incidents_from_bbox_seed()

    out: list[Incident] = []
    with _INCIDENTS_CSV.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                lat = float(row.get("lat_approx") or "nan")
                lon = float(row.get("lon_approx") or "nan")
            except ValueError:
                continue
            if lat != lat or lon != lon:  # NaN guard
                continue
            sources = [
                s.strip()
                for s in (row.get("sources") or "").replace(";", "\n").splitlines()
                if s.strip()
            ]
            out.append(
                Incident(
                    incident_id=row.get("incident_id") or row.get("name") or "INC-?",
                    name=row.get("name") or "Unknown incident",
                    date_utc=row.get("date_utc") or "",
                    time_utc=(row.get("time_utc") or None) or None,
                    lat=lat,
                    lon=lon,
                    vessel_name=_clean(row.get("vessel_name")),
                    vessel_flag=_clean(row.get("vessel_flag")),
                    vessel_type=_clean(row.get("vessel_type")),
                    infrastructure_name=_clean(row.get("infrastructure_name")),
                    infrastructure_type=_clean(row.get("infrastructure_type")),
                    region=_clean(row.get("region")),
                    attribution_status=_clean(row.get("attribution_status")),
                    narrative=_clean(row.get("notes")),
                    sources=sources,
                )
            )
    return out or _incidents_from_bbox_seed()


def _clean(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    if not v or v.lower() in {"unknown", "n/a", "na"}:
        return None
    return v


def _incidents_from_bbox_seed() -> list[Incident]:
    """Fallback incident list seeded from scripts/common/bbox.py INCIDENTS."""
    import app.core.paths  # noqa: F401  (repo root on sys.path)
    from scripts.common.bbox import INCIDENTS

    out: list[Incident] = []
    for date_str, name, lat, lon in INCIDENTS:
        out.append(
            Incident(
                incident_id=f"INC-{date_str}",
                name=name,
                date_utc=date_str,
                lat=lat,
                lon=lon,
            )
        )
    return out
