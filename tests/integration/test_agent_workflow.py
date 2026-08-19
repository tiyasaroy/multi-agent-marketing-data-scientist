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
