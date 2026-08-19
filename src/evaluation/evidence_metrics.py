"""Evidence integrity metrics for completed workflows."""

from src.orchestration.state import WorkflowResponse


def evidence_valid(result: WorkflowResponse) -> bool:
    return result.critic_review.approved and not result.critic_review.unsupported_evidence_ids


def unsupported_claim_rate(result: WorkflowResponse) -> float:
    claims = (
        result.executive_report.summary
        + [result.executive_report.primary_driver]
        + result.executive_report.contributing_factors
        + result.executive_report.recommendations
    )
    if not claims:
        return 0.0
    invalid_claims = len(result.critic_review.errors)
    return min(invalid_claims / len(claims), 1.0)
