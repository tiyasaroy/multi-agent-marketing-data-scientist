"""Compare candidate planning providers with the deterministic baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict

from src.api.schemas import InvestigationRequest
from src.evaluation.evaluation_runner import DEFAULT_BENCHMARK, EvaluationRunner
from src.orchestration.workflow import InvestigationWorkflow
from src.planning.providers import DeterministicPlanningProvider, PlanningProvider


class _CachedProvider:
    def __init__(self, provider: PlanningProvider) -> None:
        self.provider = provider
        self.name = provider.name
        self.cache = {}
        self.errors = {}

    def create_plan(self, request: InvestigationRequest):
        key = request.model_dump_json()
        if key in self.errors:
            raise self.errors[key]
        if key not in self.cache:
            try:
                self.cache[key] = self.provider.create_plan(request)
            except Exception as exc:
                self.errors[key] = exc
                raise
        return self.cache[key].model_copy(deep=True)


class ComparisonModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanAgreement(ComparisonModel):
    case_id: str
    valid: bool
    exact_match: bool
    question_type_match: bool = False
    primary_metric_match: bool = False
    tools_match: bool = False
    scope_match: bool = False
    error: Optional[str] = None
    baseline_plan: Optional[Dict[str, Any]] = None
    candidate_plan: Optional[Dict[str, Any]] = None


class PlanningComparisonReport(ComparisonModel):
    baseline_provider: str
    candidate_provider: str
    total_cases: int
    valid_plan_rate: float
    exact_plan_agreement_rate: float
    question_type_agreement_rate: float
    primary_metric_agreement_rate: float
    tool_agreement_rate: float
    scope_agreement_rate: float
    baseline_benchmark_metrics: Dict[str, Any]
    candidate_benchmark_metrics: Dict[str, Any]
    candidate_benchmark_cases: List[Dict[str, Any]]
    cases: List[PlanAgreement]


def compare_planning_providers(
    candidate: PlanningProvider, *, baseline: PlanningProvider = None,
    benchmark_path: Path = DEFAULT_BENCHMARK,
) -> PlanningComparisonReport:
    baseline = _CachedProvider(baseline or DeterministicPlanningProvider())
    candidate = _CachedProvider(candidate)
    cases = EvaluationRunner.load_cases(benchmark_path)
    agreements = []
    for case in cases:
        request = InvestigationRequest(
            question=case.question, current_start=case.current_start, current_end=case.current_end,
            previous_start=case.previous_start, previous_end=case.previous_end,
        )
        baseline_plan = baseline.create_plan(request)
        try:
            candidate_plan = candidate.create_plan(request)
            question_type_match = candidate_plan.question_type == baseline_plan.question_type
            primary_metric_match = candidate_plan.primary_metric == baseline_plan.primary_metric
            tools_match = candidate_plan.tools == baseline_plan.tools
            scope_match = candidate_plan.scope == baseline_plan.scope
            agreements.append(PlanAgreement(
                case_id=case.case_id, valid=True,
                exact_match=question_type_match and primary_metric_match and tools_match and scope_match,
                question_type_match=question_type_match, primary_metric_match=primary_metric_match,
                tools_match=tools_match, scope_match=scope_match,
                baseline_plan=baseline_plan.model_dump(mode="json"),
                candidate_plan=candidate_plan.model_dump(mode="json"),
            ))
        except Exception as exc:
            agreements.append(PlanAgreement(
                case_id=case.case_id, valid=False, exact_match=False,
                error=f"{type(exc).__name__}: {exc}",
                baseline_plan=baseline_plan.model_dump(mode="json"),
            ))

    baseline_report = EvaluationRunner(InvestigationWorkflow(baseline)).run(benchmark_path)
    candidate_report = EvaluationRunner(InvestigationWorkflow(candidate)).run(benchmark_path)
    total = len(agreements)

    def rate(attribute: str) -> float:
        return sum(float(getattr(item, attribute)) for item in agreements) / total if total else 0.0

    return PlanningComparisonReport(
        baseline_provider=baseline.name, candidate_provider=candidate.name, total_cases=total,
        valid_plan_rate=rate("valid"), exact_plan_agreement_rate=rate("exact_match"),
        question_type_agreement_rate=rate("question_type_match"),
        primary_metric_agreement_rate=rate("primary_metric_match"),
        tool_agreement_rate=rate("tools_match"), scope_agreement_rate=rate("scope_match"),
        baseline_benchmark_metrics=baseline_report.metrics.model_dump(),
        candidate_benchmark_metrics=candidate_report.metrics.model_dump(), cases=agreements,
        candidate_benchmark_cases=[case.model_dump() for case in candidate_report.cases],
    )
