"""Run the agent workflow against versioned benchmark cases."""

import json
from pathlib import Path
from time import perf_counter
from typing import List

from pydantic import TypeAdapter

from src.agents.manager_agent import UnsupportedQuestionError
from src.api.schemas import InvestigationRequest
from src.evaluation.agent_metrics import (
    driver_matches,
    funnel_match,
    root_cause_match,
    top_driver_recall,
)
from src.evaluation.evidence_metrics import evidence_valid, unsupported_claim_rate
from src.evaluation.models import (
    AggregateMetrics,
    BenchmarkCase,
    CaseEvaluation,
    EvaluationReport,
)
from src.orchestration.workflow import InvestigationWorkflow

DEFAULT_BENCHMARK = Path("data/evaluation/benchmark_cases.json")


class EvaluationRunner:
    def __init__(self, workflow: InvestigationWorkflow = None) -> None:
        self.workflow = workflow or InvestigationWorkflow()

    @staticmethod
    def load_cases(path: Path = DEFAULT_BENCHMARK) -> List[BenchmarkCase]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return TypeAdapter(List[BenchmarkCase]).validate_python(payload)

    def evaluate_case(self, case: BenchmarkCase) -> CaseEvaluation:
        request = InvestigationRequest(
            question=case.question,
            current_start=case.current_start,
            current_end=case.current_end,
            previous_start=case.previous_start,
            previous_end=case.previous_end,
        )
        started = perf_counter()
        try:
            result = self.workflow.run(request)
        except UnsupportedQuestionError as exc:
            return CaseEvaluation(
                case_id=case.case_id,
                status="unsupported",
                latency_ms=(perf_counter() - started) * 1000,
                error=str(exc),
            )
        except Exception as exc:
            return CaseEvaluation(
                case_id=case.case_id,
                status="failed",
                latency_ms=(perf_counter() - started) * 1000,
                error=f"{type(exc).__name__}: {exc}",
            )

        primary = result.evidence.ranked_candidates[0]
        return CaseEvaluation(
            case_id=case.case_id,
            status="completed",
            latency_ms=(perf_counter() - started) * 1000,
            classification_correct=result.plan.question_type == case.expected_question_type,
            primary_driver_correct=driver_matches(
                primary.dimension, primary.segment, case.expected_primary_driver
            ),
            top_three_driver_recall=top_driver_recall(result, case.expected_top_drivers),
            funnel_transition_correct=funnel_match(result, case),
            root_cause_correct=root_cause_match(result, case),
            evidence_valid=evidence_valid(result),
            unsupported_claim_rate=unsupported_claim_rate(result),
            tool_execution_success=bool(result.executed_tools),
        )

    def run(self, path: Path = DEFAULT_BENCHMARK) -> EvaluationReport:
        cases = [self.evaluate_case(case) for case in self.load_cases(path)]
        return EvaluationReport(
            benchmark_version="1.0",
            cases=cases,
            metrics=self._aggregate(cases),
        )

    @staticmethod
    def _aggregate(cases: List[CaseEvaluation]) -> AggregateMetrics:
        total = len(cases)
        completed = [case for case in cases if case.status == "completed"]
        unsupported = sum(case.status == "unsupported" for case in cases)
        failed = sum(case.status == "failed" for case in cases)

        def all_case_rate(attribute: str) -> float:
            return sum(float(getattr(case, attribute)) for case in cases) / total if total else 0.0

        completed_count = len(completed)
        return AggregateMetrics(
            total_cases=total,
            completed_cases=completed_count,
            unsupported_cases=unsupported,
            failed_cases=failed,
            workflow_coverage=completed_count / total if total else 0.0,
            classification_accuracy=all_case_rate("classification_correct"),
            primary_driver_accuracy=all_case_rate("primary_driver_correct"),
            mean_top_three_driver_recall=all_case_rate("top_three_driver_recall"),
            funnel_accuracy=all_case_rate("funnel_transition_correct"),
            root_cause_accuracy=all_case_rate("root_cause_correct"),
            evidence_validity_rate=(
                sum(case.evidence_valid for case in completed) / completed_count if completed_count else 0.0
            ),
            unsupported_claim_rate=(
                sum(case.unsupported_claim_rate for case in completed) / completed_count
                if completed_count else 0.0
            ),
            tool_success_rate=all_case_rate("tool_execution_success"),
            average_completed_latency_ms=(
                sum(case.latency_ms for case in completed) / completed_count if completed_count else 0.0
            ),
        )

    @staticmethod
    def write_report(report: EvaluationReport, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
