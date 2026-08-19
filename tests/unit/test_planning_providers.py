from datetime import date

import pytest

from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.evaluation.planning_comparison import compare_planning_providers
from src.orchestration.workflow import InvestigationWorkflow
from src.planning.providers import (
    DeterministicPlanningProvider,
    PlanValidationError,
    PlanningDecision,
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
        plan = ManagerAgent().create_plan(request())
        return PlanningDecision(
            question_type=plan.question_type, primary_metric=plan.primary_metric, scope=plan.scope
        ).model_dump(mode="json")

    provider = StructuredLLMPlanningProvider(complete=complete, name="fake_llm")
    result = InvestigationWorkflow(provider).run(request())
    assert "Never calculate metrics" in captured["policy"]
    assert captured["payload"]["question"] == request().question
    assert "properties" in captured["schema"]
    assert result.executed_tools == ["run_revenue_investigation"]
    assert result.critic_review.approved is True


@pytest.mark.parametrize("mutation", ["extra_field", "metric"])
def test_structured_provider_rejects_extra_execution_fields_and_invalid_metrics(mutation):
    plan = ManagerAgent().create_plan(request())
    decision = PlanningDecision(
        question_type=plan.question_type, primary_metric=plan.primary_metric, scope=plan.scope
    ).model_dump(mode="json")
    if mutation == "extra_field":
        decision["tools"] = ["arbitrary_sql"]
    else:
        decision["primary_metric"] = "cpc"
    provider = StructuredLLMPlanningProvider(complete=lambda *_: decision)
    with pytest.raises(PlanValidationError):
        provider.create_plan(request())


def test_llm_decision_cannot_supply_or_change_dates():
    plan = ManagerAgent().create_plan(request())
    decision = PlanningDecision(
        question_type=plan.question_type, primary_metric=plan.primary_metric, scope=plan.scope
    ).model_dump(mode="json")
    provider = StructuredLLMPlanningProvider(complete=lambda *_: decision)
    materialized = provider.create_plan(request())
    assert materialized.current_period.start == request().current_start
    assert materialized.current_period.end_exclusive == request().current_end
    assert materialized.tools == ["run_revenue_investigation"]


def test_llm_decision_cannot_invent_scope_values():
    plan = ManagerAgent().create_plan(request())
    decision = PlanningDecision(
        question_type=plan.question_type, primary_metric=plan.primary_metric,
        scope={"country": "Canada"},
    ).model_dump(mode="json")
    provider = StructuredLLMPlanningProvider(complete=lambda *_: decision)
    with pytest.raises(PlanValidationError, match="not explicitly stated"):
        provider.create_plan(request())


def test_llm_scope_is_canonicalized_and_placeholders_are_removed():
    decision = PlanningDecision(
        question_type="root_cause_analysis", primary_metric="revenue",
        scope={"country": "india", "device": "none specified"},
    )
    provider = StructuredLLMPlanningProvider(
        complete=lambda *_: decision.model_dump(mode="json")
    )
    assert provider.create_plan(request()).scope.active_filters() == {"country": "India"}


def test_deterministic_candidate_has_full_plan_and_benchmark_agreement():
    report = compare_planning_providers(
        DeterministicPlanningProvider(name="deterministic_candidate")
    )
    assert report.total_cases == 7
    assert report.valid_plan_rate == 1.0
    assert report.exact_plan_agreement_rate == 1.0
    assert report.candidate_benchmark_metrics["workflow_coverage"] == 1.0
    assert report.candidate_benchmark_metrics["evidence_validity_rate"] == 1.0
