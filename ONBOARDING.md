# Team onboarding — EDTH 2026 Baltic project

Set up your machine to work on the project. Cross-platform: Windows (PowerShell + winget) and macOS (Homebrew). All three teammates should be able to clone-and-go after this.

**Time budget:** ~30 minutes the first time, including downloads.

---

## 0. What you'll have at the end

- A local clone of the repo with `data/geo/` and `data/reference/` populated (~16 MB of GeoJSON + small CSVs)
- Python 3.12 venv with all data tools (DuckDB, GeoPandas, boto3, JupyterLab, …)
- AWS CLI configured for read/write on `s3://edth2026-baltic/` (~21 MB right now, growing to ~300 GB after AIS + Sentinel)
- A working notebook environment to inspect data

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

# Tools
brew install awscli python@3.12 git
```

Verify:
```bash
aws --version          # expect aws-cli/2.x
python3.12 --version   # expect Python 3.12.x
```

### Windows 11 (winget)

Open **PowerShell** (the regular one — not "PowerShell ISE").

```powershell
winget install -e --id Amazon.AWSCLI       --accept-source-agreements --accept-package-agreements
winget install -e --id Python.Python.3.12  --accept-source-agreements --accept-package-agreements
winget install -e --id Git.Git             --accept-source-agreements --accept-package-agreements
```

**Important:** close and reopen PowerShell after these, so the new PATH entries get picked up.

Verify:
```powershell
aws --version
python --version
```

If `python` opens the Microsoft Store: go to `Settings → Apps → Advanced app settings → App execution aliases` and turn off the Python aliases. Re-open PowerShell.

---

## 3. Get your AWS credentials

We use a shared AWS account (the user `edth2026-data`). Two options, in order of preference:

### Option A — your own IAM user (recommended)

Ask Alexis to create an IAM user for you in the AWS console: `edth2026-<your-name>` with the `AmazonS3FullAccess` policy attached. He sends you the access key + secret over a secure channel (1Password share, Signal, etc. — **not** Slack or email).

### Option B — shared `edth2026-data` user

Cheap and cheerful for the first weekend; rotate after. Alexis shares the keys over a secure channel.

### Wiring the keys

Once you have them, run:

```bash
aws configure
```

Paste in:

- AWS Access Key ID: `AKIA...`
- AWS Secret Access Key: `...`
- Default region name: **`eu-west-3`**
- Default output format: `json`

Verify:

```bash
aws sts get-caller-identity
aws s3 ls s3://edth2026-baltic/
```

You should see six top-level prefixes: `ais/`, `geo/`, `optical/`, `reference/`, `samples/`, `sar/`.

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

# Read a layer directly from S3 with DuckDB (no download)
python -c "import duckdb; con = duckdb.connect(); con.execute(\"INSTALL httpfs; LOAD httpfs; SET s3_region='eu-west-3'\"); print(con.execute(\"SELECT COUNT(*) FROM read_parquet('s3://edth2026-baltic/ais/parquet/year=2024/month=12/*.parquet') OR FROM read_json('s3://edth2026-baltic/geo/submarine_cables.geojson')\").fetchall())" 2>/dev/null || echo "AIS not loaded yet (Tasks 2-5 still pending)"

# Read a geo layer
python -c "import geopandas as gpd; gdf = gpd.read_file('data/geo/submarine_cables.geojson'); print('cables:', len(gdf), 'features')"
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
| `PLAN.md` | Project plan — read this if you haven't yet |
| `data/SOURCES.md` | Where every dataset comes from + license |
| `data/geo/*.geojson` | Criticality layers (small, committed) |
| `data/reference/*.csv` | Incidents + sanctions (small, committed) |
| `data/ais/`, `data/sar/`, `data/optical/` | Local mirrors of S3 big data (**gitignored**) |
| `scripts/common/` | Shared helpers (Baltic bbox, S3 constants) |
| `scripts/geo/` | Criticality layer scripts |
| `scripts/reference/` | Sanctions + reference data scripts |
| `scripts/ingest/` | AIS ingest pipelines (in progress) |
| `requirements.txt` | Python deps |
| `s3://edth2026-baltic/` | All data, including the large stuff |

## 8. Conventions

- **AWS region:** `eu-west-3` (Paris). Don't create buckets or resources elsewhere.
- **Baltic bbox:** lat 52°N–66°N, lon 9°E–30°E. Use `scripts.common.bbox.BALTIC_BBOX`.
- **Coordinates:** EPSG:4326 (WGS84) for storage, project to local UTM as needed.
- **Parquet partitioning:** `year=YYYY/month=MM/`.
- **Never commit:** `.env*`, raw AIS dumps, anything under `data/ais|sar|optical/`, your venv.
- **Always commit:** any code you wrote, GeoJSON layers under `data/geo/`, CSVs under `data/reference/`.

## 9. When something breaks

- **`aws` command not found** → reopen your terminal after installing
- **PowerShell can't activate venv** → see §4 ExecutionPolicy fix
- **pip resolver bouncing on s3fs/aiobotocore** → known. `pip install --force-reinstall --no-deps -r requirements.txt` and report what blew up
- **`Access Denied` on S3** → check your region is `eu-west-3` and `aws sts get-caller-identity` returns `edth2026-*`
- **Overpass API 504/429** → the OSM fetch script auto-falls-over to mirrors; if all fail, wait and retry

## 10. Optional but useful

- **VS Code** or **Cursor** with Python + Jupyter extensions
- **DBeaver** if you want a GUI for DuckDB / inspecting Parquet
- **QGIS** (free) for poking at GeoJSON visually — `brew install --cask qgis` or `winget install QGIS.QGIS`

---

When you've gone through these and the smoke tests pass, ping the team channel. If you got stuck somewhere, fix the doc as you go — it's better that the next person doesn't hit the same wall.
