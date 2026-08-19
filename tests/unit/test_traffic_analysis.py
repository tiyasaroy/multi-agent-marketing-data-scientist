from datetime import date

from src.analytics.traffic_analysis import investigate_traffic_change, period_traffic_kpis
from src.database.connection import connect


CURRENT = (date(2026, 6, 15), date(2026, 7, 1))
PREVIOUS = (date(2026, 5, 30), date(2026, 6, 15))


def test_period_traffic_kpis_respect_channel_scope():
    with connect(read_only=True) as connection:
        global_kpis = period_traffic_kpis(connection, *CURRENT)
        organic_kpis = period_traffic_kpis(connection, *CURRENT, scope={"channel": "Organic Search"})
    assert 0 < organic_kpis["sessions"] < global_kpis["sessions"]
    assert organic_kpis["users"] <= organic_kpis["sessions"]


def test_organic_decline_has_scoped_driver_and_root_cause():
    with connect(read_only=True) as connection:
        report = investigate_traffic_change(
            connection, *CURRENT, *PREVIOUS, scope={"channel": "Organic Search"}
        )
    assert report["kpis"]["sessions"]["percent_change"] < 0
    assert report["ranked_candidates"][0]["dimension"] == "channel"
    assert report["ranked_candidates"][0]["segment"] == "Organic Search"
    assert report["related_incidents"][0]["root_cause"] == "Search ranking change"
