"""Shared DuckDB helpers for the EDTH 2026 project.

- `connect()` returns a configured DuckDB with httpfs + S3 secret loaded.
- `query()` runs a SQL string with progress bar disabled (avoids cli spam).
"""
from __future__ import annotations

import configparser
import os
from pathlib import Path

import duckdb
import pandas as pd


def connect() -> duckdb.DuckDBPyConnection:
    """Connect, load httpfs, and create an S3 secret from ~/.aws/credentials."""
    cp = configparser.ConfigParser()
    cp.read(os.path.expanduser("~/.aws/credentials"))
    ak = cp["default"]["aws_access_key_id"]
    sk = cp["default"]["aws_secret_access_key"]

    con = duckdb.connect()
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    # Disable progress bar (spams stdout)
    con.execute("SET enable_progress_bar = false;")
    # Speed up S3 reads
    con.execute("SET s3_use_ssl = true;")
    con.execute(f"CREATE OR REPLACE SECRET (TYPE s3, KEY_ID '{ak}', SECRET '{sk}', REGION 'eu-west-3')")
    return con


def query(sql: str) -> pd.DataFrame:
    con = connect()
    try:
        return con.execute(sql).df()
    finally:
        con.close()
