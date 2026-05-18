# scripts/

Data-prep code for the EDTH 2026 maritime cueing project.

## Layout

- `common/` — shared helpers (S3 client, Baltic bbox constants, schema definitions).
- `geo/` — criticality layer compilation (cables, pipelines, ports, naval bases, etc.). Output → `data/geo/*.geojson` (small, committed).
- `ingest/` — AIS ingest pipelines (Danish, Finnish, Norwegian). Output → `s3://edth2026-baltic/ais/parquet/` (large, NOT committed).
- `reference/` — sanctions, shadow-fleet, vessel registry, incident timeline. Output → `data/reference/*.csv` (small, committed) or S3 if larger.

## Conventions

- All scripts assume the project root as the working directory.
- AWS credentials read from `~/.aws/credentials` (profile: `default`).
- Baltic bounding box: lat 52°N–66°N, lon 9°E–30°E. Imported from `scripts.common.bbox`.
- Output Parquet partitioned by `year=YYYY/month=MM/`.
- Coordinates: EPSG:4326 (WGS84) for storage, project to local UTM when needed for analysis.

## Running

```powershell
# One-time setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Then any script:
python scripts/geo/build_cables.py
```
