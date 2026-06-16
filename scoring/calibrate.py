"""Fleet calibration for the behavioural prior.

The raw behavioural composite is too hot: loitering, AIS gaps and manoeuvring are
*normal* for fishing/service vessels, so a class-agnostic score flags them. This
re-expresses each vessel's behaviour as deviation *within its own ship class*
(median→0, p90→1 per feature). It strongly re-centres the MASS — fleet p50 drops
from ~0.78 to ~0.33 — so ordinary class-typical traffic no longer reads as risky.

KNOWN LIMITATION (handed to Côme — behavioural core): the upper TAIL still
saturates. The raw `dark_events` and `kinematics` features themselves pin at 1.0
for a large fraction of small `other`/`pleasure` craft, so a dozen multi-axis-
extreme small boats max out at class_risk≈1.0. Class-relative deviation can't
un-saturate a feature that's already 1.0 across much of its class — that needs a
softer feature definition (or a sample-size/confidence guard for 1–2-day priors)
in `behavioral.py`. Net effect today: treat the prior as a SUPPORTING signal; the
zone cue's real discrimination comes from combining it with infra + live + SAR.

Baselines are learned from the fleet (no per-vessel tuning), so it's principled,
not hero-fitted. Used by the fleet validator and the backend scoring loader so
both score identically.
"""
from __future__ import annotations

from collections import defaultdict

FEATURES = ("dark_events", "loiter", "kinematics")
_MIN_CLASS = 20  # below this, a class falls back to the global baseline


def percentile(sorted_asc: list[float], q: float) -> float:
    if not sorted_asc:
        return 0.0
    idx = min(len(sorted_asc) - 1, int(q * (len(sorted_asc) - 1)))
    return sorted_asc[idx]


def class_relative(rows: list[dict]) -> None:
    """Set ``row['class_risk']`` ∈ [0,1] in place for each row.

    Each row needs ``type`` (ship class), ``components`` (raw behavioural feature
    values), and ``prior_days`` (rows with no prior history score 0 and don't seed
    baselines).
    """
    by_class: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["prior_days"] > 0:
            by_class[r["type"]].append(r)

    def baseline(pool: list[dict], feat: str) -> tuple[float, float]:
        vals = sorted(float(r["components"].get(feat, 0.0)) for r in pool)
        return percentile(vals, 0.50), percentile(vals, 0.90)

    global_pool = [r for r in rows if r["prior_days"] > 0]
    gbase = {f: baseline(global_pool, f) for f in FEATURES}
    cbase = {
        cls: {f: baseline(pool, f) for f in FEATURES}
        for cls, pool in by_class.items()
        if len(pool) >= _MIN_CLASS
    }

    for r in rows:
        if r["prior_days"] == 0:
            r["class_risk"] = 0.0
            continue
        base = cbase.get(r["type"], gbase)
        devs = []
        for f in FEATURES:
            med, p90 = base[f]
            val = float(r["components"].get(f, 0.0))
            devs.append(max(0.0, min(1.0, (val - med) / max(p90 - med, 0.05))))
        r["class_risk"] = round(sum(devs) / len(devs), 4)
