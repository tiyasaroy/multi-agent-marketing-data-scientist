"""Deterministic Manager → tools → report → Critic workflow."""

from src.agents.critic_agent import CriticAgent
from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.reporting.executive_report import build_executive_report
from src.tools.analytics_tools import AnalyticsToolRegistry

from .state import WorkflowResponse, WorkflowState


class EvidenceValidationError(RuntimeError):
    """Raised when the Critic rejects the generated report."""


class InvestigationWorkflow:
    def __init__(self) -> None:
        self.manager = ManagerAgent()
        self.tools = AnalyticsToolRegistry()
        self.critic = CriticAgent()

    def run(self, request: InvestigationRequest) -> WorkflowResponse:
        state = WorkflowState(question=request.question)
        state.plan = self.manager.create_plan(request)
        for tool_name in state.plan.tools:
            state.evidence = self.tools.execute(tool_name, state.plan)
            state.executed_tools.append(tool_name)
        if state.evidence is None:
            raise RuntimeError("Investigation plan produced no evidence")
        state.executive_report = build_executive_report(state.evidence)
        state.critic_review = self.critic.review(
            state.executive_report, self._evidence_ids(state.evidence)
        )
        if not state.critic_review.approved:
            raise EvidenceValidationError("Critic rejected unsupported report claims")
        return WorkflowResponse(
            plan=state.plan,
            executed_tools=state.executed_tools,
            executive_report=state.executive_report,
            critic_review=state.critic_review,
            evidence=state.evidence,
        )

    @staticmethod
    def _evidence_ids(evidence) -> set:
        ids = {metric.evidence_id for metric in evidence.kpis.values()}
        for rows in evidence.decompositions.values():
            ids.update(row.evidence_id for row in rows)
        ids.update(row.evidence_id for row in evidence.overall_funnel)
        ids.update(row.evidence_id for row in evidence.leading_device_funnel)
        ids.update(row.evidence_id for row in evidence.related_incidents)
        ids.update(row.evidence_id for row in evidence.ranked_candidates)
        return ids
