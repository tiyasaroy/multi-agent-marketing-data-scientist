"""Validated API and evidence contracts."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InvestigationRequest(StrictModel):
    question: str = Field(min_length=5, max_length=500)
    current_start: date
    current_end: date = Field(description="Exclusive end date")
    previous_start: date
    previous_end: date = Field(description="Exclusive end date")

    @model_validator(mode="after")
    def validate_periods(self) -> "InvestigationRequest":
        if self.current_start >= self.current_end:
            raise ValueError("current_start must be before current_end")
        if self.previous_start >= self.previous_end:
            raise ValueError("previous_start must be before previous_end")
        if self.current_start < self.previous_end:
            raise ValueError("current period must not overlap the previous period")
        if self.current_end - self.current_start != self.previous_end - self.previous_start:
            raise ValueError("comparison periods must have equal duration")
        return self


class Period(StrictModel):
    start: date
    end_exclusive: date


class MetricComparison(StrictModel):
    current: float
    previous: float
    absolute_change: float
    percent_change: Optional[float]


class DimensionEvidence(StrictModel):
    evidence_id: str
    metric: str
    dimension: str
    segment: str
    current_sessions: int
    previous_sessions: int
    current_conversions: int
    previous_conversions: int
    current_revenue: float
    previous_revenue: float
    revenue_change: float
    revenue_percent_change: Optional[float]
    contribution_share: Optional[float]
    current_conversion_rate: float
    previous_conversion_rate: float
    conversion_rate_change: float
    conversion_rate_p_value: Optional[float]
    statistically_significant: bool


class FunnelEvidence(StrictModel):
    evidence_id: str
    from_step: str
    to_step: str
    current_from_sessions: int
    current_to_sessions: int
    previous_from_sessions: int
    previous_to_sessions: int
    current_rate: float
    previous_rate: float
    absolute_change: float
    percent_change: Optional[float]
    p_value: Optional[float]
    statistically_significant: bool
    filter_dimension: Optional[str]
    filter_value: Optional[str]


class RootCauseCandidate(StrictModel):
    evidence_id: str
    candidate_type: str
    dimension: str
    segment: str
    score: float = Field(ge=0, le=1)
    rank_within_dimension: Optional[int] = None
    transition: Optional[str] = None
    evidence: Dict[str, Any]


class IncidentEvidence(StrictModel):
    incident_id: str
    incident_date: date
    title: str
    root_cause: str
    resolution: str
    impact: str


class InvestigationReport(StrictModel):
    question_type: str
    metric: str
    current_period: Period
    previous_period: Period
    kpis: Dict[str, MetricComparison]
    decompositions: Dict[str, List[DimensionEvidence]]
    overall_funnel: List[FunnelEvidence]
    leading_device_funnel: List[FunnelEvidence]
    ranked_candidates: List[RootCauseCandidate]
    related_incidents: List[IncidentEvidence]


class MetricDefinition(StrictModel):
    metric_name: str
    definition: str
    formula: str
    required_columns: str
    allowed_dimensions: str
    business_context: str
    owner: str


class HealthResponse(StrictModel):
    status: str
    database: str
    session_count: int
