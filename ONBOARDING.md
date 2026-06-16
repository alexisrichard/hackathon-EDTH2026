# Team onboarding — EDTH 2026 Baltic project

Set up your machine to work on the project. Cross-platform: Windows (PowerShell + winget) and macOS (Homebrew). All three teammates should be able to clone-and-go after this.

**Just want the demo?** `git clone … && cd frontend && npm install && npm run dev` — the dashboard runs entirely from committed data (cues, overlays, hero-incident AIS replay days), no AWS, no Python, no rebuild. The rest of this guide is for the data-prep / full-rebuild path.

**Time budget:** ~15 minutes the first time (no AWS setup needed).

---

## 0. What you'll have at the end

- A local clone of the repo with `data/geo/` and `data/reference/` populated (~16 MB of GeoJSON + small CSVs)
- Python 3.12 venv with all data tools (DuckDB, GeoPandas, JupyterLab, …)
- A working notebook environment to inspect data

> **No AWS.** The project bucket has been retired and deleted — nothing reads from S3 anymore. Full datasets rebuild from their original public sources via `scripts/` (see [`DATA_GUIDE.md`](DATA_GUIDE.md)); only a few of those need keys (Copernicus / Kaggle / GFW / Equasis), never AWS.

---

## 1. Clone the repo

```bash
git clone https://github.com/alexisrichard/hackathon-EDTH2026.git
cd hackathon-EDTH2026
```

If you've never used `gh` before, install it (`brew install gh` on macOS, `winget install GitHub.cli` on Windows) and run `gh auth login`.

---

## 2. Install the system tools

### macOS (Homebrew)

```bash
# Homebrew itself, if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Tools (awscli is NOT required — the project no longer uses S3)
brew install python@3.12 git
```

Verify:
```bash
python3.12 --version   # expect Python 3.12.x
```

### Windows 11 (winget)

Open **PowerShell** (the regular one — not "PowerShell ISE").

```powershell
# awscli is NOT required — the project no longer uses S3
winget install -e --id Python.Python.3.12  --accept-source-agreements --accept-package-agreements
winget install -e --id Git.Git             --accept-source-agreements --accept-package-agreements
```

**Important:** close and reopen PowerShell after these, so the new PATH entries get picked up.

Verify:
```powershell
python --version
```

If `python` opens the Microsoft Store: go to `Settings → Apps → Advanced app settings → App execution aliases` and turn off the Python aliases. Re-open PowerShell.

---

## 3. Credentials (OPTIONAL — only for full-dataset rebuilds)

**No AWS is needed.** The project bucket has been retired and deleted; there is nothing to configure with `aws configure`. The demo and the committed data need zero credentials.

You only need keys if you want to **regenerate a full dataset from its public source** — and even then, only some sources require them (never AWS):

- **Copernicus** (`COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET`) — Sentinel imagery
- **Kaggle** (`~/.kaggle/kaggle.json`) — the 10 Kaggle ML datasets
- **GFW** (`GFW_API_TOKEN`) — Global Fishing Watch events
- **Equasis** (`EQUASIS_USERNAME` / `EQUASIS_PASSWORD`) — vessel registry lookups

Put the API keys in `.env.local` at the repo root (gitignored). Per-source rebuild commands are in [`DATA_GUIDE.md`](DATA_GUIDE.md). The Danish AIS rebuild (`python scripts/ingest/danish_ais.py date <YYYY-MM-DD>`) downloads from the **public** Danish Maritime Authority source and needs **no credentials at all**.

---

## 4. Python venv + project dependencies

From the repo root:

### macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks the activation script, run once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The install takes 3–5 minutes (geopandas + jupyterlab + sentinelhub pull large native deps).

**Smoke test:**

```bash
python -c "import geopandas, duckdb, pyarrow, boto3, pyais; print('ok')"
```

If that prints `ok`, you're set.

---

## 5. Verify you can read project data

```bash
# Read the incidents CSV from the repo
python -c "import pandas as pd; df = pd.read_csv('data/reference/incidents.csv'); print(df[['date_utc','name','vessel_name']])"

# Read a geo layer
python -c "import geopandas as gpd; gdf = gpd.read_file('data/geo/submarine_cables.geojson'); print('cables:', len(gdf), 'features')"

# (Optional) rebuild one day of AIS from the public Danish source and query the local parquet — no AWS
python -c "import duckdb; con = duckdb.connect(); print(con.execute(\"SELECT COUNT(*) FROM read_parquet('data/ais/parquet/source=danish/year=2024/month=12/day=25/*.parquet')\").fetchall())" 2>/dev/null || echo "no local AIS yet — run scripts/ingest/danish_ais.py date 2024-12-25 first"
```

---

## 6. JupyterLab for notebooks

```bash
jupyter lab
```

This opens in your browser at `http://localhost:8888/lab`. Notebooks live in `data/samples/notebooks/` (created during Task 11 — empty for now).

---

## 7. Where things live

| Path | What |
|---|---|
| `AGENTS.md` | Project guide for humans + AI assistants — system design, data/rebuild layout, conventions, way of working. `CLAUDE.md` / `GEMINI.md` are pointers to it |
| `PLAN.md` | Project plan — read this if you haven't yet |
| `data/SOURCES.md` | Where every dataset comes from + license |
| `data/geo/*.geojson` | Criticality layers (small, committed) |
| `data/reference/*.csv` | Incidents + sanctions (small, committed) |
| `data/ais/`, `data/sar/`, `data/optical/` | Local big-data rebuild output (**gitignored** — regenerate from public sources) |
| `scripts/common/` | Shared helpers (Baltic bbox; `sync_from_s3.py` is a retired no-op) |
| `scripts/geo/` | Criticality layer scripts |
| `scripts/reference/` | Sanctions + reference data scripts |
| `scripts/ingest/` | AIS ingest pipelines (Danish AIS → parquet → tracks → tiles) |
| `requirements.txt` | Python deps |
| `frontend/public/data/` | Committed demo data — cues, overlays, hero-incident AIS replay days |

## 8. Conventions

- **No cloud resources.** The project runs locally; the old S3 bucket is retired and deleted — don't create buckets or other cloud resources.
- **Baltic bbox:** lat 52°N–66°N, lon 9°E–30°E. Use `scripts.common.bbox.BALTIC_BBOX`.
- **Coordinates:** EPSG:4326 (WGS84) for storage, project to local UTM as needed.
- **Parquet partitioning:** `year=YYYY/month=MM/`.
- **Never commit:** `.env*`, raw AIS dumps, anything under `data/ais|sar|optical/`, your venv.
- **Always commit:** any code you wrote, GeoJSON layers under `data/geo/`, CSVs under `data/reference/`.

## 9. When something breaks

- **PowerShell can't activate venv** → see §4 ExecutionPolicy fix
- **pip resolver bouncing on s3fs/aiobotocore** → known. `pip install --force-reinstall --no-deps -r requirements.txt` and report what blew up
- **Danish AIS download fails** → the source is the public Danish Maritime Authority (no credentials); retry, and check `scripts/ingest/danish_ais.py` for the date range it covers
- **Overpass API 504/429** → the OSM fetch script auto-falls-over to mirrors; if all fail, wait and retry

## 10. Optional but useful

- **VS Code** or **Cursor** with Python + Jupyter extensions
- **DBeaver** if you want a GUI for DuckDB / inspecting Parquet
- **QGIS** (free) for poking at GeoJSON visually — `brew install --cask qgis` or `winget install QGIS.QGIS`

---

When you've gone through these and the smoke tests pass, ping the team channel. If you got stuck somewhere, fix the doc as you go — it's better that the next person doesn't hit the same wall.
