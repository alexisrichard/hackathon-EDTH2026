"""Fleet-wide vessel-risk distribution as-of a date — the no-overfitting check.

Scores *every* vessel in the theatre on the cut day using ONLY its behavioural
prior (day-records strictly before the cut), with the same rules and constants
for all — no per-vessel tuning. A transparent rule engine can't memorise the
hero; the only honest test is whether known incident vessels sit in the tail
while the mass of ordinary traffic sits low.

This scores the behavioural PRIOR alone (identity/watchlist empty, cable
proximity omitted for speed) — it deliberately does NOT include the live
in-incident manoeuvre (that is the `unusual_movement` factor in the cue score)
or the SAR mismatch signal. So it answers a precise question: *how discriminative
is a vessel's track record by itself?*

Usage:
  python -m scoring.validate_fleet --as-of 2024-11-18 --lookback 90
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import defaultdict
from datetime import date, timedelta

from scoring.behavioral import behavioral_history
from scoring.calibrate import class_relative, percentile
from scoring.sar_signals import per_vessel as sar_per_vessel
from scoring.ship_trust import score_vessel_risk

DEFAULT_TILES = "frontend/public/data/ais_v2"

# Known Baltic incident vessels, for the generalisation check (do they rank high?).
KNOWN_INCIDENT = {
    414270000: "Yi Peng 3 (C-Lion1)",
    229659000: "Vezhen (BCS)",
    353125000: "Newnew Polar Bear",
}


def _tile_date(path: str) -> str:
    return os.path.basename(path)[len("tracks_") : -len(".json")]




def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", default="2024-11-18", help="cut date YYYY-MM-DD")
    ap.add_argument("--lookback", type=int, default=90, help="prior-history window (days)")
    ap.add_argument("--tiles-dir", default=DEFAULT_TILES)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--out", default="scoring/fleet_validation.json")
    args = ap.parse_args(argv)

    cut = args.as_of
    start = (date.fromisoformat(cut) - timedelta(days=args.lookback)).isoformat()
    as_of_ts = f"{cut}T00:00:00Z"

    cut_path = os.path.join(args.tiles_dir, f"tracks_{cut}.json")
    if not os.path.exists(cut_path):
        ap.error(f"no cut-day tile: {cut_path}")
    targets = {
        v["mmsi"]: {"name": v.get("name"), "type": v.get("type", "unknown")}
        for v in json.load(open(cut_path))["vessels"]
    }

    # One pass over the prior window, bucketing each target's day-records.
    prior: dict[int, list[dict]] = defaultdict(list)
    files = sorted(glob.glob(os.path.join(args.tiles_dir, "tracks_*.json")))
    scanned = 0
    for f in files:
        d = _tile_date(f)
        if d < start or d >= cut:
            continue
        scanned += 1
        for v in json.load(open(f))["vessels"]:
            if v["mmsi"] in targets:
                prior[v["mmsi"]].append({"date": d, "kf": v["kf"], "gaps": v["gaps"]})

    sar = sar_per_vessel()  # Signal Brick: per-vessel dark approaches / blackouts

    # Pass 1 — raw behavioural features per vessel (needed for the class baselines).
    rows = []
    for mmsi, meta in targets.items():
        days = prior.get(mmsi, [])
        bh = behavioral_history(days, as_of=cut)  # no geo predicate (speed)
        rows.append(
            {
                "mmsi": mmsi,
                "name": meta["name"],
                "type": meta["type"],
                "prior_days": len(days),
                "components": bh.get("components", {}),
                "available": bh["available"],
                "known_through": bh.get("known_through"),
            }
        )

    # Calibrate: the raw composite is too hot (a fishing boat loitering like other
    # fishing boats reads as anomalous). Class-relative deviation fixes that — this
    # becomes the behavioural value the risk engine consumes.
    class_relative(rows)

    # Pass 2 — risk from class-relative behaviour + SAR mismatch (point-in-time).
    for r in rows:
        bh_input = (
            {"available": True, "known_through": r["known_through"],
             "value": r["class_risk"], "components": r["components"]}
            if r["available"] else {"available": False}
        )
        scored = score_vessel_risk(
            {
                "vessel_id": f"MMSI:{r['mmsi']}",
                "vessel_name": r["name"],
                "is_synthetic": False,
                "as_of": as_of_ts,
                "behavioral_history": bh_input,
                "identity_risk": {"available": False},
                "watchlist": [],
                "sar_signals": sar.get(r["mmsi"], []),
            }
        )
        r["risk"] = scored["risk"]

    rows.sort(key=lambda r: (-r["risk"], r["mmsi"]))
    risks_asc = sorted(r["risk"] for r in rows)
    n = len(rows)
    with_prior = sum(1 for r in rows if r["prior_days"] > 0)

    print(f"=== Fleet vessel-risk (behavioural prior only) as-of {cut} ===")
    print(f"window {start} → {cut} ({scanned} day-tiles) | {n} vessels | {with_prior} with prior history\n")
    print("distribution (risk percentiles):")
    for q in (0.50, 0.75, 0.90, 0.95, 0.99):
        print(f"  p{int(q*100):>2} = {percentile(risks_asc, q):.3f}")
    print(f"  max = {risks_asc[-1]:.3f}\n")

    print(f"top {args.top} by risk:")
    for i, r in enumerate(rows[: args.top], 1):
        flag = "  <<< INCIDENT" if r["mmsi"] in KNOWN_INCIDENT else ""
        c = r["components"]
        why = f"dark={c.get('dark_events',0)} loiter={c.get('loiter',0)} kin={c.get('kinematics',0)} days={r['prior_days']}"
        print(f"  {i:>2}. {r['risk']:.3f}  {str(r['name'])[:22]:<22} ({why}){flag}")

    print("\nknown incident vessels in the theatre:")
    for r in rows:
        if r["mmsi"] in KNOWN_INCIDENT:
            rank = rows.index(r) + 1
            print(
                f"  {KNOWN_INCIDENT[r['mmsi']]}: risk {r['risk']:.3f}, "
                f"rank {rank}/{n} (top {100*rank/n:.1f}%), prior_days {r['prior_days']}"
            )

    # ---- class-relative experiment: is "extreme for your class" more discriminative? ----
    crel = sorted(rows, key=lambda r: (-r["class_risk"], r["mmsi"]))
    crel_asc = sorted(r["class_risk"] for r in rows)
    print("\n=== CLASS-RELATIVE risk (experiment: deviation within ship class) ===")
    print("distribution:", "  ".join(f"p{int(q*100)}={percentile(crel_asc,q):.3f}" for q in (0.5, 0.9, 0.95, 0.99)))
    print(f"top {args.top} by class-relative risk:")
    for i, r in enumerate(crel[: args.top], 1):
        flag = "  <<< INCIDENT" if r["mmsi"] in KNOWN_INCIDENT else ""
        print(f"  {i:>2}. {r['class_risk']:.3f}  [{r['type'][:8]:<8}] {str(r['name'])[:22]:<22}{flag}")
    for r in crel:
        if r["mmsi"] in KNOWN_INCIDENT:
            rank = crel.index(r) + 1
            print(f"  -> {KNOWN_INCIDENT[r['mmsi']]}: class_risk {r['class_risk']:.3f}, rank {rank}/{n} (top {100*rank/n:.1f}%)")

    json.dump(
        {"as_of": cut, "window_start": start, "n": n, "rows": rows[: max(args.top, 50)]},
        open(args.out, "w"),
        indent=1,
    )
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
