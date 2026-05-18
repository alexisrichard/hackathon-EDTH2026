# KSE Russian Shadow Fleet — what we have and what we'd need

## KSE definition (from their quarterly tracker)

> **Shadow fleet** — vessels without links to G7+ jurisdictions for registered
> ownership, management, and flagging, as well as without P&I insurance by the
> International Group of P&I Clubs.

— Kyiv School of Economics Institute, Russian Shadow Fleet Tracker, April 2026.

## What we extracted from the public PDF

Two CSVs in this directory:

- **`kse_shadow_fleet_managers.csv`** — 72 rows. Top ship/commercial managers
  by Russian shadow-fleet volume per month (Jan-Mar 2026). Names like
  `Russia. South Fleet Ltd`, `UAE. Nova Shipmanagement Llc-Fz`, etc. These are
  the **shell companies operating the tankers**, not the tankers themselves.

- **`kse_shadow_fleet_buyers.csv`** — 48 rows. Top oil buyers (China,
  India, Syria, etc.) by Russian-origin volume.

The public PDF is aggregate market analysis. It does NOT contain a vessel-level
list (no IMO numbers, no MMSIs).

## What we'd need to apply the KSE definition ourselves

To classify any vessel as "shadow fleet" by KSE's criteria, we'd need to check
4 attributes per vessel and assert "no G7+ link" for the first three:

| Attribute | Source | Cost / access |
|---|---|---|
| Registered ownership | Equasis, IHS Markit, Clarksons | Equasis is free with login; commercial DBs are paid |
| Management (ship + ISM manager) | Equasis | Free with login |
| Flag state | AIS data (we have this) + Equasis for history | Free |
| P&I insurance (IG club member?) | International Group of P&I Clubs (igpandi.org); IG publishes aggregate but not per-vessel | Per-vessel status not publicly listed |

**G7+ jurisdictions** = G7 countries + EU + selected aligned states.

## Practical paths from here

In order of bang-for-the-buck:

1. **Email KSE** (`kse@kse.org.ua`) and ask for the underlying vessel-level
   dataset. Their analysts maintain a list of ~600+ shadow-fleet tankers with
   IMOs. They sometimes share for research with attribution. This is the most
   direct path to a list.

2. **Equasis batch lookup**. We have ~1,500 unique MMSIs in our Danish AIS
   coverage that operated in the Baltic. For each MMSI, Equasis can return
   IMO + owner + manager + flag history. Free but rate-limited (manual web
   scraping or polite API use). We could derive our own shadow-fleet score
   per vessel from this, but it's not a pre-event task — defer to hackathon.

3. **Cross-reference what we already have**:
   - **OFAC SDN** (1,480 entries with IMO/MMSI) — already gives us a sanctioned
     subset of the population.
   - **UK OFSI** (219 shipping entities) — gives us shipping shell companies,
     which match KSE's manager column. e.g., AZIA SHIPPING, EIGER SHIPPING,
     ALGHAF MARINE DMCC are already in our `sanctions_maritime.csv`.
   - **KSE managers CSV** (this folder) — adds 72 more company names.
   - Joining `kse_shadow_fleet_managers.csv` × `sanctions_maritime.csv` by
     fuzzy company name match is left to the hackathon team.

4. **Atlantic Council / think-tank lists**. Several think tanks (Atlantic
   Council, Henry Jackson Society, CEPA) publish named shadow-fleet incident
   trackers. Less comprehensive than KSE but free.

## File-format conventions for if KSE shares the vessel-level data

Whatever they send (Excel, CSV, JSON), save to
`data/reference/raw/kse_shadow_fleet_vessels_YYYYMMDD.{xlsx,csv,json}` and
the parser can be added to `scripts/reference/parse_kse_pdf.py` (rename to
`parse_kse.py` once it handles non-PDF inputs).
