"""Provider-neutral planning interfaces with strict deterministic guardrails."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.orchestration.state import InvestigationPlan


class PlanValidationError(ValueError):
    """Raised when a provider changes immutable request facts."""


class PlanningProvider(Protocol):
    """Create a plan; providers never execute analytics or calculate evidence."""

    name: str

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        ...


TOOL_BY_QUESTION_TYPE = {
    "root_cause_analysis": "run_revenue_investigation",
    "campaign_performance_analysis": "run_campaign_performance_investigation",
    "traffic_analysis": "run_traffic_investigation",
    "data_quality_analysis": "run_attribution_quality_investigation",
    "sentiment_analysis": "run_review_sentiment_investigation",
    "experiment_analysis": "run_experiment_investigation",
}
METRICS_BY_QUESTION_TYPE = {
    "root_cause_analysis": {"revenue"},
    "campaign_performance_analysis": {"cpc", "ctr", "cpa", "roas", "conversion_rate"},
    "traffic_analysis": {"sessions", "users"},
    "data_quality_analysis": {"attribution_completeness"},
    "sentiment_analysis": {"negative_review_rate"},
    "experiment_analysis": {"conversion_rate"},
}


def validate_plan_for_request(
    plan: InvestigationPlan, request: InvestigationRequest,
) -> InvestigationPlan:
    """Reject provider output that changes the question or comparison periods."""
    expected = {
        "question": request.question,
        "current_start": request.current_start,
        "current_end": request.current_end,
        "previous_start": request.previous_start,
        "previous_end": request.previous_end,
    }
    actual = {
        "question": plan.question,
        "current_start": plan.current_period.start,
        "current_end": plan.current_period.end_exclusive,
        "previous_start": plan.comparison_period.start,
        "previous_end": plan.comparison_period.end_exclusive,
    }
    changed = [key for key in expected if expected[key] != actual[key]]
    if changed:
        raise PlanValidationError(f"Planning provider changed immutable request fields: {changed}")
    expected_tool = TOOL_BY_QUESTION_TYPE[plan.question_type]
    if plan.tools != [expected_tool]:
        raise PlanValidationError(
            f"Question type {plan.question_type!r} requires exactly tool {expected_tool!r}"
        )
    if plan.primary_metric not in METRICS_BY_QUESTION_TYPE[plan.question_type]:
        raise PlanValidationError(
            f"Metric {plan.primary_metric!r} is invalid for question type {plan.question_type!r}"
        )
    return plan


@dataclass
class DeterministicPlanningProvider:
    """Adapter for the existing rule-based Manager baseline."""

    name: str = "deterministic"

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        return validate_plan_for_request(ManagerAgent().create_plan(request), request)


LLMCompletion = Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


@dataclass
class StructuredLLMPlanningProvider:
    """Inject a structured-output LLM callable without coupling to a vendor SDK."""

    complete: LLMCompletion
    name: str = "llm"

    SYSTEM_POLICY = (
        "You are a planning component for a marketing analytics system. Return only a plan matching "
        "the supplied JSON schema. Never calculate metrics, statistics, evidence, or business results. "
        "Never change the question or dates. Select only deterministic tools represented by the schema."
    )

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        request_payload = request.model_dump(mode="json")
        schema = InvestigationPlan.model_json_schema()
        raw = self.complete(self.SYSTEM_POLICY, request_payload, schema)
        if not isinstance(raw, Mapping):
            raise PlanValidationError("Structured planning provider must return a mapping")
        try:
            plan = InvestigationPlan.model_validate(dict(raw))
        except Exception as exc:
            raise PlanValidationError(f"Provider returned an invalid plan: {exc}") from exc
        return validate_plan_for_request(plan, request)

    def prompt_preview(self, request: InvestigationRequest) -> str:
        """Return a reproducible prompt preview for logs and offline evaluation."""
        return json.dumps({"policy": self.SYSTEM_POLICY, "request": request.model_dump(mode="json"),
                           "schema": InvestigationPlan.model_json_schema()}, sort_keys=True)


@dataclass
class ReplayPlanningProvider:
    """Replay previously captured structured plans for reproducible offline comparison."""

    plans_by_question: Mapping[str, Mapping[str, Any]]
    name: str = "replay"

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        if request.question not in self.plans_by_question:
            raise PlanValidationError(f"No replay plan for question: {request.question}")
        plan = InvestigationPlan.model_validate(self.plans_by_question[request.question])
        return validate_plan_for_request(plan, request)
