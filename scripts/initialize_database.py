#!/usr/bin/env python3
"""Create the DuckDB analytics database and load all synthetic CSV tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import DEFAULT_DATABASE, connect

TABLE_LOAD_ORDER = [
    "customers", "campaigns", "sessions", "conversions", "funnel_events",
    "daily_campaign_metrics", "app_reviews", "experiments", "marketing_incidents",
    "metric_definitions", "anomaly_ground_truth",
]


def initialize(database: Path, source: Path, schema: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Synthetic data directory does not exist: {source}")
    database.parent.mkdir(parents=True, exist_ok=True)
    database.unlink(missing_ok=True)
    connection = connect(database)
    try:
        connection.execute(schema.read_text(encoding="utf-8"))
        connection.execute("BEGIN TRANSACTION")
        for table in TABLE_LOAD_ORDER:
            csv_path = (source / f"{table}.csv").resolve()
            if not csv_path.is_file():
                raise FileNotFoundError(f"Required data file is missing: {csv_path}")
            connection.execute(
                f"INSERT INTO {table} SELECT * FROM read_csv(?, header=true)", [str(csv_path)]
            )
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"{table}: {count:,} rows")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
    print(f"Database created: {database}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--source", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--schema", type=Path, default=Path("src/database/schema.sql"))
    args = parser.parse_args()
    initialize(args.database, args.source, args.schema)
