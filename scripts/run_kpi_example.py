#!/usr/bin/env python3
"""Print a KPI comparison for the known Android checkout incident week."""

from datetime import date
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.kpi_engine import compare_periods
from src.database.connection import connect

with connect(read_only=True) as connection:
    comparison = compare_periods(
        connection,
        current_start=date(2026, 7, 20), current_end=date(2026, 7, 27),
        previous_start=date(2026, 7, 13), previous_end=date(2026, 7, 20),
    )

for metric, values in comparison.items():
    change = values["percent_change"]
    print(f"{metric:22} current={values['current']:.4f} previous={values['previous']:.4f} change={change:.1%}")
