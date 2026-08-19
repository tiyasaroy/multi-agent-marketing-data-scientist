"""Canonical revenue and conversion KPI calculations."""

from __future__ import annotations

from datetime import date
from typing import Any
from typing import Mapping

import duckdb

from .scope import scope_clause


KPI_SQL = """
SELECT
    COUNT(DISTINCT sf.session_id) AS sessions,
    COUNT(DISTINCT sf.conversion_id) AS conversions,
    COALESCE(SUM(sf.revenue), 0) AS revenue,
    COUNT(DISTINCT sf.customer_id) AS users,
    COALESCE(COUNT(DISTINCT sf.conversion_id)::DOUBLE / NULLIF(COUNT(DISTINCT sf.session_id), 0), 0) AS conversion_rate,
    COALESCE(SUM(sf.revenue) / NULLIF(COUNT(DISTINCT sf.conversion_id), 0), 0) AS average_order_value,
    COALESCE(SUM(sf.revenue) / NULLIF(COUNT(DISTINCT sf.session_id), 0), 0) AS revenue_per_session
FROM session_facts sf
JOIN customers cu ON sf.customer_id = cu.customer_id
LEFT JOIN campaigns c ON sf.campaign_id = c.campaign_id
WHERE sf.timestamp >= ? AND sf.timestamp < ? {scope_sql}
"""


def period_kpis(connection: duckdb.DuckDBPyConnection, start: date, end: date, *, scope: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Calculate canonical KPIs for a half-open [start, end) period."""
    filter_sql, filter_parameters = scope_clause(scope)
    row = connection.execute(KPI_SQL.format(scope_sql=filter_sql), [start, end, *filter_parameters]).fetchone()
    columns = [item[0] for item in connection.description]
    return dict(zip(columns, row))


def compare_periods(
    connection: duckdb.DuckDBPyConnection,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
    *,
    scope: Mapping[str, str] | None = None,
) -> dict[str, dict[str, float | int | None]]:
    """Return current, previous, absolute change, and percentage change per KPI."""
    current = period_kpis(connection, current_start, current_end, scope=scope)
    previous = period_kpis(connection, previous_start, previous_end, scope=scope)
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
