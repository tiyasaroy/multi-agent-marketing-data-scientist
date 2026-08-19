from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.agents.critic_agent import CriticAgent
from src.agents.manager_agent import ManagerAgent
from src.api.main import app
from src.api.schemas import InvestigationRequest
from src.orchestration.state import EvidenceClaim, ExecutiveReport
from src.orchestration.workflow import InvestigationWorkflow
from src.tools.analytics_tools import AnalyticsToolRegistry, UnknownToolError


def request(question: str = "Why did revenue decline during the incident week?") -> InvestigationRequest:
    return InvestigationRequest(
        question=question,
        current_start=date(2026, 7, 20), current_end=date(2026, 7, 27),
        previous_start=date(2026, 7, 13), previous_end=date(2026, 7, 20),
    )


def test_manager_creates_validated_revenue_plan():
    plan = ManagerAgent().create_plan(request())
    assert plan.question_type == "root_cause_analysis"
    assert plan.primary_metric == "revenue"
    assert plan.tools == ["run_revenue_investigation"]
    assert plan.scope.active_filters() == {}


def test_manager_extracts_country_scope_and_workflow_applies_it():
    scoped_request = request("Why did revenue decline in India during the incident week?")
    plan = ManagerAgent().create_plan(scoped_request)
    assert plan.scope.country == "India"

    result = InvestigationWorkflow().run(scoped_request)
    assert result.evidence.applied_scope == {"country": "India"}
    assert result.evidence.ranked_candidates[0].dimension == "country"
    assert result.evidence.ranked_candidates[0].segment == "India"
    assert "country=India" in result.executive_report.title
    assert any("Payment completion failure concentrated in India" in row.root_cause
               for row in result.evidence.related_incidents)


@pytest.mark.parametrize(
    ("question", "dimension", "value"),
    [
        ("Why did revenue decline for Android?", "device", "Android"),
        ("Why did revenue decline from Google Ads?", "channel", "Google Ads"),
        ("Why did revenue decline for Meta Summer Lift?", "campaign", "Meta_Summer_Lift"),
        ("Why did revenue decline among High Value customers?", "customer_segment", "High Value"),
    ],
)
def test_manager_extracts_each_supported_scope_dimension(question, dimension, value):
    plan = ManagerAgent().create_plan(request(question))
    assert plan.scope.active_filters() == {dimension: value}


def test_campaign_question_uses_campaign_tool_and_validated_report():
    campaign_request = InvestigationRequest(
        question="Why did Google Ads CPC increase in the first half of June?",
        current_start=date(2026, 6, 1), current_end=date(2026, 6, 15),
        previous_start=date(2026, 5, 18), previous_end=date(2026, 6, 1),
    )
    result = InvestigationWorkflow().run(campaign_request)
    assert result.plan.question_type == "campaign_performance_analysis"
    assert result.plan.primary_metric == "cpc"
    assert result.executed_tools == ["run_campaign_performance_investigation"]
    assert result.executive_report.primary_driver.text.endswith("channel=Google Ads.")
    assert result.critic_review.approved is True


def test_scoped_and_global_evidence_ids_are_distinct():
    global_result = InvestigationWorkflow().run(request())
    scoped_result = InvestigationWorkflow().run(
        request("Why did revenue decline in India during the incident week?")
    )
    assert global_result.evidence.kpis["revenue"].evidence_id != scoped_result.evidence.kpis["revenue"].evidence_id
    assert global_result.evidence.ranked_candidates[0].evidence_id != scoped_result.evidence.ranked_candidates[0].evidence_id


def test_registry_rejects_unregistered_tools():
    registry = AnalyticsToolRegistry()
    plan = ManagerAgent().create_plan(request())
    with pytest.raises(UnknownToolError):
        registry.execute("arbitrary_sql", plan)


def test_workflow_produces_critic_approved_evidence_report():
    result = InvestigationWorkflow().run(request())
    assert result.critic_review.approved is True
    assert result.executed_tools == ["run_revenue_investigation"]
    assert result.executive_report.primary_driver.text.endswith("device=Android.")
    assert any(
        "checkout_started -> payment_started" in claim.text
        for claim in result.executive_report.contributing_factors
    )


def test_critic_rejects_fabricated_evidence_id():
    fake = EvidenceClaim(claim_id="fake", text="Unsupported claim", evidence_ids=["made_up"])
    report = ExecutiveReport(
        title="Bad report", summary=[fake], primary_driver=fake,
        contributing_factors=[], recommendations=[], limitations=[],
    )
    review = CriticAgent().review(report, {"real_evidence"})
    assert review.approved is False
    assert review.unsupported_evidence_ids == ["made_up"]


def test_ask_endpoint_returns_plan_report_and_evidence():
    response = TestClient(app).post("/investigations/ask", json=request().model_dump(mode="json"))
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["primary_metric"] == "revenue"
    assert body["critic_review"]["approved"] is True
    assert body["evidence"]["ranked_candidates"][0]["segment"] == "Android"
