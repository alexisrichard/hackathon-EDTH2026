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
    s3_bucket: str = S3_BUCKET
    s3_region: str = S3_REGION
    # AIS parquet prefix template, partitioned year/month/day (AGENTS.md §2).
    ais_prefix: str = "ais/parquet/source=danish"
    baltic_bbox: dict = BALTIC_BBOX
    cors_allow_origins: list[str] = ["*"]  # hackathon dev; tighten for prod

    @property
    def ais_glob(self) -> str:
        """Full s3:// glob for the AIS parquet dataset (all partitions)."""
        return f"s3://{self.s3_bucket}/{self.ais_prefix}/year=*/month=*/day=*/*.parquet"

    def ais_day_glob(self, year: int, month: int, day: int) -> str:
        """s3:// glob for a single day's AIS parquet partition."""
        return (
            f"s3://{self.s3_bucket}/{self.ais_prefix}"
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
