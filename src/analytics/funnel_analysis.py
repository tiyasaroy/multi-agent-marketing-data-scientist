"""Conversion funnel comparison across two periods."""

from __future__ import annotations

import math
import hashlib
from datetime import date
from typing import Any

import duckdb

FUNNEL_STEPS = [
    "landing_page", "product_view", "add_to_cart", "checkout_started",
    "payment_started", "purchase_completed",
]
FILTERS = {"device": "s.device", "country": "s.country", "channel": "s.traffic_source"}


def _p_value(success_a: int, total_a: int, success_b: int, total_b: int) -> float | None:
    if not total_a or not total_b:
        return None
    pooled = (success_a + success_b) / (total_a + total_b)
    error = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if error == 0:
        return 1.0
    z_score = (success_a / total_a - success_b / total_b) / error
    return math.erfc(abs(z_score) / math.sqrt(2))


def _counts(
    connection: duckdb.DuckDBPyConnection,
    start: date,
    end: date,
    filter_dimension: str | None,
    filter_value: str | None,
) -> dict[str, int]:
    filter_sql = ""
    parameters: list[Any] = [start, end]
    if filter_dimension is not None:
        if filter_dimension not in FILTERS:
            raise ValueError(f"Unsupported funnel filter: {filter_dimension!r}")
        if filter_value is None:
            raise ValueError("filter_value is required when filter_dimension is provided")
        filter_sql = f" AND {FILTERS[filter_dimension]} = ?"
        parameters.append(filter_value)
    rows = connection.execute(
        f"""
        SELECT fe.event_name, COUNT(DISTINCT fe.session_id) AS sessions
        FROM funnel_events fe
        JOIN sessions s USING (session_id)
        WHERE s.timestamp >= ? AND s.timestamp < ? {filter_sql}
        GROUP BY fe.event_name
        """,
        parameters,
    ).fetchall()
    return dict(rows)


def compare_funnels(
    connection: duckdb.DuckDBPyConnection,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
    *,
    filter_dimension: str | None = None,
    filter_value: str | None = None,
) -> list[dict[str, Any]]:
    """Compare sequential funnel transition rates between two periods."""
    current = _counts(connection, current_start, current_end, filter_dimension, filter_value)
    previous = _counts(connection, previous_start, previous_end, filter_dimension, filter_value)
    transitions = []
    for from_step, to_step in zip(FUNNEL_STEPS, FUNNEL_STEPS[1:]):
        current_from, current_to = current.get(from_step, 0), current.get(to_step, 0)
        previous_from, previous_to = previous.get(from_step, 0), previous.get(to_step, 0)
        current_rate = current_to / current_from if current_from else 0.0
        previous_rate = previous_to / previous_from if previous_from else 0.0
        p_value = _p_value(current_to, current_from, previous_to, previous_from)
        evidence_key = "|".join([
            "funnel", from_step, to_step, filter_dimension or "all", filter_value or "all",
            current_start.isoformat(), current_end.isoformat(),
            previous_start.isoformat(), previous_end.isoformat(),
        ])
        transitions.append({
            "evidence_id": f"fun_{hashlib.sha256(evidence_key.encode()).hexdigest()[:12]}",
            "from_step": from_step,
            "to_step": to_step,
            "current_from_sessions": current_from,
            "current_to_sessions": current_to,
            "previous_from_sessions": previous_from,
            "previous_to_sessions": previous_to,
            "current_rate": current_rate,
            "previous_rate": previous_rate,
            "absolute_change": current_rate - previous_rate,
            "percent_change": None if previous_rate == 0 else (current_rate - previous_rate) / previous_rate,
            "p_value": p_value,
            "statistically_significant": p_value is not None and p_value < 0.05,
            "filter_dimension": filter_dimension,
            "filter_value": filter_value,
        })
    return transitions
