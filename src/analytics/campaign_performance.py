"""Deterministic campaign KPI comparisons and evidence-backed driver ranking."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping

import duckdb

from .scope import scope_identity

CAMPAIGN_SCOPE_COLUMNS = {
    "channel": "c.channel",
    "campaign": "c.campaign_name",
}


def _scope_clause(scope: Mapping[str, str] | None) -> tuple[str, list[str]]:
    relevant = {key: value for key, value in (scope or {}).items() if key in CAMPAIGN_SCOPE_COLUMNS}
    unsupported = set(scope or {}) - set(CAMPAIGN_SCOPE_COLUMNS)
    if unsupported:
        raise ValueError(f"Campaign analysis does not support scope dimensions: {sorted(unsupported)}")
    if not relevant:
        return "", []
    ordered = [(key, relevant[key]) for key in CAMPAIGN_SCOPE_COLUMNS if key in relevant]
    return " AND " + " AND ".join(f"{CAMPAIGN_SCOPE_COLUMNS[key]} = ?" for key, _ in ordered), [
        value for _, value in ordered
    ]


def _metrics(row: tuple) -> dict[str, float]:
    impressions, clicks, spend, conversions, revenue = row
    return {
        "impressions": float(impressions), "clicks": float(clicks), "spend": float(spend),
        "conversions": float(conversions), "revenue": float(revenue),
        "ctr": clicks / impressions if impressions else 0.0,
        "cpc": spend / clicks if clicks else 0.0,
        "cpa": spend / conversions if conversions else 0.0,
        "roas": revenue / spend if spend else 0.0,
        "conversion_rate": conversions / clicks if clicks else 0.0,
    }


def period_campaign_kpis(connection: duckdb.DuckDBPyConnection, start: date, end: date, *, scope=None):
    filter_sql, values = _scope_clause(scope)
    row = connection.execute(
        f"""
        SELECT COALESCE(SUM(d.impressions), 0), COALESCE(SUM(d.clicks), 0),
               COALESCE(SUM(d.spend), 0), COALESCE(SUM(d.conversions), 0),
               COALESCE(SUM(d.revenue), 0)
        FROM daily_campaign_metrics d JOIN campaigns c USING (campaign_id)
        WHERE d.date >= ? AND d.date < ?{filter_sql}
        """,
        [start, end, *values],
    ).fetchone()
    return _metrics(row)


def investigate_campaign_performance(
    connection: duckdb.DuckDBPyConnection, current_start: date, current_end: date,
    previous_start: date, previous_end: date, *, metric: str, scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    applied_scope = dict(scope or {})
    current = period_campaign_kpis(connection, current_start, current_end, scope=applied_scope)
    previous = period_campaign_kpis(connection, previous_start, previous_end, scope=applied_scope)
    kpis = {}
    for name, current_value in current.items():
        previous_value = previous[name]
        change = current_value - previous_value
        key = "|".join(["campaign_kpi", name, current_start.isoformat(), current_end.isoformat(),
                        previous_start.isoformat(), previous_end.isoformat(), scope_identity(applied_scope)])
        kpis[name] = {"evidence_id": f"cmp_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                      "current": current_value, "previous": previous_value,
                      "absolute_change": change,
                      "percent_change": None if previous_value == 0 else change / previous_value}

    candidates = []
    dimensions = [next(iter(applied_scope))] if applied_scope else ["channel", "campaign"]
    for dimension in dimensions:
        expression = CAMPAIGN_SCOPE_COLUMNS[dimension]
        rows = connection.execute(
            f"""
            SELECT DISTINCT {expression}
            FROM daily_campaign_metrics d JOIN campaigns c USING (campaign_id)
            WHERE d.date >= ? AND d.date < ?
            """, [previous_start, current_end]
        ).fetchall()
        for (segment,) in rows:
            segment_scope = {**applied_scope, dimension: segment}
            cur = period_campaign_kpis(connection, current_start, current_end, scope=segment_scope)[metric]
            prev = period_campaign_kpis(connection, previous_start, previous_end, scope=segment_scope)[metric]
            change = cur - prev
            percent = None if prev == 0 else change / prev
            key = "|".join(["campaign_driver", metric, dimension, segment, current_start.isoformat(),
                            current_end.isoformat(), previous_start.isoformat(), previous_end.isoformat(),
                            scope_identity(applied_scope)])
            candidates.append({
                "evidence_id": f"drv_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                "candidate_type": "dimension_driver", "dimension": dimension, "segment": segment,
                "rank_within_dimension": None, "score": 1.0 if applied_scope.get(dimension) == segment else min(abs(percent or 0), 1.0),
                "evidence": {"metric": metric, "current": cur, "previous": prev,
                             "absolute_change": change, "percent_change": percent,
                             "applied_scope": segment_scope},
            })
    candidates.sort(key=lambda item: item["score"], reverse=True)
    for index, candidate in enumerate(candidates, start=1):
        candidate["rank_within_dimension"] = index

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
    return {"question_type": "campaign_performance_analysis", "metric": metric,
            "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "previous_period": {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat()},
            "applied_scope": applied_scope, "kpis": kpis, "decompositions": {}, "overall_funnel": [],
            "leading_device_funnel": [], "ranked_candidates": candidates, "related_incidents": incidents}
