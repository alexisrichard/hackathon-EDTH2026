"""Stitch the per-day AIS tiles into clean, self-aligned tiles — once, at build.

The per-day tiles (`build_ais_tracks.py`) are processed in isolation: a vessel's
track is cut at midnight, gaps are detected per-day, and no keyframe sits at the
boundary. So each tile is an island the *app* has to rejoin at runtime, and every
rejoin heuristic leaks at the seam (the midnight-discontinuity saga).

This fixes it at the source. For each vessel we rebuild a continuous track, detect
gaps globally, and — crucially — insert an interpolated keyframe at *exactly* each
midnight the vessel crosses, so adjacent day-tiles share the seam point. Then the
app renders one tile with zero stitching and is continuous by construction.

It also drops static fixtures (AtoN, base stations, permanently-moored) — ~1/5 of
"vessels", pure clutter for a movement-cueing tool and the source of the
near-midnight blips — and records them for transparency.

Memory-bounded: a per-MMSI bbox pre-pass (tiny) for the static filter, then a
sliding 3-day window (D-1, D, D+1) — only what's needed for day-D's two seams and
its cross-boundary gaps.

Usage:
  python scripts/ingest/stitch_tracks.py                       # full archive
  python scripts/ingest/stitch_tracks.py --start 2024-11-15 --end 2024-11-21
Output: <out>/tracks_<date>.json  (default frontend/public/data/ais_v2/)
        data/reference/dropped_static_reporters.csv
"""
from __future__ import annotations

import argparse
import bisect
import csv
import glob
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

# Generic AIS classes carry no real class info — a vessel that ever broadcasts a
# specific type should keep it on every tile (see canonical_types).
_GENERIC_TYPES = {None, "", "other", "unknown"}

ROOT = Path(__file__).resolve().parents[2]
GAP_SECONDS = 600          # >10 min with no ping = a gap (matches build_ais_tracks)
MAX_KNOTS = 60.0           # above this a segment is a bad fix / MMSI collision
KM_PER_NM = 1.852
DAY = 86400


def _hav_km(lon0, lat0, lon1, lat1):
    R, rad = 6371.0, math.pi / 180
    dlat = (lat1 - lat0) * rad
    dlon = (lon1 - lon0) * rad
    h = math.sin(dlat / 2) ** 2 + math.cos(lat0 * rad) * math.cos(lat1 * rad) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _implied_kn(a, b):
    dt_h = (b[0] - a[0]) / 3600
    if dt_h <= 0:
        return math.inf
    return _hav_km(a[1], a[2], b[1], b[2]) / dt_h / KM_PER_NM


def _despike(kf):
    if len(kf) < 3:
        return kf
    out = [kf[0]]
    for i in range(1, len(kf) - 1):
        a, b, c = out[-1], kf[i], kf[i + 1]
        if _implied_kn(a, b) > MAX_KNOTS and _implied_kn(b, c) > MAX_KNOTS:
            continue
        out.append(b)
    out.append(kf[-1])
    return out


def _date_of(path):
    return os.path.basename(path)[len("tracks_") : -len(".json")]


# ---- static-reporter pre-pass -------------------------------------------------

def static_filter(files, static_km):
    """One cheap pass over the whole archive. Returns (dropped, canonical_type).

    - dropped: MMSIs to drop (static installations), with a transparency record.
      A vessel whose entire archive footprint fits in a tiny box is a fixed
      installation, not a moving vessel.
    - canonical_type: one stable class per MMSI. AIS broadcasts the type field
      intermittently, so build_ais_tracks classed the same vessel "cargo" one day
      and "unknown"/"other" the next — which made it flip in/out of the vessel-
      class filter at every midnight (the fleet-thinning bug). We pin the type to
      the most-common SPECIFIC class the vessel ever broadcasts, archive-wide.
    """
    bbox = {}
    meta = {}
    type_votes = defaultdict(Counter)
    for f in files:
        for v in json.load(open(f))["vessels"]:
            m = v["mmsi"]
            if not v["kf"]:
                continue
            type_votes[m][v.get("type")] += 1
            b = bbox.get(m)
            for k in v["kf"]:
                lo, la = k[1], k[2]
                if b is None:
                    b = [lo, lo, la, la, 0]
                    bbox[m] = b
                    meta[m] = (v.get("name"), v.get("type"))
                b[0] = min(b[0], lo); b[1] = max(b[1], lo)
                b[2] = min(b[2], la); b[3] = max(b[3], la)
                b[4] += 1

    canonical_type = {}
    for m, votes in type_votes.items():
        specific = Counter({t: n for t, n in votes.items() if t not in _GENERIC_TYPES})
        canonical_type[m] = (specific or votes).most_common(1)[0][0]

    dropped = {}
    for m, b in bbox.items():
        span_km = max(
            (b[1] - b[0]) * 111.32 * math.cos(math.radians(b[2])),
            (b[3] - b[2]) * 111.32,
        )
        reason = None
        if span_km < static_km:
            reason = "stationary"
        elif 990000000 <= m <= 999999999:
            reason = "aton"
        elif m < 100000000:
            reason = "base_station"
        if reason:
            dropped[m] = (reason, round(span_km, 3), b[4], meta[m][0], meta[m][1])
    return dropped, canonical_type


# ---- seam keyframes -----------------------------------------------------------

def _fix_at(kf, gaps, t):
    """Position [lon,lat,sog,cog] at instant t on a continuous track, or None if t
    is outside it. Interpolates across a real segment; holds the last fix only when
    a REAL gap overlaps (a DP-straight leg has a long delta but no gap → interpolate,
    not freeze). `gaps` are the source pre-DP gaps, not keyframe deltas."""
    n = len(kf)
    if n == 0 or t < kf[0][0] or t > kf[-1][0]:
        return None
    lo, hi = 0, n - 1
    while hi - lo > 1:
        mid = (lo + hi) >> 1
        if kf[mid][0] <= t:
            lo = mid
        else:
            hi = mid
    a, b = kf[lo], kf[hi]
    if a[0] == t:
        return [a[1], a[2], a[3], a[4]]
    span = b[0] - a[0]
    in_gap = any(g0 < b[0] and g1 > a[0] for g0, g1 in gaps)
    if in_gap or span <= 0:        # dark crossing → frozen at last fix
        return [a[1], a[2], a[3], a[4]]
    f = (t - a[0]) / span
    return [a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f,
            a[3] + (b[3] - a[3]) * f, a[4]]


# ---- gap-end (reacquisition) keyframes ---------------------------------------

def insert_reacq(kf, gaps):
    """Insert a keyframe at each gap END, positioned at the next surviving fix.

    Upstream DP-simplification drops the reacquisition ping (and, for a vessel that
    parks after a gap, every post-gap ping is collinear and collapses too). That
    leaves a single bracket spanning the gap AND the long sparse tail, so the
    renderer freezes the vessel at its PRE-gap position for hours, then snaps it to
    the next keyframe — the midnight-teleport bug (the seam guarantees that next
    keyframe lands at 00:00). Anchoring the gap end to where the vessel is next
    actually seen makes the freeze release at the real reacquisition (faded), with
    no movement afterwards, instead of holding stale and snapping at the seam.
    """
    if not kf or not gaps:
        return kf
    times = [k[0] for k in kf]
    have = set(times)
    extra = []
    for g0, g1 in gaps:
        if g1 in have:
            continue
        i = bisect.bisect_left(times, g1)
        if i >= len(kf):
            continue  # gap end is past the whole track — nothing to anchor to
        nxt = kf[i]   # the next position we actually observe
        extra.append([g1, nxt[1], nxt[2], nxt[3], nxt[4]])
        have.add(g1)
    if not extra:
        return kf
    return sorted(kf + extra, key=lambda k: k[0])


# ---- main stitch --------------------------------------------------------------

def stitch_day(combined, combined_gaps, start_m):
    """Given a vessel's de-spiked combined kf over [D-1,D,D+1] (sorted), the real
    source gaps over the same window, and day-D's midnight `start_m`, return
    (kf, gaps) clipped to [start_m, start_m+DAY] with seam keyframes at both
    midnights when the vessel crosses them."""
    end_m = start_m + DAY
    # Re-de-spike the COMBINED track. Per-tile de-spiking always keeps each tile's
    # first/last keyframe, so an MMSI-collision spike sitting at a day edge slips
    # through and lands mid-track once neighbouring tiles are concatenated — a
    # huge cross-midnight teleport (the renderer even freezes ON the spike via its
    # implied-speed check). Now interior, the spike gets removed.
    combined = _despike(combined)
    # Anchor each gap end to the next observed fix BEFORE seams/clip, so the
    # renderer can't freeze the vessel at a stale pre-gap position past midnight.
    combined = insert_reacq(combined, combined_gaps)
    out = []
    # start seam
    if combined[0][0] < start_m < combined[-1][0]:
        p = _fix_at(combined, combined_gaps, start_m)
        if p:
            out.append([start_m, round(p[0], 5), round(p[1], 5), round(p[2], 1), round(p[3])])
    out.extend(k for k in combined if start_m < k[0] < end_m)
    # end seam
    if combined[0][0] < end_m < combined[-1][0]:
        p = _fix_at(combined, combined_gaps, end_m)
        if p:
            out.append([end_m, round(p[0], 5), round(p[1], 5), round(p[2], 1), round(p[3])])
    if not out:
        return None, None
    # Carry the REAL gaps (detected pre-DP in the source tiles), clipped to the day.
    # Recomputing from keyframe deltas would label every DP-straight steaming leg a
    # gap — phantom "AIS-dark" that poisons the suspicion score.
    gaps = []
    for g0, g1 in combined_gaps:
        c0, c1 = max(g0, start_m), min(g1, end_m)
        if c1 > c0:
            gaps.append([c0, c1])
    gaps.sort()
    return out, gaps


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tiles-dir", default=str(ROOT / "frontend/public/data/ais"))
    ap.add_argument("--out", default=str(ROOT / "frontend/public/data/ais_v2"))
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--static-km", type=float, default=0.2)  # only true fixtures; keep slow/anchored real vessels
    args = ap.parse_args(argv)

    files = sorted(glob.glob(os.path.join(args.tiles_dir, "tracks_*.json")))
    if not files:
        ap.error(f"no tiles in {args.tiles_dir}")

    print(f"[1/2] static-reporter pre-pass over {len(files)} tiles…")
    dropped, canon = static_filter(files, args.static_km)
    drop_path = ROOT / "data/reference/dropped_static_reporters.csv"
    drop_path.parent.mkdir(parents=True, exist_ok=True)
    with open(drop_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["mmsi", "reason", "span_km", "ping_count", "name", "type"])
        for m, (reason, span, n, name, typ) in sorted(dropped.items()):
            w.writerow([m, reason, span, n, name, typ])
    print(f"      dropping {len(dropped)} static reporters → {drop_path.name}")

    os.makedirs(args.out, exist_ok=True)
    by_date = {_date_of(f): f for f in files}
    dates = sorted(by_date)
    if args.start:
        dates = [d for d in dates if d >= args.start]
    if args.end:
        dates = [d for d in dates if d <= args.end]

    cache = {}  # date -> {mmsi: vessel} of de-spiked, non-dropped vessels

    def load(date):
        if date in cache:
            return cache[date]
        f = by_date.get(date)
        vm = {}
        if f:
            for v in json.load(open(f))["vessels"]:
                if v["mmsi"] in dropped or not v["kf"]:
                    continue
                vm[v["mmsi"]] = {"mmsi": v["mmsi"], "name": v.get("name"),
                                 "type": canon.get(v["mmsi"]) or v.get("type"),
                                 "kf": _despike(v["kf"]), "gaps": v["gaps"]}
        if len(cache) > 4:
            cache.pop(next(iter(cache)))
        cache[date] = vm
        return vm

    print(f"[2/2] stitching {len(dates)} day-tiles → {args.out}")
    for i, date in enumerate(dates):
        meta = json.load(open(by_date[date]))["meta"]
        start_m = meta["start"]
        # neighbours by calendar day (epoch arithmetic; tiles are gapless but be safe)
        prev_d = _date_of_epoch(start_m - DAY)
        next_d = _date_of_epoch(start_m + DAY)
        cur, prev, nxt = load(date), load(prev_d), load(next_d)

        out_vessels = []
        for m, v in cur.items():
            combined = list(v["kf"])
            cgaps = list(v["gaps"])  # REAL pre-DP gaps from the source tile
            if m in prev:
                combined = prev[m]["kf"] + combined
                cgaps = prev[m]["gaps"] + cgaps
            if m in nxt:
                combined = combined + nxt[m]["kf"]
                cgaps = cgaps + nxt[m]["gaps"]
            combined.sort(key=lambda k: k[0])
            kf, gaps = stitch_day(combined, cgaps, start_m)
            if kf:
                out_vessels.append({"mmsi": m, "name": v["name"], "type": v["type"],
                                    "kf": kf, "gaps": gaps})
        out_meta = dict(meta)
        out_meta["end"] = start_m + DAY  # exact seam, not the inherited last-ping epoch
        out_meta["vessels"] = len(out_vessels)
        out_meta["keyframes"] = sum(len(x["kf"]) for x in out_vessels)
        out_meta["stitched"] = True
        with open(os.path.join(args.out, f"tracks_{date}.json"), "w") as fh:
            json.dump({"meta": out_meta, "vessels": out_vessels}, fh, separators=(",", ":"))
        if i % 100 == 0 or i == len(dates) - 1:
            print(f"      {i + 1}/{len(dates)}  {date}  ({len(out_vessels)} vessels)")
    print("done.")


def _date_of_epoch(epoch):
    import datetime as dt
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d")


if __name__ == "__main__":
    main()
