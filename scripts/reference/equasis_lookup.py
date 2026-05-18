"""Equasis per-MMSI / per-IMO vessel lookup.

Equasis has no public API; we use a session-based form login + HTML scrape.
Designed for on-demand single-vessel lookups during the demo, NOT bulk scraping
(their ToS disallows that).

Usage:
  python scripts/reference/equasis_lookup.py --imo 9329760
  python scripts/reference/equasis_lookup.py --imo 9329760 --imo 9462108
  python scripts/reference/equasis_lookup.py --imo-file path/to/imos.txt

Auth: reads EQUASIS_USERNAME and EQUASIS_PASSWORD from .env.local.

Output: data/reference/equasis/<imo>.json — full Equasis details for the vessel.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

USERNAME = os.environ.get("EQUASIS_USERNAME")
PASSWORD = os.environ.get("EQUASIS_PASSWORD")
if not (USERNAME and PASSWORD):
    print("ERROR: EQUASIS_USERNAME and/or EQUASIS_PASSWORD not set in .env.local", file=sys.stderr)
    sys.exit(1)

OUT_DIR = Path("data/reference/equasis")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://www.equasis.org/EquasisWeb"
LOGIN_URL = f"{BASE}/authen/HomePage?fs=HomePage"
SEARCH_URL = f"{BASE}/restricted/Search"
SHIP_INFO_URL = f"{BASE}/restricted/ShipInfo"

# Equasis rejects non-browser User-Agents (will refuse with "browser not supported").
# Use a realistic Chrome UA. Per-MMSI lookup at hackathon scale; not bulk scraping.
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36"
BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
}


def login(session: requests.Session) -> bool:
    """Authenticate the session against Equasis.

    Two-step: GET the login page first (to establish a JSESSIONID cookie),
    then POST the credentials. Equasis is Java-backed and rejects POSTs that
    don't have an existing session.
    """
    # Step 1: GET to establish session
    session.get(LOGIN_URL, headers=BROWSER_HEADERS, timeout=30)

    # Step 2: POST credentials
    r = session.post(
        LOGIN_URL,
        data={"j_email": USERNAME, "j_password": PASSWORD, "submit": "Login"},
        headers={"User-Agent": UA, "Referer": LOGIN_URL},
        timeout=30,
        allow_redirects=True,
    )
    if r.status_code not in (200, 302):
        print(f"  login HTTP {r.status_code}", flush=True)
        return False

    # The authenticated home shows "Logout" link / the user's name; the
    # login page still shows j_email/j_password fields. Heuristic:
    if 'name="j_email"' in r.text or 'name="j_password"' in r.text:
        print("  login appears to have failed (still seeing login form fields)", flush=True)
        # Look for error hints
        soup = BeautifulSoup(r.text, "lxml")
        for el in soup.select(".alert, .error, .message"):
            txt = el.get_text(strip=True)
            if txt:
                print(f"  page message: {txt[:200]}", flush=True)
        return False
    return True


def search_vessel(session: requests.Session, imo: str) -> str | None:
    """Search for a vessel by IMO. Returns the vessel info page HTML or None."""
    r = session.post(
        SEARCH_URL,
        data={
            "P_ENTREE_HAU": imo,
            "P_PAGE": "ShipsImoSearch",
            "valueImo": imo,
            "valueNameSearch": "",
            "Type_visit": "",
        },
        headers=BROWSER_HEADERS,
        timeout=30,
        allow_redirects=True,
    )
    if r.status_code != 200:
        return None
    if "Ship not found" in r.text or "No ship matches" in r.text:
        return None
    # The search result page links to ShipInfo?P_IMO=<imo>
    info = session.get(SHIP_INFO_URL, params={"P_IMO": imo},
                       headers=BROWSER_HEADERS, timeout=30)
    if info.status_code != 200:
        return None
    return info.text


def parse_ship_info(html: str, imo: str) -> dict:
    """Extract structured fields from an Equasis ship info HTML page.

    Equasis ship pages have:
      - An <h4> title like "EAGLE S - IMO n° 9329760"
      - Multiple <table>s with column headers in <th> and data in <td>
      - Each table is its own structured section (management, classification,
        inspections, P&I, etc.)
    """
    soup = BeautifulSoup(html, "lxml")
    def clean(s: str | None) -> str:
        return re.sub(r"\s+", " ", s or "").strip()

    out: dict = {"imo": imo}

    # Ship title block (h4 with "NAME - IMO n° NNNNNNN")
    title_h4 = soup.find("h4")
    if title_h4:
        title_text = clean(title_h4.get_text())
        out["ship_title"] = title_text
        # Parse name out of "NAME - IMO n° ..."
        m = re.match(r"^(.*?)\s*-\s*IMO", title_text)
        if m:
            out["ship_name"] = m.group(1).strip()

    # Parse every table: first row is headers (th), subsequent rows are data rows
    tables_out: list[dict] = []
    for ti, table in enumerate(soup.find_all("table")):
        # Try to label the table by its closest preceding heading
        heading = None
        for prev in table.find_all_previous(["h3", "h4", "h5"], limit=1):
            heading = clean(prev.get_text())[:80]
            break

        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"])
        headers = [clean(c.get_text()) for c in header_cells]
        # If first row has only td (no th), treat as a data row with no headers
        first_is_header = any(c.name == "th" for c in header_cells)

        data_rows: list[dict | list] = []
        for tr in rows[(1 if first_is_header else 0):]:
            cells = [clean(c.get_text(" ")) for c in tr.find_all(["th", "td"])]
            if not cells or not any(cells):
                continue
            if headers and len(cells) == len(headers):
                data_rows.append({headers[i]: cells[i] for i in range(len(headers))})
            else:
                data_rows.append(cells)
        if data_rows:
            tables_out.append({
                "table_index": ti,
                "preceding_heading": heading,
                "headers": headers if first_is_header else None,
                "rows": data_rows,
            })

    out["tables"] = tables_out
    out["_fetched_at"] = datetime.now(timezone.utc).isoformat()
    return out


_s3 = boto3.client("s3", region_name="eu-west-3")


def lookup_one(session: requests.Session, imo: str) -> dict | None:
    out_path = OUT_DIR / f"{imo}.json"
    if out_path.exists() and out_path.stat().st_size > 100:
        print(f"  {imo}: cache hit", flush=True)
        return json.loads(out_path.read_text(encoding="utf-8"))

    html = search_vessel(session, imo)
    if not html:
        print(f"  {imo}: not found or fetch failed", flush=True)
        return None
    data = parse_ship_info(html, imo)
    # Save both parsed JSON and raw HTML for debugging
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    raw_path = OUT_DIR / f"{imo}.raw.html"
    raw_path.write_text(html, encoding="utf-8")
    # Mirror to S3 (parsed JSON only — raw HTML stays local for repro)
    try:
        _s3.upload_file(str(out_path), "edth2026-baltic", f"reference/equasis/{out_path.name}")
    except Exception as ex:
        print(f"  {imo}: S3 upload failed ({ex})", flush=True)
    print(f"  {imo}: ok ({len(data.get('tables',[]))} tables, {raw_path.stat().st_size//1024} KB raw)", flush=True)
    return data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--imo", action="append", default=[], help="IMO number(s) to look up; repeatable")
    p.add_argument("--imo-file", help="File with one IMO per line")
    p.add_argument("--rate-limit", type=float, default=2.0, help="Sleep seconds between lookups")
    args = p.parse_args()

    imos = list(args.imo)
    if args.imo_file:
        with open(args.imo_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    imos.append(line)
    imos = [i for i in imos if re.match(r"^\d{7}$", i)]
    if not imos:
        print("No valid IMO numbers given (must be 7 digits)", file=sys.stderr)
        return 2

    session = requests.Session()
    print(f"Logging in as {USERNAME}...", flush=True)
    if not login(session):
        print("Login failed — check credentials in .env.local", file=sys.stderr)
        return 1
    print(f"Logged in. Looking up {len(imos)} IMO(s)...\n", flush=True)

    for i, imo in enumerate(imos):
        lookup_one(session, imo)
        if i < len(imos) - 1:
            time.sleep(args.rate_limit)

    print(f"\nDone. Results in {OUT_DIR}/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
