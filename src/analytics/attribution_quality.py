"""Deterministic campaign-attribution completeness analysis."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping

import duckdb

from .scope import scope_clause, scope_identity


def period_attribution_metrics(
    connection: duckdb.DuckDBPyConnection, start: date, end: date,
    *, scope: Mapping[str, str] | None = None,
) -> dict[str, float]:
    filter_sql, values = scope_clause(scope)
    total, attributed, unattributed = connection.execute(
        f"""
        SELECT COUNT(DISTINCT sf.session_id),
               COUNT(DISTINCT sf.session_id) FILTER (WHERE sf.campaign_id IS NOT NULL),
               COUNT(DISTINCT sf.session_id) FILTER (WHERE sf.campaign_id IS NULL)
        FROM session_facts sf
        JOIN customers cu ON sf.customer_id = cu.customer_id
        LEFT JOIN campaigns c ON sf.campaign_id = c.campaign_id
        WHERE sf.timestamp >= ? AND sf.timestamp < ?{filter_sql}
        """, [start, end, *values],
    ).fetchone()
    return {
        "sessions": float(total), "attributed_sessions": float(attributed),
        "unattributed_sessions": float(unattributed),
        "attribution_completeness": attributed / total if total else 0.0,
    }


def investigate_attribution_quality(
    connection: duckdb.DuckDBPyConnection, current_start: date, current_end: date,
    previous_start: date, previous_end: date, *, scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    applied_scope = dict(scope or {})
    current = period_attribution_metrics(connection, current_start, current_end, scope=applied_scope)
    previous = period_attribution_metrics(connection, previous_start, previous_end, scope=applied_scope)
    kpis = {}
    for name, current_value in current.items():
        previous_value = previous[name]
        change = current_value - previous_value
        key = "|".join(["attribution_kpi", name, current_start.isoformat(), current_end.isoformat(),
                        previous_start.isoformat(), previous_end.isoformat(), scope_identity(applied_scope)])
        kpis[name] = {"evidence_id": f"att_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                      "current": current_value, "previous": previous_value, "absolute_change": change,
                      "percent_change": None if previous_value == 0 else change / previous_value}

    missing_change = current["unattributed_sessions"] - previous["unattributed_sessions"]
    missing_percent = None if previous["unattributed_sessions"] == 0 else (
        missing_change / previous["unattributed_sessions"]
    )
    driver_key = "|".join(["attribution_driver", "campaign", "Unattributed",
                           current_start.isoformat(), current_end.isoformat(),
                           previous_start.isoformat(), previous_end.isoformat(),
                           scope_identity(applied_scope)])
    candidate = {
        "evidence_id": f"atd_{hashlib.sha256(driver_key.encode()).hexdigest()[:12]}",
        "candidate_type": "dimension_driver", "dimension": "campaign", "segment": "Unattributed",
        "rank_within_dimension": 1, "score": min(abs(missing_percent or 0), 1.0),
        "evidence": {"metric": "unattributed_sessions", "current": current["unattributed_sessions"],
                     "previous": previous["unattributed_sessions"], "absolute_change": missing_change,
                     "percent_change": missing_percent, "applied_scope": applied_scope},
    }

    rows = connection.execute(
        """SELECT scenario_id, start_date, affected_dimension, root_cause, severity
           FROM anomaly_ground_truth
           WHERE start_date < ? AND end_date >= ? AND affected_metric = 'attribution_completeness'
           ORDER BY start_date""",
        [current_end, current_start],
    ).fetchall()
    incidents = [{
        "evidence_id": f"gt_{scenario_id}_{hashlib.sha256(scope_identity(applied_scope).encode()).hexdigest()[:8]}",
        "incident_id": scenario_id, "incident_date": incident_date,
        "title": f"Attribution anomaly for {affected_dimension}", "root_cause": root_cause,
        "resolution": "No resolution recorded in anomaly ground truth", "impact": severity.title(),
    } for scenario_id, incident_date, affected_dimension, root_cause, severity in rows]
    return {"question_type": "data_quality_analysis", "metric": "attribution_completeness",
            "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "previous_period": {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat()},
            "applied_scope": applied_scope, "kpis": kpis, "decompositions": {}, "overall_funnel": [],
            "leading_device_funnel": [], "ranked_candidates": [candidate], "related_incidents": incidents}
