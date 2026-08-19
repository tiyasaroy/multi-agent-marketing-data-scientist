"""Deterministic control-versus-treatment experiment analysis."""

from __future__ import annotations

import hashlib
import math
from datetime import date
from statistics import NormalDist
from typing import Any

import duckdb


def _two_proportion_test(control_success: int, control_total: int, treatment_success: int, treatment_total: int):
    control_rate = control_success / control_total if control_total else 0.0
    treatment_rate = treatment_success / treatment_total if treatment_total else 0.0
    difference = treatment_rate - control_rate
    pooled = (control_success + treatment_success) / (control_total + treatment_total)
    null_se = math.sqrt(pooled * (1 - pooled) * (1 / control_total + 1 / treatment_total))
    p_value = math.erfc(abs(difference / null_se) / math.sqrt(2)) if null_se else 1.0
    interval_se = math.sqrt(
        control_rate * (1 - control_rate) / control_total
        + treatment_rate * (1 - treatment_rate) / treatment_total
    )
    ci_low, ci_high = difference - 1.96 * interval_se, difference + 1.96 * interval_se
    standardized_effect = abs(difference) / interval_se if interval_se else 0.0
    normal = NormalDist()
    observed_power = 1 - normal.cdf(1.96 - standardized_effect) + normal.cdf(-1.96 - standardized_effect)
    return control_rate, treatment_rate, difference, p_value, ci_low, ci_high, observed_power


def investigate_experiment(
    connection: duckdb.DuckDBPyConnection, current_start: date, current_end: date,
    *, experiment_name: str | None = None,
) -> dict[str, Any]:
    names = connection.execute(
        """SELECT DISTINCT experiment_name FROM experiments
           WHERE exposure_date >= ? AND exposure_date < ? ORDER BY experiment_name""",
        [current_start, current_end],
    ).fetchall()
    available = [row[0] for row in names]
    if experiment_name is None:
        if len(available) != 1:
            raise ValueError("Specify an experiment when the period does not contain exactly one")
        experiment_name = available[0]
    if experiment_name not in available:
        raise ValueError(f"Experiment {experiment_name!r} has no exposures in the requested period")

    rows = connection.execute(
        """SELECT variant, COUNT(*) AS participants, SUM(conversion) AS conversions,
                  SUM(revenue) AS revenue, AVG(revenue) AS revenue_per_user
           FROM experiments
           WHERE experiment_name = ? AND exposure_date >= ? AND exposure_date < ?
           GROUP BY variant""",
        [experiment_name, current_start, current_end],
    ).fetchall()
    variants = {row[0].casefold(): row for row in rows}
    if "control" not in variants or "treatment" not in variants:
        raise ValueError("Experiment requires control and treatment variants")
    _, control_n, control_conversions, control_revenue, control_rpu = variants["control"]
    _, treatment_n, treatment_conversions, treatment_revenue, treatment_rpu = variants["treatment"]
    control_rate, treatment_rate, lift, p_value, ci_low, ci_high, power = _two_proportion_test(
        control_conversions, control_n, treatment_conversions, treatment_n
    )
    relative_lift = None if control_rate == 0 else lift / control_rate
    revenue_lift = treatment_revenue - control_revenue
    rpu_lift = treatment_rpu - control_rpu
    identity = "|".join([experiment_name, current_start.isoformat(), current_end.isoformat()])
    conversion_id = f"exp_{hashlib.sha256(('conversion|' + identity).encode()).hexdigest()[:12]}"
    revenue_id = f"exp_{hashlib.sha256(('revenue|' + identity).encode()).hexdigest()[:12]}"
    driver_id = f"exd_{hashlib.sha256(('treatment|' + identity).encode()).hexdigest()[:12]}"
    kpis = {
        "conversion_rate": {"evidence_id": conversion_id, "current": treatment_rate,
                            "previous": control_rate, "absolute_change": lift,
                            "percent_change": relative_lift},
        "revenue_per_user": {"evidence_id": revenue_id, "current": treatment_rpu,
                             "previous": control_rpu, "absolute_change": rpu_lift,
                             "percent_change": None if control_rpu == 0 else rpu_lift / control_rpu},
    }
    candidate = {
        "evidence_id": driver_id, "candidate_type": "experiment_lift", "dimension": "experiment",
        "segment": "treatment", "rank_within_dimension": 1,
        "score": min(abs(relative_lift or 0), 1.0),
        "evidence": {"experiment_name": experiment_name, "control_participants": control_n,
                     "treatment_participants": treatment_n, "control_conversions": control_conversions,
                     "treatment_conversions": treatment_conversions, "absolute_conversion_lift": lift,
                     "relative_conversion_lift": relative_lift, "p_value": p_value,
                     "confidence_interval_95": [ci_low, ci_high], "statistically_significant": p_value < 0.05,
                     "observed_power": power, "low_power_warning": power < 0.8,
                     "control_revenue": control_revenue, "treatment_revenue": treatment_revenue,
                     "absolute_revenue_lift": revenue_lift, "revenue_per_user_lift": rpu_lift},
    }
    return {"question_type": "experiment_analysis", "metric": "conversion_rate",
            "current_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "previous_period": {"start": current_start.isoformat(), "end_exclusive": current_end.isoformat()},
            "applied_scope": {"experiment": experiment_name}, "kpis": kpis, "decompositions": {},
            "overall_funnel": [], "leading_device_funnel": [], "ranked_candidates": [candidate],
            "related_incidents": []}
