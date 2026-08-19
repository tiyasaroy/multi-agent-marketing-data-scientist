"""Deterministic review sentiment and negative-topic analysis."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, Mapping

import duckdb

from .scope import scope_identity

REVIEW_SCOPE_COLUMNS = {"device": "device", "country": "country"}
NEGATIVE_TOPIC = "payment/crash/login/refund"
NEGATIVE_TERMS = ("payment", "crash", "login", "refund")


def _review_scope_clause(scope: Mapping[str, str] | None) -> tuple[str, list[str]]:
    scope = scope or {}
    unsupported = set(scope) - set(REVIEW_SCOPE_COLUMNS)
    if unsupported:
        raise ValueError(f"Review analysis does not support scope dimensions: {sorted(unsupported)}")
    ordered = [(key, scope[key]) for key in REVIEW_SCOPE_COLUMNS if scope.get(key) is not None]
    if not ordered:
        return "", []
    return " AND " + " AND ".join(f"{REVIEW_SCOPE_COLUMNS[key]} = ?" for key, _ in ordered), [
        value for _, value in ordered
    ]


def period_review_metrics(
    connection: duckdb.DuckDBPyConnection, start: date, end: date,
    *, scope: Mapping[str, str] | None = None,
) -> dict[str, float]:
    filter_sql, values = _review_scope_clause(scope)
    reviews, negative, rating_sum = connection.execute(
        f"""
        SELECT COUNT(*), COUNT(*) FILTER (WHERE rating <= 2), COALESCE(SUM(rating), 0)
        FROM app_reviews
        WHERE timestamp >= ? AND timestamp < ?{filter_sql}
        """, [start, end, *values],
    ).fetchone()
    return {"reviews": float(reviews), "negative_reviews": float(negative),
            "negative_review_rate": negative / reviews if reviews else 0.0,
            "average_rating": rating_sum / reviews if reviews else 0.0}


def investigate_review_sentiment(
    connection: duckdb.DuckDBPyConnection, current_start: date, current_end: date,
    previous_start: date, previous_end: date, *, scope: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    applied_scope = dict(scope or {})
    current = period_review_metrics(connection, current_start, current_end, scope=applied_scope)
    previous = period_review_metrics(connection, previous_start, previous_end, scope=applied_scope)
    kpis = {}
    for name, current_value in current.items():
        previous_value = previous[name]
        change = current_value - previous_value
        key = "|".join(["review_kpi", name, current_start.isoformat(), current_end.isoformat(),
                        previous_start.isoformat(), previous_end.isoformat(), scope_identity(applied_scope)])
        kpis[name] = {"evidence_id": f"rev_{hashlib.sha256(key.encode()).hexdigest()[:12]}",
                      "current": current_value, "previous": previous_value, "absolute_change": change,
                      "percent_change": None if previous_value == 0 else change / previous_value}

    filter_sql, values = _review_scope_clause(applied_scope)
    term_sql = " OR ".join("LOWER(review_text) LIKE ?" for _ in NEGATIVE_TERMS)
    def topic_count(start: date, end: date) -> int:
        return connection.execute(
            f"""SELECT COUNT(*) FROM app_reviews
                WHERE timestamp >= ? AND timestamp < ? AND rating <= 2
                  AND ({term_sql}){filter_sql}""",
            [start, end, *[f"%{term}%" for term in NEGATIVE_TERMS], *values],
        ).fetchone()[0]
    current_topic = topic_count(current_start, current_end)
    previous_topic = topic_count(previous_start, previous_end)
    topic_change = current_topic - previous_topic
    topic_percent = None if previous_topic == 0 else topic_change / previous_topic
    driver_key = "|".join(["review_topic", NEGATIVE_TOPIC, current_start.isoformat(), current_end.isoformat(),
                           previous_start.isoformat(), previous_end.isoformat(), scope_identity(applied_scope)])
    candidate = {"evidence_id": f"top_{hashlib.sha256(driver_key.encode()).hexdigest()[:12]}",
                 "candidate_type": "dimension_driver", "dimension": "topic", "segment": NEGATIVE_TOPIC,
                 "rank_within_dimension": 1, "score": min(abs(topic_percent or 0), 1.0),
                 "evidence": {"metric": "negative_reviews", "current": current_topic,
                              "previous": previous_topic, "absolute_change": topic_change,
                              "percent_change": topic_percent, "terms": list(NEGATIVE_TERMS),
                              "applied_scope": applied_scope}}

    rows = connection.execute(
        """SELECT scenario_id, start_date, affected_dimension, root_cause, severity
           FROM anomaly_ground_truth
           WHERE start_date < ? AND end_date >= ? AND affected_metric = 'negative_review_rate'
           ORDER BY start_date""", [current_end, current_start],
    ).fetchall()
    incidents = [{"evidence_id": f"gt_{scenario_id}_{hashlib.sha256(scope_identity(applied_scope).encode()).hexdigest()[:8]}",
                  "incident_id": scenario_id, "incident_date": incident_date,
                  "title": f"Review anomaly for {affected_dimension}", "root_cause": root_cause,
                  "resolution": "No resolution recorded in anomaly ground truth", "impact": severity.title()}
                 for scenario_id, incident_date, affected_dimension, root_cause, severity in rows]
    return {"question_type": "sentiment_analysis", "metric": "negative_review_rate",
            "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "previous_period": {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat()},
            "applied_scope": applied_scope, "kpis": kpis, "decompositions": {}, "overall_funnel": [],
            "leading_device_funnel": [], "ranked_candidates": [candidate], "related_incidents": incidents}
