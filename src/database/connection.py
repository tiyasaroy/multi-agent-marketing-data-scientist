"""DuckDB connection helpers."""

from __future__ import annotations

from pathlib import Path

import duckdb

DEFAULT_DATABASE = Path("data/processed/marketing.duckdb")


def connect(database: Path | str = DEFAULT_DATABASE, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Open the project database, creating its parent directory when writable."""
    path = Path(database)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)
