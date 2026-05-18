"""Fetch maritime-relevant sanctions data from US, EU, and UK sources.

Strategy:
- OFAC SDN (US): authoritative vessel-type entries, stable CSV download.
- EU consolidated list: best-effort; format changes, fall back to noting failure.
- UK OFSI list: best-effort; URL rotates monthly.

Outputs to data/reference/:
  raw/ofac_sdn.csv              raw downloads as fetched
  raw/eu_consolidated.xml
  raw/uk_consolidated.csv
  sanctions_maritime.csv        normalized union, vessel/maritime entries only

Schema of sanctions_maritime.csv:
  source, entry_id, name, type, country, imo, mmsi, flag, owner, notes, fetched_at
"""

from __future__ import annotations

import csv
import io
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

REF_DIR = Path("data/reference")
RAW_DIR = REF_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "edth2026-baltic-prep/0.1 (alexisrichard@github)"}

OFAC_SDN_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
OFAC_SDN_ALT = "https://www.treasury.gov/ofac/downloads/sdn.csv"
# EU consolidated direct URL is token-gated; using OpenSanctions normalized copy (CC-BY-NC).
EU_FSF_OPENSANCTIONS_URL = "https://data.opensanctions.org/datasets/latest/eu_fsf/targets.simple.csv"
EU_FSF_OPENSANCTIONS_DATED = "https://data.opensanctions.org/datasets/20260518/eu_fsf/targets.simple.csv"
UK_OFSI_URL = "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.csv"


def fetch(url: str, timeout: int = 60) -> bytes | None:
    try:
        r = requests.get(url, timeout=timeout, headers=UA)
        r.raise_for_status()
        return r.content
    except requests.exceptions.RequestException as ex:
        print(f"  fetch failed: {url} -> {ex}", flush=True)
        return None


def fetch_ofac_sdn() -> list[dict]:
    """OFAC SDN CSV. Schema is documented at
    https://www.treasury.gov/ofac/downloads/data_spec.txt
    Columns: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type,
             Tonnage, GRT, Vess_flag, Vess_owner, Remarks
    """
    print("[OFAC SDN]")
    body = fetch(OFAC_SDN_URL) or fetch(OFAC_SDN_ALT)
    if not body:
        print("  no data\n")
        return []
    raw_path = RAW_DIR / "ofac_sdn.csv"
    raw_path.write_bytes(body)
    print(f"  saved raw: {raw_path} ({len(body) // 1024} KB)")

    text = body.decode("latin-1", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows: list[dict] = []
    for r in reader:
        if len(r) < 12:
            continue
        ent_num, name, sdn_type, program, title, call_sign, vess_type, tonnage, grt, flag, owner, remarks = r[:12]
        if sdn_type.strip().upper() != "VESSEL":
            continue
        imo = ""
        m = re.search(r"\bIMO\s+(\d{7})\b", remarks, re.IGNORECASE)
        if m:
            imo = m.group(1)
        rows.append({
            "source": "OFAC_SDN",
            "entry_id": ent_num.strip(),
            "name": name.strip(),
            "type": "vessel",
            "country": flag.strip(),
            "imo": imo,
            "mmsi": "",
            "flag": flag.strip(),
            "owner": owner.strip(),
            "notes": remarks.strip().replace("\n", " ")[:500],
        })
    print(f"  parsed {len(rows)} vessel entries\n")
    return rows


def fetch_eu_fsf() -> list[dict]:
    """EU Financial Sanctions Files via OpenSanctions normalized CSV.

    OpenSanctions normalizes the EU consolidated list into a Follow-the-Money
    schema. License: CC-BY-NC 4.0 (non-commercial use; we treat as research-only
    for the hackathon demo, NOT for any commercial productization).
    """
    print("[EU FSF via OpenSanctions]")
    body = fetch(EU_FSF_OPENSANCTIONS_URL) or fetch(EU_FSF_OPENSANCTIONS_DATED)
    if not body:
        print("  no data\n")
        return []
    raw_path = RAW_DIR / "eu_fsf_targets.csv"
    raw_path.write_bytes(body)
    print(f"  saved raw: {raw_path} ({len(body) // 1024} KB)")

    text = body.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    # OpenSanctions FTM schema: Vessel rows have schema='Vessel'; shipping companies
    # often have 'maritime' or 'shipping' in their name/aliases.
    SHIP_SCHEMAS = {"Vessel", "Vehicle"}  # Vehicle covers some legacy entries
    SHIPPING_KW = ("shipping", "tanker", "marine", "maritime", "fleet",
                   "navigation", "vessel", "ship management")
    for row in reader:
        sch = (row.get("schema") or "").strip()
        name = (row.get("name") or "").strip()
        aliases = (row.get("aliases") or "").lower()
        identifiers = row.get("identifiers") or ""
        is_vessel = sch in SHIP_SCHEMAS
        is_ship_co = sch in ("Organization", "Company") and any(
            kw in name.lower() or kw in aliases for kw in SHIPPING_KW
        )
        if not (is_vessel or is_ship_co):
            continue
        # Try to extract IMO from identifiers field
        imo = ""
        m = re.search(r"\b(IMO|imo[N]?o?)[:\s]*(\d{7})\b", identifiers + " " + (row.get("name") or ""), re.IGNORECASE)
        if m:
            imo = m.group(2)
        country = (row.get("countries") or "").split(";")[0].strip()
        rows.append({
            "source": "EU_FSF_OS",
            "entry_id": (row.get("id") or "").strip(),
            "name": name,
            "type": "vessel" if is_vessel else "shipping_entity",
            "country": country,
            "imo": imo,
            "mmsi": "",
            "flag": "",
            "owner": "",
            "notes": (row.get("sanctions") or "")[:500],
        })
    print(f"  parsed {len(rows)} maritime entries\n")
    return rows


def fetch_uk_ofsi() -> list[dict]:
    """UK OFSI consolidated list CSV.

    Schema: row 1 is a 'Last Updated,DATE' preamble; row 2 has the real headers.
    `Group Type` is the discriminator (Individual / Entity / Ship). For maritime
    we want Ship rows; we also keep entities whose name suggests shipping ops.
    """
    print("[UK OFSI]")
    body = fetch(UK_OFSI_URL)
    if not body:
        print("  no data\n")
        return []
    raw_path = RAW_DIR / "uk_consolidated.csv"
    raw_path.write_bytes(body)
    print(f"  saved raw: {raw_path} ({len(body) // 1024} KB)")

    text = body.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("last updated"):
        text = "\n".join(lines[1:])
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict] = []
    SHIPPING_KW = ("shipping", "tanker", "marine", "maritime", "fleet", "vessel", "navigation")
    for row in reader:
        gtype = (row.get("Group Type") or "").strip().lower()
        name_blob = " ".join(
            row.get(k, "") for k in ("Name 6", "Name 1", "Name 2", "Name 3")
        ).lower()
        is_ship = gtype == "ship"
        is_shipping_entity = gtype == "entity" and any(kw in name_blob for kw in SHIPPING_KW)
        if not (is_ship or is_shipping_entity):
            continue
        primary_name = (
            row.get("Name 6")
            or " ".join(filter(None, [row.get(k, "") for k in ("Name 1", "Name 2", "Name 3", "Name 4", "Name 5")])).strip()
        )
        notes = (row.get("Other Information") or "").replace("\n", " ")
        imo = ""
        m = re.search(r"\bIMO[:\s]*(\d{7})\b", notes, re.IGNORECASE)
        if m:
            imo = m.group(1)
        rows.append({
            "source": "UK_OFSI",
            "entry_id": (row.get("Group ID") or "").strip(),
            "name": primary_name.strip(),
            "type": "vessel" if is_ship else "shipping_entity",
            "country": (row.get("Country") or "").strip(),
            "imo": imo,
            "mmsi": "",
            "flag": "",
            "owner": "",
            "notes": notes[:500],
        })
    print(f"  parsed {len(rows)} maritime entries (ships + shipping entities)\n")
    return rows


def main() -> int:
    print(f"Fetching sanctions data ({datetime.now(timezone.utc).isoformat()})\n")
    all_rows: list[dict] = []
    all_rows += fetch_ofac_sdn()
    all_rows += fetch_eu_fsf()
    all_rows += fetch_uk_ofsi()

    fetched_at = datetime.now(timezone.utc).isoformat()
    for r in all_rows:
        r["fetched_at"] = fetched_at

    out = REF_DIR / "sanctions_maritime.csv"
    fieldnames = [
        "source", "entry_id", "name", "type", "country",
        "imo", "mmsi", "flag", "owner", "notes", "fetched_at",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            w.writerow(r)

    print(f"--- Summary ---")
    print(f"Total maritime-relevant entries: {len(all_rows)}")
    counts: dict[str, int] = {}
    for r in all_rows:
        counts[r["source"]] = counts.get(r["source"], 0) + 1
    for src, n in counts.items():
        print(f"  {src:20s} {n}")
    print(f"Output: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
