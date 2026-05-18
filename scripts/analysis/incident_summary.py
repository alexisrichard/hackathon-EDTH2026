"""Produce a one-page Markdown demo summary per incident, combining all evidence
we have collected: AIS coverage, sanctioned vessels in area, suspicious behaviors,
Sentinel scenes, criticality context.

Outputs:
  data/reference/incident_summaries/<incident_id>.md
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from textwrap import dedent

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.duck import connect  # type: ignore


INCIDENTS_CSV = Path("data/reference/incidents.csv")
SANCTIONS_CSV = Path("data/reference/sanctions_maritime.csv")
SENTINEL_CSV = Path("data/reference/sentinel_scenes.csv")
VESSELS_OF_INTEREST_CSV = Path("data/reference/vessels_of_interest.csv")
SUSPICIOUS_BEHAVIOR_CSV = Path("data/reference/suspicious_behavior.csv")

OUT_DIR = Path("data/reference/incident_summaries")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def ais_summary(con, d: date) -> dict:
    glob = f"s3://edth2026-baltic/ais/parquet/source=danish/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-*.parquet"
    try:
        row = con.execute(f"""
            SELECT COUNT(*) AS n_rows, COUNT(DISTINCT MMSI) AS n_vessels,
                   MIN(ts) AS min_ts, MAX(ts) AS max_ts
            FROM read_parquet('{glob}')
        """).fetchone()
        return {"available": True, "rows": row[0], "vessels": row[1],
                "min_ts": row[2], "max_ts": row[3]}
    except Exception:
        return {"available": False}


def main() -> int:
    if not INCIDENTS_CSV.exists():
        print(f"missing {INCIDENTS_CSV}", file=sys.stderr)
        return 1
    incidents = pd.read_csv(INCIDENTS_CSV)
    sentinel = pd.read_csv(SENTINEL_CSV) if SENTINEL_CSV.exists() else pd.DataFrame()
    voi = pd.read_csv(VESSELS_OF_INTEREST_CSV) if VESSELS_OF_INTEREST_CSV.exists() else pd.DataFrame()
    susp = pd.read_csv(SUSPICIOUS_BEHAVIOR_CSV) if SUSPICIOUS_BEHAVIOR_CSV.exists() else pd.DataFrame()

    con = connect()
    for _, inc in incidents.iterrows():
        inc_id = inc["incident_id"]
        d = datetime.fromisoformat(inc["date_utc"]).date()
        print(f"=== {inc_id} ({d}) ===", flush=True)

        ais = ais_summary(con, d)

        # Sentinel scenes for this incident
        sent_inc = sentinel[sentinel["incident_id"] == inc_id] if not sentinel.empty else pd.DataFrame()
        s2 = sent_inc[sent_inc["collection"] == "sentinel-2-l2a"] if not sent_inc.empty else pd.DataFrame()
        s1 = sent_inc[sent_inc["collection"] == "sentinel-1-grd"] if not sent_inc.empty else pd.DataFrame()
        s2_best = s2.nsmallest(3, "cloud_cover") if not s2.empty else pd.DataFrame()

        voi_inc = voi[voi["incident_id"] == inc_id] if not voi.empty else pd.DataFrame()
        susp_inc = susp[susp["date_utc"] == d.isoformat()] if not susp.empty else pd.DataFrame()

        md = []
        md.append(f"# {inc_id} — {inc['name']}")
        md.append("")
        md.append(f"**Date (UTC):** {inc['date_utc']} {inc.get('time_utc','') or '(time unknown)'}")
        md.append(f"**Vessel suspect:** {inc.get('vessel_name','unknown')} ({inc.get('vessel_flag','?')}, {inc.get('vessel_type','?')})")
        md.append(f"**Infrastructure:** {inc.get('infrastructure_name','?')} ({inc.get('infrastructure_type','?')})")
        md.append(f"**Approx location:** {inc['lat_approx']}°N, {inc['lon_approx']}°E ({inc.get('region','?')})")
        md.append(f"**Attribution status:** {inc.get('attribution_status','?')}")
        md.append("")
        notes = (inc.get("notes") or "")
        if notes:
            md.append(f"**Notes:** {notes}")
            md.append("")
        sources = (inc.get("sources") or "").split(";")
        if sources:
            md.append("**Sources:**")
            for s in sources:
                s = s.strip()
                if s:
                    md.append(f"- {s}")
            md.append("")

        md.append("## AIS data availability")
        if ais.get("available"):
            md.append(f"- Danish AIS: **{ais['rows']:,} rows / {ais['vessels']:,} vessels** for {d}")
            md.append(f"- S3: `s3://edth2026-baltic/ais/parquet/source=danish/year={d.year}/month={d.month:02d}/day={d.day:02d}/`")
        else:
            md.append(f"- Danish AIS for {d}: **not yet in S3** (pipeline may still be running)")
        md.append("")

        md.append("## Sentinel imagery (Element84 STAC, downloads need Copernicus account)")
        if not sent_inc.empty:
            md.append(f"- Sentinel-2 L2A: {len(s2)} scenes catalogued; best cloud-free options:")
            for _, r in s2_best.iterrows():
                md.append(f"  - `{r['scene_id']}` ({r['scene_datetime'][:10]}, "
                          f"cloud {r['cloud_cover']:.0f}%) → {r['self_href']}")
            md.append(f"- Sentinel-1 GRD (all-weather): {len(s1)} scenes catalogued.")
        else:
            md.append("- (no catalog data for this incident yet)")
        md.append("")

        md.append("## Vessels of interest (sanctioned/named matches in coverage)")
        if not voi_inc.empty:
            md.append(f"- {len(voi_inc)} matches in Danish AIS for this date:")
            for _, r in voi_inc.head(20).iterrows():
                md.append(f"  - **{r.get('Name','?')}** MMSI={r['MMSI']} IMO={r.get('IMO','')} "
                          f"({r['match_reason']}) — {r.get('n_points','?')} points")
        else:
            md.append("- (no matches yet — AIS pipeline may still be downloading this day, or vessel not in Danish receiver range)")
        md.append("")

        md.append("## Suspicious behavior (slow vessels × high criticality)")
        if not susp_inc.empty:
            md.append(f"- {len(susp_inc)} vessel-days flagged on {d}")
            md.append(f"- Top 10 by max_crit × duration:")
            top = susp_inc.assign(
                score=susp_inc["max_crit"] * susp_inc["duration_minutes"]
            ).nlargest(10, "score")
            for _, r in top.iterrows():
                md.append(f"  - **{r['Name']}** ({r['ship_type']}) MMSI={r['MMSI']} "
                          f"— {r['n_suspicious_points']} susp pts, "
                          f"min SOG {r['min_sog']:.2f} kn, "
                          f"duration {r['duration_minutes']:.0f} min")
        else:
            md.append("- (no AIS-criticality join for this date yet)")
        md.append("")

        md.append("## Demo notes")
        md.append(f"- Hero potential: {'YES — Eagle S replay is the canonical demo (PLAN §6 hero flow)' if inc_id == 'INC-2024-12-25' else 'secondary replay candidate'}")
        if ais.get("available"):
            md.append("- AIS data ready for replay")
        else:
            md.append("- Wait for AIS pipeline to finish this date before building replay")
        md.append("")

        out = OUT_DIR / f"{inc_id}.md"
        out.write_text("\n".join(md), encoding="utf-8")
        print(f"  -> {out}", flush=True)

    con.close()

    # Master index
    index = ["# Incident summaries", "",
             f"Generated {datetime.now().isoformat(timespec='seconds')}. "
             "One Markdown file per incident in this folder.", ""]
    for _, inc in incidents.iterrows():
        ais = ais_summary(connect(), datetime.fromisoformat(inc['date_utc']).date())
        avail = "✓ AIS ready" if ais.get("available") else "⏳ AIS pending"
        index.append(f"- [{inc['incident_id']}]({inc['incident_id']}.md) — {inc['name']} ({avail})")
    (OUT_DIR / "INDEX.md").write_text("\n".join(index), encoding="utf-8")
    print(f"\nWrote {OUT_DIR / 'INDEX.md'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
