"""Dimension-level KPI decomposition and contribution calculations."""

from __future__ import annotations

import math
import hashlib
from datetime import date
from typing import Any, Mapping

import duckdb

from .scope import scope_clause, scope_identity

DIMENSIONS = {
    "device": "sf.device",
    "country": "sf.country",
    "channel": "sf.traffic_source",
    "campaign": "COALESCE(c.campaign_name, 'Unattributed')",
    "customer_segment": "cu.customer_segment",
    "product": "COALESCE(sf.product_id, 'No purchase')",
}


def _two_proportion_p_value(success_a: int, total_a: int, success_b: int, total_b: int) -> float | None:
    """Return the two-sided pooled two-proportion z-test p-value."""
    if total_a == 0 or total_b == 0:
        return None
    pooled = (success_a + success_b) / (total_a + total_b)
    standard_error = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if standard_error == 0:
        return 1.0
    z_score = (success_a / total_a - success_b / total_b) / standard_error
    return math.erfc(abs(z_score) / math.sqrt(2))


def decompose_metric(
    connection: duckdb.DuckDBPyConnection,
    dimension: str,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
    *,
    scope: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Decompose revenue change by an approved business dimension."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unsupported dimension {dimension!r}; choose from {sorted(DIMENSIONS)}")
    expression = DIMENSIONS[dimension]
    filter_sql, filter_parameters = scope_clause(scope)
    query = f"""
        WITH grouped AS (
            SELECT
                {expression} AS segment,
                CASE
                    WHEN sf.timestamp >= ? AND sf.timestamp < ? THEN 'current'
                    WHEN sf.timestamp >= ? AND sf.timestamp < ? THEN 'previous'
                END AS period,
                COUNT(DISTINCT sf.session_id) AS sessions,
                COUNT(DISTINCT sf.conversion_id) AS conversions,
                COALESCE(SUM(sf.revenue), 0) AS revenue
            FROM session_facts sf
            JOIN customers cu USING (customer_id)
            LEFT JOIN campaigns c ON sf.campaign_id = c.campaign_id
            WHERE ((sf.timestamp >= ? AND sf.timestamp < ?)
               OR (sf.timestamp >= ? AND sf.timestamp < ?)){filter_sql}
            GROUP BY segment, period
        )
        SELECT
            segment,
            COALESCE(MAX(sessions) FILTER (WHERE period = 'current'), 0) AS current_sessions,
            COALESCE(MAX(sessions) FILTER (WHERE period = 'previous'), 0) AS previous_sessions,
            COALESCE(MAX(conversions) FILTER (WHERE period = 'current'), 0) AS current_conversions,
            COALESCE(MAX(conversions) FILTER (WHERE period = 'previous'), 0) AS previous_conversions,
            COALESCE(MAX(revenue) FILTER (WHERE period = 'current'), 0) AS current_revenue,
            COALESCE(MAX(revenue) FILTER (WHERE period = 'previous'), 0) AS previous_revenue
        FROM grouped
        GROUP BY segment
    """
    parameters = [current_start, current_end, previous_start, previous_end,
                  current_start, current_end, previous_start, previous_end, *filter_parameters]
    result = connection.execute(query, parameters)
    columns = [item[0] for item in result.description]
    raw_rows = [dict(zip(columns, row)) for row in result.fetchall()]
    total_change = sum(row["current_revenue"] - row["previous_revenue"] for row in raw_rows)

    rows = []
    for row in raw_rows:
        current_rate = row["current_conversions"] / row["current_sessions"] if row["current_sessions"] else 0.0
        previous_rate = row["previous_conversions"] / row["previous_sessions"] if row["previous_sessions"] else 0.0
        revenue_change = row["current_revenue"] - row["previous_revenue"]
        previous_revenue = row["previous_revenue"]
        p_value = _two_proportion_p_value(
            row["current_conversions"], row["current_sessions"],
            row["previous_conversions"], row["previous_sessions"],
        )
        evidence_key = "|".join([
            "dimension", dimension, str(row["segment"]),
            current_start.isoformat(), current_end.isoformat(),
            previous_start.isoformat(), previous_end.isoformat(),
            scope_identity(scope),
        ])
        rows.append({
            "evidence_id": f"dim_{hashlib.sha256(evidence_key.encode()).hexdigest()[:12]}",
            "metric": "revenue",
            "dimension": dimension,
            "segment": row["segment"],
            **row,
            "revenue_change": revenue_change,
            "revenue_percent_change": None if previous_revenue == 0 else revenue_change / previous_revenue,
            "contribution_share": None if total_change == 0 else revenue_change / total_change,
            "current_conversion_rate": current_rate,
            "previous_conversion_rate": previous_rate,
            "conversion_rate_change": current_rate - previous_rate,
            "conversion_rate_p_value": p_value,
            "statistically_significant": p_value is not None and p_value < 0.05,
        })
    rows.sort(key=lambda item: item["revenue_change"], reverse=total_change >= 0)
    return rows
