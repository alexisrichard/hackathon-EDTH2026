# scripts/

Data-prep code for the EDTH 2026 maritime cueing project.

## Layout

- `common/` — shared helpers (Baltic bbox constants, DuckDB conn over local parquet, schema definitions). `sync_from_s3.py` is **retired** — a no-op that prints the public-source rebuild command for each layer (the old `s3://edth2026-baltic/` bucket has been deleted).
- `geo/` — criticality layer compilation (cables, pipelines, ports, naval bases, etc.). Output → `data/geo/*.geojson` (small, committed).
- `ingest/` — AIS ingest pipelines (Danish, Finnish, Norwegian). Output → local `data/ais/parquet/` (large, NOT committed; regenerable from the public Danish feed `aisdata.ais.dk` — see [`../DATA_GUIDE.md`](../DATA_GUIDE.md)).
- `reference/` — sanctions, shadow-fleet, vessel registry, incident timeline. Output → `data/reference/*.csv` (small, committed) or larger files under local `data/`.

## Conventions

- All scripts assume the project root as the working directory.
- No AWS account required: the Danish AIS feed (`aisdata.ais.dk`) is read anonymously, and output is written locally to `data/`. AWS credentials are only needed if you opt into mirroring parquet to your own bucket (`EDTH_UPLOAD_S3=1`).
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
