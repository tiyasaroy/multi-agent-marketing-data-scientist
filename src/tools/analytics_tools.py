"""Allowlisted deterministic analytics tool registry."""

from typing import Callable, Dict

from src.analytics.root_cause_analysis import investigate_revenue_decline
from src.analytics.campaign_performance import investigate_campaign_performance
from src.analytics.traffic_analysis import investigate_traffic_change
from src.analytics.attribution_quality import investigate_attribution_quality
from src.analytics.review_sentiment import investigate_review_sentiment
from src.api.schemas import InvestigationReport
from src.database.connection import connect
from src.orchestration.state import InvestigationPlan


class UnknownToolError(ValueError):
    """Raised when an agent requests a tool outside the allowlist."""


class AnalyticsToolRegistry:
    """Execute only explicitly registered read-only analytics operations."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[[InvestigationPlan], InvestigationReport]] = {
            "run_revenue_investigation": self._run_revenue_investigation,
            "run_campaign_performance_investigation": self._run_campaign_performance_investigation,
            "run_traffic_investigation": self._run_traffic_investigation,
            "run_attribution_quality_investigation": self._run_attribution_quality_investigation,
            "run_review_sentiment_investigation": self._run_review_sentiment_investigation,
        }

    @property
    def registered_names(self) -> set:
        return set(self._tools)

    def execute(self, name: str, plan: InvestigationPlan) -> InvestigationReport:
        if name not in self._tools:
            raise UnknownToolError(f"Tool {name!r} is not registered")
        return self._tools[name](plan)

    @staticmethod
    def _run_revenue_investigation(plan: InvestigationPlan) -> InvestigationReport:
        with connect(read_only=True) as connection:
            result = investigate_revenue_decline(
                connection,
                plan.current_period.start,
                plan.current_period.end_exclusive,
                plan.comparison_period.start,
                plan.comparison_period.end_exclusive,
                scope=plan.scope.active_filters(),
            )
        return InvestigationReport.model_validate(result)

    @staticmethod
    def _run_campaign_performance_investigation(plan: InvestigationPlan) -> InvestigationReport:
        with connect(read_only=True) as connection:
            result = investigate_campaign_performance(
                connection, plan.current_period.start, plan.current_period.end_exclusive,
                plan.comparison_period.start, plan.comparison_period.end_exclusive,
                metric=plan.primary_metric, scope=plan.scope.active_filters(),
            )
        return InvestigationReport.model_validate(result)

    @staticmethod
    def _run_traffic_investigation(plan: InvestigationPlan) -> InvestigationReport:
        with connect(read_only=True) as connection:
            result = investigate_traffic_change(
                connection, plan.current_period.start, plan.current_period.end_exclusive,
                plan.comparison_period.start, plan.comparison_period.end_exclusive,
                metric=plan.primary_metric, scope=plan.scope.active_filters(),
            )
        return InvestigationReport.model_validate(result)

    @staticmethod
    def _run_attribution_quality_investigation(plan: InvestigationPlan) -> InvestigationReport:
        with connect(read_only=True) as connection:
            result = investigate_attribution_quality(
                connection, plan.current_period.start, plan.current_period.end_exclusive,
                plan.comparison_period.start, plan.comparison_period.end_exclusive,
                scope=plan.scope.active_filters(),
            )
        return InvestigationReport.model_validate(result)

    @staticmethod
    def _run_review_sentiment_investigation(plan: InvestigationPlan) -> InvestigationReport:
        with connect(read_only=True) as connection:
            result = investigate_review_sentiment(
                connection, plan.current_period.start, plan.current_period.end_exclusive,
                plan.comparison_period.start, plan.comparison_period.end_exclusive,
                scope=plan.scope.active_filters(),
            )
        return InvestigationReport.model_validate(result)
