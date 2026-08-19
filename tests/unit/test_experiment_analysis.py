from datetime import date

import pytest

from src.analytics.experiment_analysis import investigate_experiment
from src.database.connection import connect


def test_experiment_analysis_calculates_lift_and_uncertainty():
    with connect(read_only=True) as connection:
        report = investigate_experiment(
            connection, date(2026, 7, 1), date(2026, 8, 1),
            experiment_name="Checkout reassurance copy",
        )
    conversion = report["kpis"]["conversion_rate"]
    evidence = report["ranked_candidates"][0]["evidence"]
    assert conversion["current"] == 62 / 450
    assert conversion["previous"] == 44 / 450
    assert conversion["absolute_change"] == pytest.approx((62 - 44) / 450)
    assert evidence["confidence_interval_95"][0] < 0 < evidence["confidence_interval_95"][1]
    assert evidence["statistically_significant"] is False
    assert evidence["low_power_warning"] is True


def test_experiment_revenue_metrics_reconcile():
    with connect(read_only=True) as connection:
        report = investigate_experiment(
            connection, date(2026, 7, 1), date(2026, 8, 1),
            experiment_name="Checkout reassurance copy",
        )
    evidence = report["ranked_candidates"][0]["evidence"]
    assert evidence["absolute_revenue_lift"] == evidence["treatment_revenue"] - evidence["control_revenue"]
    assert report["kpis"]["revenue_per_user"]["absolute_change"] == evidence["revenue_per_user_lift"]
