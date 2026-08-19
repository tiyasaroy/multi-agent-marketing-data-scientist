"""Deterministic analytics tools."""

from .contribution_analysis import decompose_metric
from .funnel_analysis import compare_funnels
from .kpi_engine import compare_periods, period_kpis
from .root_cause_analysis import investigate_revenue_decline

__all__ = [
    "compare_funnels", "compare_periods", "decompose_metric",
    "investigate_revenue_decline", "period_kpis",
]
