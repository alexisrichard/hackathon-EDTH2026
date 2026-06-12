"""Data-access layer: the :class:`DataSource` interface + its implementations.

``get_data_source()`` is the factory the API depends on; it picks the
implementation from ``DATA_SOURCE`` (default ``mock``) and caches a singleton.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.data.base import DataSource


@lru_cache(maxsize=1)
def get_data_source() -> DataSource:
    """Return the configured DataSource singleton (mock unless DATA_SOURCE=duckdb)."""
    settings = get_settings()
    if settings.data_source == "duckdb":
        # Imported lazily so a mock-only run never imports duckdb/boto3.
        from app.data.duckdb_source import DuckDBDataSource

        return DuckDBDataSource()
    # Default: mock (also the fallback for any unrecognized value).
    from app.data.mock import MockDataSource

    return MockDataSource()


__all__ = ["DataSource", "get_data_source"]
