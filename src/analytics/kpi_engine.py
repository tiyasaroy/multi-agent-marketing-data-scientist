"""Canonical revenue and conversion KPI calculations."""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb


KPI_SQL = """
SELECT
    COUNT(DISTINCT session_id) AS sessions,
    COUNT(DISTINCT conversion_id) AS conversions,
    COALESCE(SUM(revenue), 0) AS revenue,
    COUNT(DISTINCT customer_id) AS users,
    COALESCE(COUNT(DISTINCT conversion_id)::DOUBLE / NULLIF(COUNT(DISTINCT session_id), 0), 0) AS conversion_rate,
    COALESCE(SUM(revenue) / NULLIF(COUNT(DISTINCT conversion_id), 0), 0) AS average_order_value,
    COALESCE(SUM(revenue) / NULLIF(COUNT(DISTINCT session_id), 0), 0) AS revenue_per_session
FROM session_facts
WHERE timestamp >= ? AND timestamp < ?
"""


def period_kpis(connection: duckdb.DuckDBPyConnection, start: date, end: date) -> dict[str, Any]:
    """Calculate canonical KPIs for a half-open [start, end) period."""
    row = connection.execute(KPI_SQL, [start, end]).fetchone()
    columns = [item[0] for item in connection.description]
    return dict(zip(columns, row))


def compare_periods(
    connection: duckdb.DuckDBPyConnection,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
) -> dict[str, dict[str, float | int | None]]:
    """Return current, previous, absolute change, and percentage change per KPI."""
    current = period_kpis(connection, current_start, current_end)
    previous = period_kpis(connection, previous_start, previous_end)
    result = {}
    for metric, current_value in current.items():
        previous_value = previous[metric]
        absolute_change = current_value - previous_value
        percent_change = None if previous_value == 0 else absolute_change / previous_value
        result[metric] = {
            "current": current_value,
            "previous": previous_value,
            "absolute_change": absolute_change,
            "percent_change": percent_change,
        }
    return result
