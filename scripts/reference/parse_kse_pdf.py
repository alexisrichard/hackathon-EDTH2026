"""Extract structured tables from KSE Russian Shadow Fleet Tracker quarterly PDFs.

Input:  data/reference/raw/kse_shadow_fleet_tracker_*.pdf
Output: data/reference/kse_shadow_fleet_managers.csv   — top ship managers by volume
        data/reference/kse_shadow_fleet_buyers.csv     — top buyers by volume

NOTE: The KSE quarterly PDF reports aggregate statistics only — country
shares, top-10 ship managers, top-10 oil buyers. It does NOT contain
vessel-level IMO numbers. For the per-vessel shadow fleet list, you need
to email KSE directly: kse@kse.org.ua.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pdfplumber

PDF_DIR = Path("data/reference/raw")
OUT_DIR = Path("data/reference")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_three_month_table(rows: list[list[str | None]], months: list[str]) -> list[dict]:
    """Parse a 3-month side-by-side ship-manager / buyer table.

    Layout (from pdfplumber on the KSE PDFs):
      Row 0: [Month1, None, None, Month2, None, None, Month3, None, None]
      Row 1: [Manager, Volume, %, Manager, Volume, %, Manager, Volume, %]
      Row 2+: data
    """
    if len(rows) < 3:
        return []
    headers = [c or "" for c in (rows[1] if rows[1] else [])]
    if len(headers) < 9:
        return []
    out: list[dict] = []
    for r in rows[2:]:
        if not r or len(r) < 9:
            continue
        for m_idx, month in enumerate(months):
            base = m_idx * 3
            entity = (r[base] or "").strip()
            volume = (r[base + 1] or "").strip().replace(",", "")
            share = (r[base + 2] or "").strip().rstrip("%")
            if not entity:
                continue
            out.append({
                "month": month,
                "entity": entity,
                "volume_kbd": volume,
                "share_pct": share,
            })
    return out


def parse_pdf(pdf_path: Path, source_quarter: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Returns (managers_global, managers_baltic, buyers) row lists."""
    managers_global: list[dict] = []
    managers_baltic: list[dict] = []
    buyers: list[dict] = []
    months_guess = ["Jan", "Feb", "Mar"]  # quarterly tracker — adjust for other quarters

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            text = (page.extract_text() or "").lower()
            for j, t in enumerate(tables):
                if not t or len(t) < 3:
                    continue
                header = " ".join(str(c or "") for c in t[0]).lower()
                second = " ".join(str(c or "") for c in t[1]).lower()
                if "ship manager" in second:
                    rows = extract_three_month_table(t, months_guess)
                    target = managers_baltic if "baltic" in text else managers_global
                    for r in rows:
                        r["scope"] = "Baltic Sea" if target is managers_baltic else "Global"
                        r["source_quarter"] = source_quarter
                    target.extend(rows)
                elif "buyer" in second:
                    # Buyer tables are single-quarter aggregate
                    headers = [c or "" for c in t[1]]
                    for row in t[2:]:
                        if not row or len(row) < 3:
                            continue
                        buyers.append({
                            "scope": "Baltic Sea" if "baltic" in text else "Global",
                            "source_quarter": source_quarter,
                            "buyer": (row[0] or "").strip(),
                            "volume_kbd": (row[1] or "").strip().replace(",", ""),
                            "share_pct": (row[2] or "").strip().rstrip("%"),
                            "product": "crude_oil" if "crude" in text else "oil_products" if "products" in text else "unknown",
                        })
    return managers_global, managers_baltic, buyers


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  -> {path}  {len(rows)} rows")


def main() -> int:
    pdfs = sorted(PDF_DIR.glob("kse_shadow_fleet_tracker_*.pdf"))
    if not pdfs:
        print(f"No KSE PDFs found in {PDF_DIR}", file=sys.stderr)
        return 1
    all_managers: list[dict] = []
    all_buyers: list[dict] = []
    for pdf in pdfs:
        # Derive quarter from filename
        m = re.search(r"(\w+)_(\d{4})\.pdf", pdf.name)
        quarter = f"{m.group(1)}-{m.group(2)}" if m else pdf.stem
        print(f"\n=== {pdf.name} (quarter={quarter}) ===")
        mg, mb, b = parse_pdf(pdf, quarter)
        all_managers.extend(mg)
        all_managers.extend(mb)
        all_buyers.extend(b)
        print(f"  managers_global: {len(mg)}, managers_baltic: {len(mb)}, buyers: {len(b)}")

    write_csv(
        OUT_DIR / "kse_shadow_fleet_managers.csv",
        ["scope", "source_quarter", "month", "entity", "volume_kbd", "share_pct"],
        all_managers,
    )
    write_csv(
        OUT_DIR / "kse_shadow_fleet_buyers.csv",
        ["scope", "source_quarter", "product", "buyer", "volume_kbd", "share_pct"],
        all_buyers,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
