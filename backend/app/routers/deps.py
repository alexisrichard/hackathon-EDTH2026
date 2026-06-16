"""Shared FastAPI dependencies for the routers."""

from __future__ import annotations

from app.data import DataSource, get_data_source


def data_source() -> DataSource:
    """FastAPI dependency that yields the configured :class:`DataSource`."""
    return get_data_source()
