from datetime import date

import pytest

from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.evaluation.planning_comparison import compare_planning_providers
from src.orchestration.workflow import InvestigationWorkflow
from src.planning.providers import (
    DeterministicPlanningProvider,
    PlanValidationError,
    StructuredLLMPlanningProvider,
)


def request():
    return InvestigationRequest(
        question="Why did revenue decline in India from July 20 to July 26?",
        current_start=date(2026, 7, 20), current_end=date(2026, 7, 27),
        previous_start=date(2026, 7, 13), previous_end=date(2026, 7, 20),
    )


def test_structured_provider_can_plan_but_deterministic_tools_calculate():
    captured = {}

    def complete(policy, payload, schema):
        captured.update(policy=policy, payload=payload, schema=schema)
        return ManagerAgent().create_plan(request()).model_dump(mode="json")

    provider = StructuredLLMPlanningProvider(complete=complete, name="fake_llm")
    result = InvestigationWorkflow(provider).run(request())
    assert "Never calculate metrics" in captured["policy"]
    assert captured["payload"]["question"] == request().question
    assert "properties" in captured["schema"]
    assert result.executed_tools == ["run_revenue_investigation"]
    assert result.critic_review.approved is True


@pytest.mark.parametrize("mutation", ["date", "tool", "metric"])
def test_structured_provider_rejects_changed_facts_and_unallowlisted_tools(mutation):
    plan = ManagerAgent().create_plan(request()).model_dump(mode="json")
    if mutation == "date":
        plan["current_period"]["start"] = "2026-07-21"
    elif mutation == "tool":
        plan["tools"] = ["arbitrary_sql"]
    else:
        plan["primary_metric"] = "cpc"
    provider = StructuredLLMPlanningProvider(complete=lambda *_: plan)
    with pytest.raises(PlanValidationError):
        provider.create_plan(request())


def test_deterministic_candidate_has_full_plan_and_benchmark_agreement():
    report = compare_planning_providers(
        DeterministicPlanningProvider(name="deterministic_candidate")
    )
    assert report.total_cases == 7
    assert report.valid_plan_rate == 1.0
    assert report.exact_plan_agreement_rate == 1.0
    assert report.candidate_benchmark_metrics["workflow_coverage"] == 1.0
    assert report.candidate_benchmark_metrics["evidence_validity_rate"] == 1.0
