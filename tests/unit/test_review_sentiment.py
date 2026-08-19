from datetime import date

from src.analytics.review_sentiment import investigate_review_sentiment, period_review_metrics
from src.database.connection import connect


CURRENT = (date(2026, 7, 20), date(2026, 8, 1))
PREVIOUS = (date(2026, 7, 8), date(2026, 7, 20))


def test_review_metrics_use_rating_threshold_consistently():
    with connect(read_only=True) as connection:
        metrics = period_review_metrics(connection, *CURRENT)
    assert 0 <= metrics["negative_review_rate"] <= 1
    assert metrics["negative_review_rate"] == metrics["negative_reviews"] / metrics["reviews"]


def test_negative_review_spike_has_topic_and_incident_evidence():
    with connect(read_only=True) as connection:
        report = investigate_review_sentiment(connection, *CURRENT, *PREVIOUS)
    assert report["kpis"]["negative_review_rate"]["percent_change"] > 0
    assert report["ranked_candidates"][0]["dimension"] == "topic"
    assert report["ranked_candidates"][0]["segment"] == "payment/crash/login/refund"
    assert report["related_incidents"][0]["root_cause"] == "Android checkout regression"
