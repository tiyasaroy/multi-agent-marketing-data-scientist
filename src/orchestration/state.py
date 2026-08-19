"""Validated state shared by the Manager, tools, reporter, and Critic."""

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.api.schemas import InvestigationReport


class WorkflowModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanPeriod(WorkflowModel):
    start: date
    end_exclusive: date


class InvestigationScope(WorkflowModel):
    country: Optional[str] = None
    device: Optional[str] = None
    channel: Optional[str] = None
    campaign: Optional[str] = None
    customer_segment: Optional[str] = None
    experiment: Optional[str] = None

    def active_filters(self) -> dict[str, str]:
        return {
            name: value for name, value in self.model_dump().items() if value is not None
        }


class InvestigationPlan(WorkflowModel):
    question: str
    question_type: Literal[
        "root_cause_analysis", "campaign_performance_analysis", "traffic_analysis",
        "data_quality_analysis",
        "sentiment_analysis",
        "experiment_analysis",
    ]
    primary_metric: Literal[
        "revenue", "cpc", "ctr", "cpa", "roas", "conversion_rate", "sessions", "users",
        "attribution_completeness",
        "negative_review_rate",
    ]
    current_period: PlanPeriod
    comparison_period: PlanPeriod
    scope: InvestigationScope = Field(default_factory=InvestigationScope)
    investigations: List[str]
    tools: List[str]


class EvidenceClaim(WorkflowModel):
    claim_id: str
    text: str
    evidence_ids: List[str] = Field(min_length=1)


class ExecutiveReport(WorkflowModel):
    title: str
    summary: List[EvidenceClaim]
    primary_driver: EvidenceClaim
    contributing_factors: List[EvidenceClaim]
    recommendations: List[EvidenceClaim]
    limitations: List[str]


class CriticReview(WorkflowModel):
    approved: bool
    errors: List[str]
    unsupported_evidence_ids: List[str]


class WorkflowState(WorkflowModel):
    question: str
    plan: Optional[InvestigationPlan] = None
    executed_tools: List[str] = Field(default_factory=list)
    evidence: Optional[InvestigationReport] = None
    executive_report: Optional[ExecutiveReport] = None
    critic_review: Optional[CriticReview] = None
    errors: List[str] = Field(default_factory=list)


class WorkflowResponse(WorkflowModel):
    plan: InvestigationPlan
    executed_tools: List[str]
    executive_report: ExecutiveReport
    critic_review: CriticReview
    evidence: InvestigationReport
