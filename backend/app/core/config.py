"""Backend configuration — env-driven, with mock as the safe default.

The one knob that matters is ``DATA_SOURCE`` (``mock`` | ``duckdb``). Mock is the
default so the API runs with zero AWS / network setup — the frontend can develop
against it immediately (mock-first philosophy, PLAN §10.3).
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel

import app.core.paths  # noqa: F401  (side-effect: puts repo root on sys.path)
from scripts.common.bbox import BALTIC_BBOX, S3_BUCKET, S3_REGION

VERSION = "0.1.0"


class Settings(BaseModel):
    """Resolved runtime settings (read once from the environment)."""

    data_source: str = "mock"
    # Root of the AIS parquet dataset. Defaults to the LOCAL path produced by
    # ``scripts/ingest/danish_ais.py`` — the S3 bucket (``edth2026-baltic``) is
    # retired. May be overridden with ``AIS_PARQUET_ROOT``; an ``s3://...`` root
    # still works (the duckdb source creates an S3 secret only for s3:// roots).
    ais_parquet_root: str = os.environ.get("AIS_PARQUET_ROOT", "data/ais/parquet")
    # S3 identifiers, retained only for reference (no longer the default data
    # path). ``edth2026-baltic`` / ``eu-west-3`` are retired.
    s3_bucket: str = S3_BUCKET
    s3_region: str = S3_REGION
    baltic_bbox: dict = BALTIC_BBOX
    cors_allow_origins: list[str] = ["*"]  # hackathon dev; tighten for prod

    @property
    def is_s3_root(self) -> bool:
        """True when the parquet root points at S3 (``s3://...``)."""
        return self.ais_parquet_root.startswith("s3://")

    @property
    def ais_glob(self) -> str:
        """Full glob for the AIS parquet dataset (all partitions).

        Built from ``ais_parquet_root`` — LOCAL by default, e.g.
        ``data/ais/parquet/source=danish/year=*/month=*/day=*/*.parquet``.
        """
        root = self.ais_parquet_root.rstrip("/")
        return f"{root}/source=danish/year=*/month=*/day=*/*.parquet"

    def ais_day_glob(self, year: int, month: int, day: int) -> str:
        """Glob for a single day's AIS parquet partition (under the parquet root)."""
        root = self.ais_parquet_root.rstrip("/")
        return (
            f"{root}/source=danish"
            f"/year={year:04d}/month={month:02d}/day={day:02d}/*.parquet"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load settings from the environment (cached)."""
    return Settings(
        data_source=os.getenv("DATA_SOURCE", "mock").strip().lower(),
        cors_allow_origins=[
            o.strip()
            for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
            if o.strip()
        ],
    )
