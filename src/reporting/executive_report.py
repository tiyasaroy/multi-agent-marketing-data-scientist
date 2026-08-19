"""Deterministic executive report generator."""

from src.api.schemas import InvestigationReport
from src.orchestration.state import EvidenceClaim, ExecutiveReport


def build_executive_report(evidence: InvestigationReport) -> ExecutiveReport:
    """Create prose only from validated calculated evidence."""
    revenue = evidence.kpis["revenue"]
    conversion_rate = evidence.kpis["conversion_rate"]
    primary = evidence.ranked_candidates[0]
    funnel_candidates = [
        candidate for candidate in evidence.ranked_candidates
        if candidate.candidate_type == "funnel_driver"
    ]
    funnel = funnel_candidates[0] if funnel_candidates else None
    incident = evidence.related_incidents[0] if evidence.related_incidents else None

    contributing = []
    if funnel is not None:
        contributing.append(EvidenceClaim(
            claim_id="funnel_drop",
            text=f"The largest diagnostic funnel deterioration was {funnel.transition} for {funnel.segment}.",
            evidence_ids=[funnel.evidence_id],
        ))
    for index, candidate in enumerate(evidence.ranked_candidates[1:3], start=1):
        contributing.append(EvidenceClaim(
            claim_id=f"contributor_{index}",
            text=f"{candidate.dimension}={candidate.segment} was an additional negative driver.",
            evidence_ids=[candidate.evidence_id],
        ))

    recommendations = [EvidenceClaim(
        claim_id="recommendation_diagnostic",
        text=f"Prioritize diagnostics for {primary.segment} and validate the affected conversion path.",
        evidence_ids=[primary.evidence_id] + ([funnel.evidence_id] if funnel else []),
    )]
    if incident is not None:
        recommendations.append(EvidenceClaim(
            claim_id="recommendation_incident",
            text=f"Review the documented resolution: {incident.resolution}.",
            evidence_ids=[incident.evidence_id],
        ))

    return ExecutiveReport(
        title="Revenue decline investigation",
        summary=[
            EvidenceClaim(
                claim_id="revenue_change",
                text=f"Revenue changed by {revenue.percent_change:.1%} versus the previous period.",
                evidence_ids=[revenue.evidence_id],
            ),
            EvidenceClaim(
                claim_id="conversion_change",
                text=f"Conversion rate changed by {conversion_rate.percent_change:.1%}, indicating a conversion-led decline.",
                evidence_ids=[conversion_rate.evidence_id],
            ),
        ],
        primary_driver=EvidenceClaim(
            claim_id="primary_driver",
            text=f"The leading dimensional driver was {primary.dimension}={primary.segment}.",
            evidence_ids=[primary.evidence_id],
        ),
        contributing_factors=contributing,
        recommendations=recommendations,
        limitations=[
            "Contribution and funnel evidence identify likely drivers, not experimental causality.",
            "This baseline supports revenue root-cause questions with explicit comparison dates only.",
        ],
    )
