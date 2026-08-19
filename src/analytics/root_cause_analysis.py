"""Evidence-backed root-cause ranking built from deterministic analyses."""

from __future__ import annotations

from datetime import date
from typing import Any

import duckdb

from .contribution_analysis import decompose_metric
from .funnel_analysis import compare_funnels
from .kpi_engine import compare_periods

DEFAULT_DIMENSIONS = ("device", "country", "channel", "campaign", "customer_segment")
DIMENSION_RELIABILITY = {
    "device": 1.00,
    "country": 0.85,
    "channel": 0.75,
    "campaign": 0.65,
    "customer_segment": 0.40,
}


def investigate_revenue_decline(
    connection: duckdb.DuckDBPyConnection,
    current_start: date,
    current_end: date,
    previous_start: date,
    previous_end: date,
) -> dict[str, Any]:
    """Investigate a revenue change and return traceable, ranked evidence."""
    kpis = compare_periods(connection, current_start, current_end, previous_start, previous_end)
    decompositions = {
        dimension: decompose_metric(
            connection, dimension, current_start, current_end, previous_start, previous_end
        )
        for dimension in DEFAULT_DIMENSIONS
    }
    overall_funnel = compare_funnels(
        connection, current_start, current_end, previous_start, previous_end
    )
    device_drivers = decompositions["device"]
    leading_device = device_drivers[0]["segment"] if device_drivers else None
    device_funnel = compare_funnels(
        connection, current_start, current_end, previous_start, previous_end,
        filter_dimension="device", filter_value=leading_device,
    ) if leading_device else []

    candidates = []
    for dimension, rows in decompositions.items():
        for rank, row in enumerate(rows[:3], start=1):
            contribution = row["contribution_share"] or 0.0
            if row["revenue_change"] >= 0:
                continue
            score = min(abs(contribution), 1.0) * 0.65
            score += 0.20 if row["statistically_significant"] else 0.0
            score += max(0.0, min(-row["conversion_rate_change"] * 2, 0.15))
            score *= DIMENSION_RELIABILITY[dimension]
            candidates.append({
                "candidate_type": "dimension_driver",
                "dimension": dimension,
                "segment": row["segment"],
                "rank_within_dimension": rank,
                "score": round(score, 4),
                "evidence": row,
            })
    for transition in device_funnel:
        if transition["absolute_change"] >= 0:
            continue
        score = min(abs(transition["percent_change"] or 0), 1.0) * 0.65
        score += 0.25 if transition["statistically_significant"] else 0.0
        candidates.append({
            "candidate_type": "funnel_driver",
            "dimension": "device",
            "segment": leading_device,
            "transition": f"{transition['from_step']} -> {transition['to_step']}",
            "score": round(score, 4),
            "evidence": transition,
        })
    candidates.sort(key=lambda item: item["score"], reverse=True)

    incidents = connection.execute(
        """
        SELECT incident_id, incident_date, title, root_cause, resolution, impact
        FROM marketing_incidents
        WHERE incident_date >= ? AND incident_date < ?
        ORDER BY incident_date
        """,
        [current_start, current_end],
    )
    incident_columns = [column[0] for column in incidents.description]
    incident_rows = [dict(zip(incident_columns, row)) for row in incidents.fetchall()]
    return {
        "question_type": "root_cause_analysis",
        "metric": "revenue",
        "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
        "previous_period": {"start": previous_start.isoformat(), "end_exclusive": previous_end.isoformat()},
        "kpis": kpis,
        "decompositions": decompositions,
        "overall_funnel": overall_funnel,
        "leading_device_funnel": device_funnel,
        "ranked_candidates": candidates,
        "related_incidents": incident_rows,
    }
