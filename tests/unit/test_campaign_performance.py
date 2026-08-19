from datetime import date

from src.analytics.campaign_performance import investigate_campaign_performance, period_campaign_kpis
from src.database.connection import connect


def test_campaign_kpis_use_canonical_formulas():
    with connect(read_only=True) as connection:
        metrics = period_campaign_kpis(
            connection, date(2026, 6, 1), date(2026, 6, 15), scope={"channel": "Google Ads"}
        )
    assert metrics["cpc"] == metrics["spend"] / metrics["clicks"]
    assert metrics["ctr"] == metrics["clicks"] / metrics["impressions"]
    assert metrics["cpa"] == metrics["spend"] / metrics["conversions"]
    assert metrics["roas"] == metrics["revenue"] / metrics["spend"]


def test_google_ads_cpc_increase_is_scoped_and_evidenced():
    with connect(read_only=True) as connection:
        report = investigate_campaign_performance(
            connection, date(2026, 6, 1), date(2026, 6, 15),
            date(2026, 5, 18), date(2026, 6, 1), metric="cpc", scope={"channel": "Google Ads"},
        )
    assert report["kpis"]["cpc"]["percent_change"] > 0
    assert report["ranked_candidates"][0]["dimension"] == "channel"
    assert report["ranked_candidates"][0]["segment"] == "Google Ads"
    assert report["related_incidents"][0]["root_cause"] == "Competitor bidding pressure"
