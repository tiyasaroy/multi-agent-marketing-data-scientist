from datetime import date

from src.analytics.contribution_analysis import decompose_metric
from src.analytics.funnel_analysis import compare_funnels
from src.analytics.root_cause_analysis import investigate_revenue_decline
from src.database.connection import connect

CURRENT = (date(2026, 7, 20), date(2026, 7, 27))
PREVIOUS = (date(2026, 7, 13), date(2026, 7, 20))


def test_dimension_changes_reconcile_to_total_revenue_change():
    with connect(read_only=True) as connection:
        rows = decompose_metric(connection, "device", *CURRENT, *PREVIOUS)
    assert round(sum(row["revenue_change"] for row in rows), 2) == -1429.84
    assert rows[0]["segment"] == "Android"


def test_android_payment_transition_is_the_largest_funnel_drop():
    with connect(read_only=True) as connection:
        transitions = compare_funnels(
            connection, *CURRENT, *PREVIOUS,
            filter_dimension="device", filter_value="Android",
        )
    worst = min(transitions, key=lambda row: row["absolute_change"])
    assert worst["from_step"] == "checkout_started"
    assert worst["to_step"] == "payment_started"
    assert worst["absolute_change"] < -0.25


def test_root_cause_report_links_incident_and_ranked_evidence():
    with connect(read_only=True) as connection:
        report = investigate_revenue_decline(connection, *CURRENT, *PREVIOUS)
    assert report["ranked_candidates"]
    assert report["related_incidents"][0]["title"] == "Android checkout regression"
    assert report["ranked_candidates"][0]["dimension"] == "device"
    assert report["ranked_candidates"][0]["segment"] == "Android"
    top_labels = {(row["dimension"], row["segment"]) for row in report["ranked_candidates"][:10]}
    assert ("device", "Android") in top_labels
    assert ("country", "India") in top_labels
