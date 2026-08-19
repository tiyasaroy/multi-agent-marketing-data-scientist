"""Deterministic traffic comparisons and dimensional driver analysis."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping

import duckdb

from .scope import scope_clause, scope_identity

TRAFFIC_DIMENSIONS = {
    "channel": "sf.traffic_source",
    "device": "sf.device",
    "country": "sf.country",
    "landing_page": "sf.landing_page",
}


def period_traffic_kpis(
    connection: duckdb.DuckDBPyConnection, start: date, end: date,
    *, scope: Mapping[str, str] | None = None,
) -> dict[str, float]:
    filter_sql, values = scope_clause(scope)
    sessions, users = connection.execute(
        f"""
        SELECT COUNT(DISTINCT sf.session_id), COUNT(DISTINCT sf.customer_id)
        FROM session_facts sf
        JOIN customers cu ON sf.customer_id = cu.customer_id
        LEFT JOIN campaigns c ON sf.campaign_id = c.campaign_id
        WHERE sf.timestamp >= ? AND sf.timestamp < ?{filter_sql}
        """, [start, end, *values],
    ).fetchone()
    return {"sessions": float(sessions), "users": float(users)}


def _dimension_rows(
    connection: duckdb.DuckDBPyConnection, dimension: str,
    current_start: date, current_end: date, previous_start: date, previous_end: date,
    scope: Mapping[str, str],
) -> list[dict[str, Any]]:
    expression = TRAFFIC_DIMENSIONS[dimension]
    filter_sql, values = scope_clause(scope)
    rows = connection.execute(
        f"""
        WITH grouped AS (
            SELECT {expression} AS segment,
                   CASE WHEN sf.timestamp >= ? AND sf.timestamp < ? THEN 'current' ELSE 'previous' END AS period,
                   COUNT(DISTINCT sf.session_id) AS sessions
            FROM session_facts sf
            JOIN customers cu ON sf.customer_id = cu.customer_id
            LEFT JOIN campaigns c ON sf.campaign_id = c.campaign_id
            WHERE ((sf.timestamp >= ? AND sf.timestamp < ?)
                OR (sf.timestamp >= ? AND sf.timestamp < ?)){filter_sql}
            GROUP BY segment, period
        )
        SELECT segment,
               COALESCE(MAX(sessions) FILTER (WHERE period='current'), 0),
               COALESCE(MAX(sessions) FILTER (WHERE period='previous'), 0)
        FROM grouped GROUP BY segment
        """,
        [current_start, current_end, current_start, current_end,
         previous_start, previous_end, *values],
    ).fetchall()
    evidence = []
    for segment, current, previous in rows:
        change = current - previous
        percent = None if previous == 0 else change / previous
        key = "|".join(["traffic_driver", dimension, str(segment), current_start.isoformat(),
                        current_end.isoformat(), previous_start.isoformat(), previous_end.isoformat(),
                        scope_identity(scope)])
        evidence.append({"evidence_id": f"trf_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                         "dimension": dimension, "segment": segment, "current": current,
                         "previous": previous, "absolute_change": change, "percent_change": percent})
    return evidence


def investigate_traffic_change(
    connection: duckdb.DuckDBPyConnection, current_start: date, current_end: date,
    previous_start: date, previous_end: date, *, metric: str = "sessions",
    scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    applied_scope = dict(scope or {})
    current = period_traffic_kpis(connection, current_start, current_end, scope=applied_scope)
    previous = period_traffic_kpis(connection, previous_start, previous_end, scope=applied_scope)
    kpis = {}
    for name in ("sessions", "users"):
        change = current[name] - previous[name]
        key = "|".join(["traffic_kpi", name, current_start.isoformat(), current_end.isoformat(),
                        previous_start.isoformat(), previous_end.isoformat(), scope_identity(applied_scope)])
        kpis[name] = {"evidence_id": f"trk_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                      "current": current[name], "previous": previous[name], "absolute_change": change,
                      "percent_change": None if previous[name] == 0 else change / previous[name]}

    candidates = []
    for dimension in TRAFFIC_DIMENSIONS:
        for row in _dimension_rows(
            connection, dimension, current_start, current_end, previous_start, previous_end, applied_scope
        ):
            if row["absolute_change"] >= 0:
                continue
            score = min(abs(row["percent_change"] or 0), 1.0)
            if applied_scope.get(dimension) == row["segment"]:
                score = 1.0
            candidates.append({"evidence_id": row["evidence_id"], "candidate_type": "dimension_driver",
                               "dimension": dimension, "segment": row["segment"], "score": score,
                               "evidence": row})
    candidates.sort(key=lambda item: item["score"], reverse=True)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["rank_within_dimension"] = rank

    scoped_dimensions = [f"{key}={value}" for key, value in applied_scope.items()]
    incidents = []
    if scoped_dimensions:
        rows = connection.execute(
            """SELECT scenario_id, start_date, affected_dimension, root_cause, severity
               FROM anomaly_ground_truth
               WHERE start_date < ? AND end_date >= ? AND affected_dimension IN (SELECT UNNEST(?))""",
            [current_end, current_start, scoped_dimensions],
        ).fetchall()
        for scenario_id, incident_date, affected_dimension, root_cause, severity in rows:
            incidents.append({"evidence_id": f"gt_{scenario_id}_{hashlib.sha256(scope_identity(applied_scope).encode()).hexdigest()[:8]}",
                              "incident_id": scenario_id, "incident_date": incident_date,
                              "title": f"Scoped anomaly for {affected_dimension}", "root_cause": root_cause,
                              "resolution": "No resolution recorded in anomaly ground truth", "impact": severity.title()})
    return {"question_type": "traffic_analysis", "metric": metric,
            "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "previous_period": {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat()},
            "applied_scope": applied_scope, "kpis": kpis, "decompositions": {}, "overall_funnel": [],
            "leading_device_funnel": [], "ranked_candidates": candidates, "related_incidents": incidents}
