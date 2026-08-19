from datetime import date

from src.analytics.attribution_quality import investigate_attribution_quality, period_attribution_metrics
from src.database.connection import connect


CURRENT = (date(2026, 5, 10), date(2026, 5, 17))
PREVIOUS = (date(2026, 5, 3), date(2026, 5, 10))


def test_attribution_metrics_reconcile_to_total_sessions():
    with connect(read_only=True) as connection:
        metrics = period_attribution_metrics(connection, *CURRENT)
    assert metrics["attributed_sessions"] + metrics["unattributed_sessions"] == metrics["sessions"]
    assert metrics["attribution_completeness"] == metrics["attributed_sessions"] / metrics["sessions"]


def test_attribution_failure_identifies_unattributed_driver_and_cause():
    with connect(read_only=True) as connection:
        report = investigate_attribution_quality(connection, *CURRENT, *PREVIOUS)
    assert report["kpis"]["attribution_completeness"]["percent_change"] < 0
    assert report["ranked_candidates"][0]["dimension"] == "campaign"
    assert report["ranked_candidates"][0]["segment"] == "Unattributed"
    assert report["related_incidents"][0]["root_cause"] == "Campaign attribution tracking failure"
