"""Validated benchmark and evaluation result models."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class EvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedDriver(EvaluationModel):
    dimension: str
    segment: str


class BenchmarkCase(EvaluationModel):
    case_id: str
    question: str
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    expected_question_type: str
    expected_primary_driver: ExpectedDriver
    expected_top_drivers: List[ExpectedDriver]
    expected_funnel_transition: Optional[str]
    expected_root_cause_contains: str


class CaseEvaluation(EvaluationModel):
    case_id: str
    status: Literal["completed", "unsupported", "failed"]
    latency_ms: float = Field(ge=0)
    classification_correct: bool = False
    primary_driver_correct: bool = False
    top_three_driver_recall: float = Field(default=0, ge=0, le=1)
    funnel_transition_correct: bool = False
    root_cause_correct: bool = False
    evidence_valid: bool = False
    unsupported_claim_rate: float = Field(default=0, ge=0, le=1)
    tool_execution_success: bool = False
    error: Optional[str] = None


class AggregateMetrics(EvaluationModel):
    total_cases: int
    completed_cases: int
    unsupported_cases: int
    failed_cases: int
    workflow_coverage: float
    classification_accuracy: float
    primary_driver_accuracy: float
    mean_top_three_driver_recall: float
    funnel_accuracy: float
    root_cause_accuracy: float
    evidence_validity_rate: float
    unsupported_claim_rate: float
    tool_success_rate: float
    average_completed_latency_ms: float


class EvaluationReport(EvaluationModel):
    benchmark_version: str
    cases: List[CaseEvaluation]
    metrics: AggregateMetrics
