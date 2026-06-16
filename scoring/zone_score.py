"""Zone (cueing) score — THE product: rank ~50 km cells by collection priority.

The output is not "this vessel is suspicious"; it's "task your next sensor on this
box, here's why." Per ~50 km cell at instant t it carries two cue archetypes:

  vessel-driven  — ONE ship's  infra_proximity / vessel_risk / live_anomaly / sar
                   (its four sub-weights sum to 1, so a ship maxed on all → ~1.0)
  dark-density   — a SAR cluster with NO AIS (the Nord-Stream signature)

combined by noisy-OR so either can drive a cell and co-occurrence boosts. The
vessel terms shown all belong to the SINGLE worst ship in the cell, so the "why"
is truthful. Every term is in [0,1] and reported separately. Defensive collection
cue, point-in-time (no look-ahead), not a targeting recommendation.
"""
from __future__ import annotations

import glob
import json
import math
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Point

from scoring.behavioral import behavioral_history
from scoring.calibrate import class_relative
from scoring.sar_signals import dark_vessels as load_dark_vessels
from scoring.sar_signals import per_vessel as sar_per_vessel
from scoring.ship_trust import score_vessel_risk

ROOT = Path(__file__).resolve().parents[1]
TILES = ROOT / "frontend/public/data/ais_v2"
GRID_KM = 50.0


@lru_cache(maxsize=400)
def _tile_vessels(path: str):
    """Parsed vessels for one day-tile, CACHED — so repeated 90-day lookback scans
    (the live backend's hot path, and the time-series build) don't re-parse the
    same JSON tiles on every call. ~400 tiles ≈ the whole lookback window resident."""
    with open(path) as fh:
        return json.load(fh)["vessels"]


@lru_cache(maxsize=1)
def _tile_paths():
    return sorted(glob.glob(str(TILES / "tracks_*.json")))

KM_PER_DEG = 111.32
INFRA_RANGE_KM = 12.0  # within this, a vessel is "over" infrastructure

# A cell carries TWO independent cue archetypes, combined by noisy-OR so either
# can stand on its own and co-occurrence boosts (never dilutes):
#   1. vessel-driven  — one suspicious ship over infrastructure. Its four
#      sub-weights sum to 1, so a vessel maxed on all of them reaches ~1.0.
#   2. dark-density    — a SAR cluster with NO AIS (the Nord-Stream signature:
#      the suspect, if any, went dark). Scored on its own [0,1] scale.
VESSEL_W = {  # sum = 1.0
    "infra": 0.25,        # sitting on a cut-prone cable/pipeline
    "vessel_risk": 0.30,  # point-in-time ship-trust prior (behaviour + SAR)
    "live_anomaly": 0.20, # slow / dark right now
    "sar": 0.25,          # confirmed SAR dark-approach/blackout — the evasion signature
}
DARK_FULL = 10.0  # SAR dark contacts in a cell at which dark-density saturates to 1.0


def _epoch(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


def _fix_at(v, t):
    """Interpolated [lon,lat,sog,dark] for a vessel at t, or None."""
    kf = v["kf"]
    n = len(kf)
    if n == 0 or t < kf[0][0] or t > kf[-1][0]:
        return None
    lo, hi = 0, n - 1
    while hi - lo > 1:
        m = (lo + hi) >> 1
        lo, hi = (m, hi) if kf[m][0] <= t else (lo, m)
    a, b = kf[lo], kf[hi]
    dark = any(g0 < b[0] and g1 > a[0] for g0, g1 in v["gaps"])
    if dark or b[0] == a[0]:
        return [a[1], a[2], a[3], True]
    f = max(0.0, min(1.0, (t - a[0]) / (b[0] - a[0])))
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f, False]


def _cable_distance_fn():
    """Returns dist_km(lon,lat) to the nearest cable/pipeline (the cut-prone infra)."""
    geoms = []
    for name in ("submarine_cables", "pipelines"):
        p = ROOT / "data/geo" / f"{name}.geojson"
        if p.exists():
            geoms.append(gpd.read_file(p).to_crs(3035))
    if not geoms:
        return lambda lon, lat: math.inf
    union = gpd.GeoSeries(
        [g for gs in geoms for g in gs.geometry], crs=3035
    ).union_all()

    def dist(lon, lat):
        pt = gpd.GeoSeries([Point(lon, lat)], crs=4326).to_crs(3035).iloc[0]
        return pt.distance(union) / 1000.0

    return dist


def build_theatre(at_ts: int, as_of_date: str, bbox, lookback: int = 90):
    """Vessels present at `at_ts` inside bbox, each with position, live anomaly, and
    point-in-time ship-trust risk (class-relative behaviour + SAR)."""
    cut_tile = TILES / f"tracks_{as_of_date}.json"
    if not cut_tile.exists():
        return []
    vessels = _tile_vessels(str(cut_tile))
    lon0, lat0, lon1, lat1 = bbox

    here = {}  # mmsi -> (fix, type, name)
    for v in vessels:
        fx = _fix_at(v, at_ts)
        if fx and lon0 <= fx[0] <= lon1 and lat0 <= fx[1] <= lat1:
            here[v["mmsi"]] = (fx, v["type"], v.get("name"))
    if not here:
        return []

    # prior history for risk (scan the lookback window once)
    start = (date.fromisoformat(as_of_date) - timedelta(days=lookback)).isoformat()
    prior = defaultdict(list)
    for f in _tile_paths():
        d = os.path.basename(f)[len("tracks_") : -len(".json")]
        if d < start or d >= as_of_date:
            continue
        for v in _tile_vessels(f):
            if v["mmsi"] in here:
                prior[v["mmsi"]].append({"date": d, "kf": v["kf"], "gaps": v["gaps"]})

    rows = []
    for mmsi, (fx, typ, name) in here.items():
        bh = behavioral_history(prior.get(mmsi, []), as_of=as_of_date)
        rows.append({"mmsi": mmsi, "type": typ, "components": bh.get("components", {}),
                     "available": bh["available"], "known_through": bh.get("known_through"),
                     "prior_days": len(prior.get(mmsi, []))})
    class_relative(rows)

    sar = sar_per_vessel()
    # No-look-ahead at the SNAPSHOT instant (not just the day): a satellite tasked
    # at 12:00 may use a SAR signal that landed at 11:00, but not one at 13:00. The
    # behavioural prior stays day-granular (tiles strictly before as_of_date).
    as_of_ts = datetime.fromtimestamp(at_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    theatre = []
    for r in rows:
        mmsi = r["mmsi"]
        fx, typ, name = here[mmsi]
        bh_in = ({"available": True, "known_through": r["known_through"],
                  "value": r["class_risk"], "components": r["components"]}
                 if r["available"] else {"available": False})
        scored = score_vessel_risk({
            "vessel_id": f"MMSI:{mmsi}", "vessel_name": name, "is_synthetic": False,
            "as_of": as_of_ts, "behavioral_history": bh_in,
            "identity_risk": {"available": False}, "watchlist": [],
            "sar_signals": sar.get(mmsi, []),
        })
        # live anomaly: slow (≤2 kn) and/or dark, right now
        sog, dark = fx[2], fx[3]
        live = max(1.0 if sog <= 2.0 else (0.5 if sog <= 5.0 else 0.0), 0.7 if dark else 0.0)
        theatre.append({
            "mmsi": mmsi, "name": name, "type": typ, "lon": round(fx[0], 5), "lat": round(fx[1], 5),
            "sog": round(sog, 2), "dark": bool(dark),
            "vessel_risk": scored["risk"], "sar": scored["sar_mismatch"],
            "live_anomaly": round(live, 3),
            # compact, interpretable breakdown for the webapp's click-to-inspect panel
            "breakdown": {"risk": scored["risk"], "trust": scored["trust"],
                          "confidence": scored["confidence"],
                          "contributions": scored["contributions"],
                          "sar_mismatch": scored["sar_mismatch"],
                          "prior_days": r["prior_days"],
                          "explanation": scored["explanation"]},
        })
    return theatre


def _cell(lon, lat):
    """Stable ~GRID_KM grid. lon_step is fixed per latitude-band (from the band
    centre), not per point, so a row's columns are a clean partition and a cell's
    bbox is deterministic regardless of which vessel created it first."""
    lat_step = GRID_KM / KM_PER_DEG
    ci = math.floor(lat / lat_step)
    band_lat = (ci + 0.5) * lat_step  # one reference latitude for the whole row
    lon_step = GRID_KM / (KM_PER_DEG * math.cos(math.radians(band_lat)))
    cj = math.floor(lon / lon_step)
    return (ci, cj), [round(cj * lon_step, 4), round(ci * lat_step, 4),
                      round((cj + 1) * lon_step, 4), round((ci + 1) * lat_step, 4)]


def _vessel_score(rec):
    return (VESSEL_W["infra"] * rec["infra_proximity"]
            + VESSEL_W["vessel_risk"] * rec["vessel_risk"]
            + VESSEL_W["live_anomaly"] * rec["live_anomaly"]
            + VESSEL_W["sar"] * rec["sar"])


def _why(best, dark_count, dark_score, vessel_best):
    """Honest one-liner. Dark density narrates only when it dominates the cell;
    otherwise the single worst vessel and its leading reasons (all truthful to
    that one ship — never a Frankenstein of different vessels' terms)."""
    if best is None or dark_score >= vessel_best:
        if dark_count:
            return f"{dark_count} dark SAR contacts, no AIS — a suspect that went dark"
        return "no AIS vessel present"
    reasons = []
    if best["sar"] > 0:
        reasons.append("SAR dark-approach/blackout")
    if best["live_anomaly"] >= 0.5:
        reasons.append("loitering/slow now")
    if best["vessel_risk"] >= 0.5:
        reasons.append("anomalous track record")
    if best["infra_proximity"] > 0.3:
        reasons.append("over a cable")
    lead = best["name"] or f"MMSI {best['mmsi']}"
    return f"{lead}: " + (", ".join(reasons[:3]) if reasons else "present over infrastructure")


def rank_cues(theatre, dark_vessels, cable_dist, top_n=5, sensor="SAR"):
    """Aggregate per cell and rank. A cell's *vessel* score comes from its SINGLE
    worst ship (one vessel's proximity x importance, risk, live anomaly, SAR —
    never a max stitched across different ships, which would lie about *why*).
    A separate dark-density score captures no-AIS SAR clusters. The two combine
    by noisy-OR: ``1 - (1-vessel)(1-dark)`` — either can drive the cell, and a
    suspicious ship sitting amid dark contacts scores higher than either alone."""
    cells = {}

    def _get(key, bbox):
        c = cells.get(key)
        if c is None:
            c = cells[key] = {"bbox": bbox, "best": None, "best_score": 0.0,
                              "dark": 0, "vessels": []}
        elif c["bbox"] is None:
            c["bbox"] = bbox
        return c

    for v in theatre:
        key, bbox = _cell(v["lon"], v["lat"])
        c = _get(key, bbox)
        prox = max(0.0, 1.0 - cable_dist(v["lon"], v["lat"]) / INFRA_RANGE_KM)
        rec = {"name": v["name"], "mmsi": v["mmsi"], "type": v["type"],
               "infra_proximity": round(prox, 3), "vessel_risk": round(v["vessel_risk"], 3),
               "live_anomaly": round(v["live_anomaly"], 3), "sar": round(v.get("sar", 0.0), 3)}
        rec["vessel_score"] = round(_vessel_score(rec), 4)
        c["vessels"].append(rec)
        if rec["vessel_score"] > c["best_score"]:
            c["best_score"], c["best"] = rec["vessel_score"], rec
    for dv in dark_vessels:
        key, bbox = _cell(dv["lon"], dv["lat"])
        _get(key, bbox)["dark"] += 1

    out = []
    for c in cells.values():
        dark_score = min(1.0, c["dark"] / DARK_FULL)
        vessel_best = c["best_score"]
        score = 1.0 - (1.0 - vessel_best) * (1.0 - dark_score)  # noisy-OR
        best = c["best"]
        # When dark density drives the cell, the AIS vessels present are NOT the
        # cue: zero their terms and drivers so the panel matches the "no AIS
        # suspect" narrative (the dark contacts, not a ship, are the reason).
        dark_drives = dark_score >= vessel_best
        drivers = [] if dark_drives else sorted(c["vessels"], key=lambda d: -d["vessel_score"])[:3]
        vt = (lambda k: 0.0) if (dark_drives or not best) else (lambda k: best[k])
        out.append({
            "bbox": c["bbox"], "score": round(score, 4), "sensor": sensor,
            "terms": {"infra": vt("infra_proximity"), "vessel_risk": vt("vessel_risk"),
                      "live_anomaly": vt("live_anomaly"), "sar": vt("sar"),
                      "dark_density": round(dark_score, 3)},
            "drivers": drivers, "dark_contacts": c["dark"],
            "why": _why(best, c["dark"], dark_score, vessel_best),
            "disclaimer": "Defensive collection cue; not for targeting.",
        })
    out.sort(key=lambda o: (-o["score"], -o["dark_contacts"]))
    for i, o in enumerate(out[:top_n], 1):
        o["rank"] = i
    return out[:top_n]


def _signal_epoch(s):
    try:
        if not s or not str(s).strip():
            return None
        s = str(s).strip()
        return _epoch(s if "T" in s else s + "T00:00:00Z")
    except ValueError:
        return None  # unparseable date → treated as "unknown" → fail-closed below


def filter_dark_no_lookahead(rows, incident, at_ts):
    """Keep only this incident's dark contacts whose acquisition time is known and
    <= at_ts. Fail-CLOSED: a missing/unparseable signal_date is dropped, never
    admitted. Returns (kept, dropped_count)."""
    kept, dropped = [], 0
    for d in rows:
        if d.get("incident_id") != incident:
            continue
        ep = _signal_epoch(d.get("signal_date"))
        if ep is None or ep > at_ts:
            dropped += 1
            continue
        kept.append(d)
    return kept, dropped


# The two demo cues, as data. `at` is the evaluation instant (no look-ahead past
# it); `dark_incident` selects which SAR dark cluster (if any) is in play.
SCENARIOS = [
    {"id": "c-lion1", "label": "C-Lion1 / Yi Peng 3", "sensor": "SAR",
     "as_of": "2024-11-18", "at": "2024-11-18T08:41:00Z",
     "bbox": (12.0, 53.5, 22.0, 60.0), "dark_incident": "INC-2024-11-18",
     "hero_mmsi": 414270000,
     "blurb": "Vessel-driven cue: a dark-approach contact loitering over the cable.",
     # Continuous tasking: re-task N satellites every `cadence_h` hours over the
     # lead-up window. The 3h cadence catches the 08:00-10:00 Yi Peng 3 action that
     # a 12h cadence brackets (the ship is dark until 08:00, moving away by 12:00).
     "timeseries": {"start": "2024-11-17T00:00:00Z", "end": "2024-11-18T21:00:00Z",
                    "cadence_h": 3, "n_sat": 3}},
    {"id": "nord-stream", "label": "Nord Stream", "sensor": "SAR",
     "as_of": "2022-09-26", "at": "2022-09-26T06:00:00Z",
     "bbox": (13.0, 54.0, 18.0, 57.0), "dark_incident": "INC-2022-09-26",
     "hero_mmsi": None,
     "blurb": "Dark-density cue: SAR contacts with no AIS — the suspect went dark."},
]


def compute_scenario(scn: dict, cable_dist=None) -> dict:
    """Full structured payload for one demo cue: ranked queue, the dark-contact
    points, and the in-theatre per-vessel risk breakdowns. Point-in-time."""
    cable_dist = cable_dist or _cable_distance_fn()
    at_ts = _epoch(scn["at"])
    theatre = build_theatre(at_ts, scn["as_of"], scn["bbox"])
    # No look-ahead on the zone, fail-CLOSED: a SAR dark contact cues us only once
    # its acquisition time has passed. A missing/unparseable signal_date is dropped
    # (never admitted by default) — same guarantee the per-vessel SAR path enforces.
    dark, dropped = filter_dark_no_lookahead(
        load_dark_vessels(), scn["dark_incident"], at_ts)
    cues = rank_cues(theatre, dark, cable_dist, top_n=5, sensor=scn["sensor"])
    return {
        "id": scn["id"], "label": scn["label"], "blurb": scn["blurb"],
        "as_of": scn["as_of"], "at": scn["at"], "at_ts": at_ts,
        "bbox": list(scn["bbox"]), "sensor": scn["sensor"],
        "hero_mmsi": scn["hero_mmsi"],
        "cues": cues,
        "dark_contacts": [{"lon": d["lon"], "lat": d["lat"],
                           "confidence": d.get("sar_confidence")} for d in dark],
        "dark_contacts_excluded_future": dropped,
        "theatre": theatre,
        "disclaimer": "Defensive collection cue; not for targeting.",
    }


def compute_timeseries(scn: dict, cable_dist=None) -> dict:
    """Per-scenario time-series of satellite taskings at a fixed cadence — the
    CONTINUOUS engine. Each snapshot scores the theatre AS-OF that instant (no
    look-ahead) and tasks the top `n_sat` cells. So the fleet is scored throughout
    the lead-up and N satellites re-task every `cadence_h` hours, catching the hero
    the moment it acts, instead of one magic cue popping in at the incident."""
    cable_dist = cable_dist or _cable_distance_fn()
    cfg = scn["timeseries"]
    step = cfg["cadence_h"] * 3600
    t, end = _epoch(cfg["start"]), _epoch(cfg["end"])
    snaps = []
    while t <= end:
        d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
        theatre = build_theatre(t, d, scn["bbox"])
        dark, _ = filter_dark_no_lookahead(load_dark_vessels(), scn["dark_incident"], t)
        taskings = rank_cues(theatre, dark, cable_dist, top_n=cfg["n_sat"], sensor=scn["sensor"])
        risk = {v["mmsi"]: {"name": v["name"], "type": v["type"], "risk": v["vessel_risk"],
                            "sar": v["sar"], "live": v["live_anomaly"],
                            "confidence": v["breakdown"]["confidence"],
                            "prior_days": v["breakdown"]["prior_days"],
                            "contributions": v["breakdown"]["contributions"],
                            "explanation": v["breakdown"]["explanation"]}
                for v in theatre}
        snaps.append({"at": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "at_ts": t, "dark_contacts": len(dark), "taskings": taskings, "risk": risk})
        t += step
    caught = next((s["at"] for s in snaps if scn["hero_mmsi"] and
                   any(any(dr["mmsi"] == scn["hero_mmsi"] for dr in tk["drivers"])
                       for tk in s["taskings"])), None)
    return {"id": scn["id"], "label": scn["label"], "sensor": scn["sensor"],
            "bbox": list(scn["bbox"]), "hero_mmsi": scn["hero_mmsi"],
            "cadence_h": cfg["cadence_h"], "n_sat": cfg["n_sat"],
            "window": [cfg["start"], cfg["end"]], "hero_caught_at": caught,
            "snapshots": snaps}


def _print(payload: dict) -> None:
    print(f"\n=== TASK-NEXT QUEUE — {payload['label']} ({payload['at']}) ===  "
          f"theatre={len(payload['theatre'])} vessels, {len(payload['dark_contacts'])} dark SAR contacts")
    for o in payload["cues"]:
        print(f"  #{o['rank']}  score {o['score']:.3f} [{o['sensor']}]  {o['why']}")
        print(f"       terms {o['terms']}")
    if payload["hero_mmsi"]:
        yp = [v for v in payload["theatre"] if v["mmsi"] == payload["hero_mmsi"]]
        if yp:
            v = yp[0]
            print(f"   -> hero {v['name']}: vessel_risk {v['vessel_risk']}, sar {v['sar']}, "
                  f"live {v['live_anomaly']}, pos {v['lon']:.2f},{v['lat']:.2f}")


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emit", metavar="DIR", default=None,
                    help="write <id>.json per scenario + index.json into DIR (for the webapp)")
    args = ap.parse_args(argv)

    cable_dist = _cable_distance_fn()
    payloads, series = [], {}
    for scn in SCENARIOS:
        payload = compute_scenario(scn, cable_dist)
        _print(payload)
        payloads.append(payload)
        if "timeseries" in scn:
            ts = compute_timeseries(scn, cable_dist)
            series[scn["id"]] = ts
            print(f"   time-series: {len(ts['snapshots'])} snapshots @ {ts['cadence_h']}h × {ts['n_sat']} sats"
                  f" — hero first tasked at {ts['hero_caught_at'] or 'NEVER'}")

    if args.emit:
        out_dir = Path(args.emit)
        out_dir.mkdir(parents=True, exist_ok=True)
        index = []
        for p in payloads:
            json.dump(p, open(out_dir / f"{p['id']}.json", "w"))
            index.append({"id": p["id"], "label": p["label"], "blurb": p["blurb"],
                          "as_of": p["as_of"], "at": p["at"], "bbox": p["bbox"],
                          "hero_mmsi": p["hero_mmsi"],
                          "has_timeseries": p["id"] in series,
                          "top_cue": p["cues"][0] if p["cues"] else None})
        for sid, ts in series.items():
            json.dump(ts, open(out_dir / f"{sid}-timeseries.json", "w"))
        json.dump({"scenarios": index}, open(out_dir / "index.json", "w"), indent=1)
        print(f"\nwrote {len(payloads)} scenario(s) + {len(series)} time-series + index.json -> {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
