from datetime import date

from src.analytics.kpi_engine import compare_periods, period_kpis
from src.database.connection import connect


def test_period_kpis_are_internally_consistent():
    with connect(read_only=True) as connection:
        result = period_kpis(connection, date(2026, 7, 20), date(2026, 7, 27))
    assert result["sessions"] > 0
    assert result["conversions"] > 0
    assert result["revenue"] > 0
    assert result["conversion_rate"] == result["conversions"] / result["sessions"]
    assert result["average_order_value"] == result["revenue"] / result["conversions"]


def test_known_incident_week_has_conversion_decline():
    with connect(read_only=True) as connection:
        result = compare_periods(
            connection,
            date(2026, 7, 20), date(2026, 7, 27),
            date(2026, 7, 13), date(2026, 7, 20),
        )
    assert result["conversion_rate"]["percent_change"] < -0.20
