"""Provider-neutral planning interfaces with strict deterministic guardrails."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Literal, Mapping, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.agents.manager_agent import ManagerAgent, SCOPE_VALUES
from src.api.schemas import InvestigationRequest
from src.orchestration.state import InvestigationPlan, InvestigationScope, PlanPeriod


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
INVESTIGATIONS_BY_QUESTION_TYPE = {
    "root_cause_analysis": [
        "kpi_comparison", "dimension_decomposition", "funnel_analysis",
        "statistical_validation", "incident_retrieval",
    ],
    "campaign_performance_analysis": [
        "campaign_kpi_comparison", "campaign_driver_analysis", "incident_retrieval",
    ],
    "traffic_analysis": ["traffic_kpi_comparison", "traffic_driver_analysis", "incident_retrieval"],
    "data_quality_analysis": [
        "attribution_completeness", "missing_attribution_analysis", "incident_retrieval",
    ],
    "sentiment_analysis": [
        "review_sentiment_comparison", "negative_topic_analysis", "incident_retrieval",
    ],
    "experiment_analysis": ["variant_comparison", "conversion_lift", "revenue_lift", "power_check"],
}


class PlanningDecision(BaseModel):
    """The only fields an LLM may decide; execution facts are materialized locally."""

    model_config = ConfigDict(extra="forbid")
    question_type: Literal[
        "root_cause_analysis", "campaign_performance_analysis", "traffic_analysis",
        "data_quality_analysis", "sentiment_analysis", "experiment_analysis",
    ]
    primary_metric: Literal[
        "revenue", "cpc", "ctr", "cpa", "roas", "conversion_rate", "sessions", "users",
        "attribution_completeness", "negative_review_rate",
    ]
    scope: InvestigationScope = Field(default_factory=InvestigationScope)


def materialize_plan(decision: PlanningDecision, request: InvestigationRequest) -> InvestigationPlan:
    """Build immutable dates and allowlisted execution steps from a small LLM decision."""
    normalized_question = re.sub(r"[_-]+", " ", request.question).casefold()
    normalized_scope = {}
    placeholders = {"all", "any", "none", "none specified", "not specified", "n/a", "null"}
    for dimension, value in decision.scope.active_filters().items():
        normalized_value = re.sub(r"[_-]+", " ", value).casefold()
        if normalized_value in placeholders or normalized_value == dimension.replace("_", " "):
            continue
        canonical_value = next(
            (
                candidate for candidate in SCOPE_VALUES.get(dimension, ())
                if candidate.replace("_", " ").casefold() == normalized_value
            ),
            None,
        )
        if dimension == "channel" and normalized_value == "organic":
            canonical_value = "Organic Search"
        value = canonical_value or value
        normalized_value = re.sub(r"[_-]+", " ", value).casefold()
        explicitly_stated = re.search(
            rf"(?<!\w){re.escape(normalized_value)}(?!\w)", normalized_question
        )
        organic_alias = dimension == "channel" and value == "Organic Search" and re.search(
            r"(?<!\w)organic(?!\w)", normalized_question
        )
        if not explicitly_stated and not organic_alias:
            raise PlanValidationError(
                f"Scope {dimension}={value!r} was not explicitly stated in the question"
            )
        normalized_scope[dimension] = value
    decision = decision.model_copy(update={"scope": InvestigationScope(**normalized_scope)})
    expected_tool = TOOL_BY_QUESTION_TYPE[decision.question_type]
    plan = InvestigationPlan(
        question=request.question,
        question_type=decision.question_type,
        primary_metric=decision.primary_metric,
        current_period=PlanPeriod(start=request.current_start, end_exclusive=request.current_end),
        comparison_period=PlanPeriod(start=request.previous_start, end_exclusive=request.previous_end),
        scope=decision.scope,
        investigations=INVESTIGATIONS_BY_QUESTION_TYPE[decision.question_type],
        tools=[expected_tool],
    )
    return validate_plan_for_request(plan, request)


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


@dataclass
class ConsensusPlanningProvider:
    """Use an LLM decision only when it agrees with the deterministic safety baseline."""

    candidate: PlanningProvider
    baseline: PlanningProvider = None  # type: ignore[assignment]
    accepted: int = 0
    fallbacks: int = 0

    def __post_init__(self) -> None:
        if self.baseline is None:
            self.baseline = DeterministicPlanningProvider()

    @property
    def name(self) -> str:
        return f"consensus:{self.candidate.name}"

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        baseline_plan = self.baseline.create_plan(request)
        try:
            candidate_plan = self.candidate.create_plan(request)
        except (PlanValidationError, PlanningProviderUnavailableError):
            self.fallbacks += 1
            return baseline_plan
        candidate_signature = (
            candidate_plan.question_type,
            candidate_plan.primary_metric,
            candidate_plan.scope.model_dump(),
        )
        baseline_signature = (
            baseline_plan.question_type,
            baseline_plan.primary_metric,
            baseline_plan.scope.model_dump(),
        )
        if candidate_signature != baseline_signature:
            self.fallbacks += 1
            return baseline_plan
        self.accepted += 1
        return candidate_plan


LLMCompletion = Callable[[str, Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]]


@dataclass
class StructuredLLMPlanningProvider:
    """Inject a structured-output LLM callable without coupling to a vendor SDK."""

    complete: LLMCompletion
    name: str = "llm"

    SYSTEM_POLICY = (
        "You are a classification component for a marketing analytics system. Return only a decision "
        "matching the supplied JSON schema. Never calculate metrics, statistics, evidence, or business "
        "results. Select the question type, primary metric, and only scope values explicitly stated in "
        "the question. Dates and execution tools are constructed by deterministic code."
    )

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        request_payload = request.model_dump(mode="json")
        schema = PlanningDecision.model_json_schema()
        raw = self.complete(self.SYSTEM_POLICY, request_payload, schema)
        if not isinstance(raw, Mapping):
            raise PlanValidationError("Structured planning provider must return a mapping")
        try:
            decision = PlanningDecision.model_validate(dict(raw))
        except Exception as exc:
            raise PlanValidationError(f"Provider returned an invalid planning decision: {exc}") from exc
        return materialize_plan(decision, request)

    def prompt_preview(self, request: InvestigationRequest) -> str:
        """Return a reproducible prompt preview for logs and offline evaluation."""
        return json.dumps({"policy": self.SYSTEM_POLICY, "request": request.model_dump(mode="json"),
                           "schema": PlanningDecision.model_json_schema()}, sort_keys=True)


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
        schema = PlanningDecision.model_json_schema()
        user_content = json.dumps({
            "request": request.model_dump(mode="json"),
            "instruction": "Return only question_type, primary_metric, and explicit scope values.",
            "allowed_question_type_tools": TOOL_BY_QUESTION_TYPE,
            "allowed_metrics_by_question_type": {
                key: sorted(values) for key, values in METRICS_BY_QUESTION_TYPE.items()
            },
            "allowed_scope_values": {
                key: list(values) for key, values in SCOPE_VALUES.items()
            },
            "scope_rule": "Use null for every scope field not explicitly stated in the question.",
        }, sort_keys=True)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": StructuredLLMPlanningProvider.SYSTEM_POLICY},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "think": False,
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
            decision = PlanningDecision.model_validate(raw_plan)
        except Exception as exc:
            raise PlanValidationError(f"Ollama returned an invalid structured decision: {exc}") from exc
        return materialize_plan(decision, request)


def planning_provider_from_env() -> PlanningProvider:
    """Build the configured planner; deterministic remains the safe default."""
    provider = os.getenv("PLANNING_PROVIDER", "deterministic").strip().casefold()
    if provider == "deterministic":
        return DeterministicPlanningProvider()
    if provider != "ollama":
        raise ValueError("PLANNING_PROVIDER must be 'deterministic' or 'ollama'")
    ollama = OllamaPlanningProvider(
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"),
        timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
    )
    consensus_enabled = os.getenv("OLLAMA_REQUIRE_CONSENSUS", "true").casefold() in {
        "1", "true", "yes",
    }
    return ConsensusPlanningProvider(ollama) if consensus_enabled else ollama
