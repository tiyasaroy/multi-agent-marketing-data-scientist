"""Provider-neutral planning interfaces with strict deterministic guardrails."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Protocol

from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.orchestration.state import InvestigationPlan


class PlanValidationError(ValueError):
    """Raised when a provider changes immutable request facts."""


class PlanningProviderUnavailableError(ConnectionError):
    """Raised when an optional planning service cannot be reached."""


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


OllamaTransport = Callable[[str, Mapping[str, Any], float], Mapping[str, Any]]


def _ollama_http_transport(url: str, payload: Mapping[str, Any], timeout: float) -> Mapping[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PlanningProviderUnavailableError(f"Ollama is unavailable at {url}: {exc}") from exc


@dataclass
class OllamaPlanningProvider:
    """Use a local Ollama model for schema-constrained planning only."""

    model: str = "qwen3:8b"
    host: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 120.0
    fallback: Optional[PlanningProvider] = None
    transport: OllamaTransport = _ollama_http_transport

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        schema = InvestigationPlan.model_json_schema()
        user_content = json.dumps({
            "request": request.model_dump(mode="json"),
            "instruction": "Classify the question and return the execution plan. Copy question and dates exactly.",
            "allowed_question_type_tools": TOOL_BY_QUESTION_TYPE,
            "allowed_metrics_by_question_type": {
                key: sorted(values) for key, values in METRICS_BY_QUESTION_TYPE.items()
            },
        }, sort_keys=True)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": StructuredLLMPlanningProvider.SYSTEM_POLICY},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": schema,
            "options": {"temperature": 0},
        }
        try:
            response = self.transport(
                f"{self.host.rstrip('/')}/api/chat", payload, self.timeout_seconds
            )
        except PlanningProviderUnavailableError:
            if self.fallback is not None:
                return self.fallback.create_plan(request)
            raise
        try:
            content = response["message"]["content"]
            raw_plan = json.loads(content)
            plan = InvestigationPlan.model_validate(raw_plan)
        except Exception as exc:
            raise PlanValidationError(f"Ollama returned an invalid structured plan: {exc}") from exc
        return validate_plan_for_request(plan, request)


def planning_provider_from_env() -> PlanningProvider:
    """Build the configured planner; deterministic remains the safe default."""
    provider = os.getenv("PLANNING_PROVIDER", "deterministic").strip().casefold()
    if provider == "deterministic":
        return DeterministicPlanningProvider()
    if provider != "ollama":
        raise ValueError("PLANNING_PROVIDER must be 'deterministic' or 'ollama'")
    fallback_enabled = os.getenv("OLLAMA_DETERMINISTIC_FALLBACK", "false").casefold() in {
        "1", "true", "yes",
    }
    return OllamaPlanningProvider(
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
        fallback=DeterministicPlanningProvider() if fallback_enabled else None,
    )
