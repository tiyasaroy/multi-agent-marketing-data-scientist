from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

VALID_REQUEST = {
    "question": "Why did revenue decline during the incident week?",
    "current_start": "2026-07-20",
    "current_end": "2026-07-27",
    "previous_start": "2026-07-13",
    "previous_end": "2026-07-20",
}


def test_health_reports_loaded_database():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "duckdb", "session_count": 11729}


def test_metrics_come_from_official_registry():
    response = client.get("/metrics")
    assert response.status_code == 200
    names = {metric["metric_name"] for metric in response.json()}
    assert {"revenue", "conversion_rate", "checkout_completion_rate"} <= names


def test_revenue_investigation_returns_validated_evidence():
    response = client.post("/investigations/revenue", json=VALID_REQUEST)
    assert response.status_code == 200
    report = response.json()
    assert report["kpis"]["revenue"]["percent_change"] < -0.40
    assert report["ranked_candidates"][0]["segment"] == "Android"
    assert report["ranked_candidates"][0]["evidence_id"].startswith("dim_")
    assert report["related_incidents"][0]["title"] == "Android checkout regression"


def test_invalid_or_unequal_periods_are_rejected():
    payload = {**VALID_REQUEST, "current_end": "2026-07-28"}
    response = client.post("/investigations/revenue", json=payload)
    assert response.status_code == 422


def test_unknown_fields_are_rejected():
    response = client.post(
        "/investigations/revenue",
        json={**VALID_REQUEST, "unsupported_metric": "profit"},
    )
    assert response.status_code == 422
