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
EU_CONSOLIDATED_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
)
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


def fetch_eu_consolidated() -> list[dict]:
    """EU consolidated XML. Element 'sanctionEntity' with subjectType=enterprise often
    contains shipping companies; vessels themselves are rare in this feed.
    """
    print("[EU Consolidated]")
    body = fetch(EU_CONSOLIDATED_URL)
    if not body:
        print("  no data\n")
        return []
    raw_path = RAW_DIR / "eu_consolidated.xml"
    raw_path.write_bytes(body)
    print(f"  saved raw: {raw_path} ({len(body) // 1024} KB)")
    rows: list[dict] = []
    try:
        root = ET.fromstring(body)
    except ET.ParseError as ex:
        print(f"  XML parse failed: {ex}\n")
        return rows

    for entity in root.iter():
        tag = entity.tag.split("}", 1)[-1]
        if tag not in {"sanctionEntity"}:
            continue
        subject_type = entity.attrib.get("subjectType", "")
        names = []
        for ne in entity.iter():
            if ne.tag.split("}", 1)[-1] == "nameAlias":
                w = ne.attrib.get("wholeName", "")
                if w:
                    names.append(w)
        primary_name = names[0] if names else ""
        text_blob = ET.tostring(entity, encoding="unicode").lower()
        is_maritime = any(
            kw in text_blob
            for kw in ("vessel", "ship", "tanker", "shipping", "marine", "maritime", "fleet")
        )
        if not is_maritime:
            continue
        rows.append({
            "source": "EU_consolidated",
            "entry_id": entity.attrib.get("logicalId", ""),
            "name": primary_name,
            "type": subject_type or "entity",
            "country": "",
            "imo": "",
            "mmsi": "",
            "flag": "",
            "owner": "",
            "notes": " | ".join(names[1:5])[:500],
        })
    print(f"  parsed {len(rows)} maritime-relevant entries\n")
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
    all_rows += fetch_eu_consolidated()
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
