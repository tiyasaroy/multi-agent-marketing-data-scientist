"""Rule-based baseline Manager Agent for investigation planning."""

import re

from src.api.schemas import InvestigationRequest
from src.orchestration.state import InvestigationPlan, InvestigationScope, PlanPeriod


SCOPE_VALUES = {
    "country": ("India", "United States", "United Kingdom", "Canada", "Australia"),
    "device": ("Android", "iOS", "Desktop"),
    "channel": ("Google Ads", "Meta Ads", "Organic Search", "Email", "Referral", "Direct"),
    "campaign": (
        "Always_On_Search", "Brand_Search", "Meta_Prospecting", "Meta_Summer_Lift",
        "Organic_Content", "Email_Nurture", "Referral_Program", "Direct_Brand",
    ),
    "customer_segment": ("New", "Occasional", "Loyal", "High Value"),
}


def _extract_scope(question: str) -> InvestigationScope:
    normalized = re.sub(r"[_\-]+", " ", question).casefold()
    matches = {}
    for dimension, values in SCOPE_VALUES.items():
        for value in values:
            candidate = value.replace("_", " ").casefold()
            if re.search(rf"(?<!\w){re.escape(candidate)}(?!\w)", normalized):
                matches[dimension] = value
                break
    if "channel" not in matches and re.search(r"(?<!\w)organic(?!\w)", normalized):
        matches["channel"] = "Organic Search"
    return InvestigationScope(**matches)


class UnsupportedQuestionError(ValueError):
    """Raised when the baseline manager cannot safely classify a question."""


class ManagerAgent:
    """Turn a supported business question into a validated execution plan."""

    def create_plan(self, request: InvestigationRequest) -> InvestigationPlan:
        question = request.question.casefold()
        scope = _extract_scope(request.question)
        if "session" in question or "traffic" in question:
            return InvestigationPlan(
                question=request.question,
                question_type="traffic_analysis",
                primary_metric="sessions" if "session" in question or "traffic" in question else "users",
                current_period=PlanPeriod(start=request.current_start, end_exclusive=request.current_end),
                comparison_period=PlanPeriod(start=request.previous_start, end_exclusive=request.previous_end),
                scope=scope,
                investigations=["traffic_kpi_comparison", "traffic_driver_analysis", "incident_retrieval"],
                tools=["run_traffic_investigation"],
            )
        campaign_metric = next(
            (metric for token, metric in (
                ("cpc", "cpc"), ("cost per click", "cpc"), ("ctr", "ctr"),
                ("click-through rate", "ctr"), ("cpa", "cpa"),
                ("cost per acquisition", "cpa"), ("roas", "roas"),
                ("conversion rate", "conversion_rate"),
            ) if token in question),
            None,
        )
        if campaign_metric and (scope.channel or scope.campaign or "campaign" in question):
            return InvestigationPlan(
                question=request.question,
                question_type="campaign_performance_analysis",
                primary_metric=campaign_metric,
                current_period=PlanPeriod(start=request.current_start, end_exclusive=request.current_end),
                comparison_period=PlanPeriod(start=request.previous_start, end_exclusive=request.previous_end),
                scope=scope,
                investigations=["campaign_kpi_comparison", "campaign_driver_analysis", "incident_retrieval"],
                tools=["run_campaign_performance_investigation"],
            )
        if "revenue" not in question:
            raise UnsupportedQuestionError(
                "The baseline workflow supports revenue and explicit campaign KPI investigations"
            )
        return InvestigationPlan(
            question=request.question,
            question_type="root_cause_analysis",
            primary_metric="revenue",
            current_period=PlanPeriod(start=request.current_start, end_exclusive=request.current_end),
            comparison_period=PlanPeriod(start=request.previous_start, end_exclusive=request.previous_end),
            scope=scope,
            investigations=[
                "kpi_comparison", "dimension_decomposition", "funnel_analysis",
                "statistical_validation", "incident_retrieval",
            ],
            tools=["run_revenue_investigation"],
        )
