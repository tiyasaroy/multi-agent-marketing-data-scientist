"""Rule-based baseline Manager Agent for investigation planning."""

from src.api.schemas import InvestigationRequest
from src.orchestration.state import InvestigationPlan, PlanPeriod


class UnsupportedQuestionError(ValueError):
    """Raised when the baseline manager cannot safely classify a question."""


class ManagerAgent:
    """Turn a supported business question into a validated execution plan."""

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        if "revenue" not in request.question.casefold():
            raise UnsupportedQuestionError(
                "The baseline workflow currently supports revenue investigations only"
            )
        return InvestigationPlan(
            question=request.question,
            question_type="root_cause_analysis",
            primary_metric="revenue",
            current_period=PlanPeriod(start=request.current_start, end_exclusive=request.current_end),
            comparison_period=PlanPeriod(start=request.previous_start, end_exclusive=request.previous_end),
            investigations=[
                "kpi_comparison", "dimension_decomposition", "funnel_analysis",
                "statistical_validation", "incident_retrieval",
            ],
            tools=["run_revenue_investigation"],
        )
