"""Deterministic executive report generator."""

from src.api.schemas import InvestigationReport
from src.orchestration.state import EvidenceClaim, ExecutiveReport


def build_executive_report(evidence: InvestigationReport) -> ExecutiveReport:
    """Create prose only from validated calculated evidence."""
    if evidence.question_type == "campaign_performance_analysis":
        return _build_campaign_report(evidence)
    if evidence.question_type == "traffic_analysis":
        return _build_traffic_report(evidence)
    if evidence.question_type == "data_quality_analysis":
        return _build_attribution_report(evidence)
    if evidence.question_type == "sentiment_analysis":
        return _build_sentiment_report(evidence)
    revenue = evidence.kpis["revenue"]
    conversion_rate = evidence.kpis["conversion_rate"]
    primary = evidence.ranked_candidates[0]
    funnel_candidates = [
        candidate for candidate in evidence.ranked_candidates
        if candidate.candidate_type == "funnel_driver"
    ]
    funnel = funnel_candidates[0] if funnel_candidates else None
    incident = evidence.related_incidents[0] if evidence.related_incidents else None
    scope_label = ", ".join(
        f"{dimension}={value}" for dimension, value in evidence.applied_scope.items()
    )

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
        title=(f"Revenue decline investigation ({scope_label})" if scope_label else "Revenue decline investigation"),
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
            (
                f"All evidence in this report is filtered to {scope_label}."
                if scope_label else
                "This report uses global data because no explicit scope was requested."
            ),
        ],
    )


def _build_campaign_report(evidence: InvestigationReport) -> ExecutiveReport:
    metric = evidence.kpis[evidence.metric]
    primary = evidence.ranked_candidates[0]
    incident = evidence.related_incidents[0] if evidence.related_incidents else None
    scope_label = ", ".join(f"{key}={value}" for key, value in evidence.applied_scope.items())
    recommendations = [EvidenceClaim(
        claim_id="campaign_recommendation",
        text=f"Review {primary.dimension}={primary.segment} and the inputs to {evidence.metric.upper()}.",
        evidence_ids=[primary.evidence_id],
    )]
    if incident:
        recommendations.append(EvidenceClaim(
            claim_id="campaign_incident",
            text=f"Investigate the documented cause: {incident.root_cause}.",
            evidence_ids=[incident.evidence_id],
        ))
    return ExecutiveReport(
        title=f"Campaign performance investigation ({scope_label or 'all campaigns'})",
        summary=[EvidenceClaim(
            claim_id="campaign_metric_change",
            text=f"{evidence.metric.upper()} changed by {metric.percent_change:.1%} versus the previous period.",
            evidence_ids=[metric.evidence_id],
        )],
        primary_driver=EvidenceClaim(
            claim_id="primary_driver",
            text=f"The leading campaign driver was {primary.dimension}={primary.segment}.",
            evidence_ids=[primary.evidence_id],
        ),
        contributing_factors=[], recommendations=recommendations,
        limitations=["Campaign KPI comparisons are observational and do not establish causality.",
                     f"Applied campaign scope: {scope_label or 'none'}."],
    )


def _build_traffic_report(evidence: InvestigationReport) -> ExecutiveReport:
    metric = evidence.kpis[evidence.metric]
    primary = evidence.ranked_candidates[0]
    incident = evidence.related_incidents[0] if evidence.related_incidents else None
    scope_label = ", ".join(f"{key}={value}" for key, value in evidence.applied_scope.items())
    recommendations = [EvidenceClaim(
        claim_id="traffic_recommendation",
        text=f"Review acquisition and landing-page performance for {primary.dimension}={primary.segment}.",
        evidence_ids=[primary.evidence_id],
    )]
    if incident:
        recommendations.append(EvidenceClaim(
            claim_id="traffic_incident",
            text=f"Investigate the documented cause: {incident.root_cause}.",
            evidence_ids=[incident.evidence_id],
        ))
    return ExecutiveReport(
        title=f"Traffic investigation ({scope_label or 'all traffic'})",
        summary=[EvidenceClaim(
            claim_id="traffic_metric_change",
            text=f"{evidence.metric.title()} changed by {metric.percent_change:.1%} versus the previous period.",
            evidence_ids=[metric.evidence_id],
        )],
        primary_driver=EvidenceClaim(
            claim_id="primary_driver",
            text=f"The leading traffic driver was {primary.dimension}={primary.segment}.",
            evidence_ids=[primary.evidence_id],
        ),
        contributing_factors=[], recommendations=recommendations,
        limitations=["Traffic comparisons are observational and do not establish causality.",
                     f"Applied traffic scope: {scope_label or 'none'}."],
    )


def _build_attribution_report(evidence: InvestigationReport) -> ExecutiveReport:
    completeness = evidence.kpis["attribution_completeness"]
    unattributed = evidence.kpis["unattributed_sessions"]
    primary = evidence.ranked_candidates[0]
    incident = evidence.related_incidents[0] if evidence.related_incidents else None
    recommendations = [EvidenceClaim(
        claim_id="attribution_recommendation",
        text="Audit campaign-ID collection and preserve raw attribution parameters through session creation.",
        evidence_ids=[primary.evidence_id],
    )]
    if incident:
        recommendations.append(EvidenceClaim(
            claim_id="attribution_incident",
            text=f"Investigate the documented cause: {incident.root_cause}.",
            evidence_ids=[incident.evidence_id],
        ))
    return ExecutiveReport(
        title="Campaign attribution quality investigation",
        summary=[
            EvidenceClaim(
                claim_id="attribution_completeness_change",
                text=f"Attribution completeness changed by {completeness.percent_change:.1%}.",
                evidence_ids=[completeness.evidence_id],
            ),
                EvidenceClaim(
                    claim_id="unattributed_session_change",
                    text=(
                        f"Unattributed sessions changed by {unattributed.percent_change:.1%}."
                        if unattributed.percent_change is not None else
                        f"Unattributed sessions increased from {unattributed.previous:.0f} "
                        f"to {unattributed.current:.0f}."
                    ),
                evidence_ids=[unattributed.evidence_id],
            ),
        ],
        primary_driver=EvidenceClaim(
            claim_id="primary_driver",
            text=f"The leading data-quality driver was {primary.dimension}={primary.segment}.",
            evidence_ids=[primary.evidence_id],
        ),
        contributing_factors=[], recommendations=recommendations,
        limitations=["Missing campaign IDs identify an instrumentation gap but not the point of failure."],
    )


def _build_sentiment_report(evidence: InvestigationReport) -> ExecutiveReport:
    negative_rate = evidence.kpis["negative_review_rate"]
    primary = evidence.ranked_candidates[0]
    incident = evidence.related_incidents[0] if evidence.related_incidents else None
    recommendations = [EvidenceClaim(
        claim_id="review_recommendation",
        text=f"Prioritize product diagnostics and support review for topic={primary.segment}.",
        evidence_ids=[primary.evidence_id],
    )]
    if incident:
        recommendations.append(EvidenceClaim(
            claim_id="review_incident",
            text=f"Investigate the documented cause: {incident.root_cause}.",
            evidence_ids=[incident.evidence_id],
        ))
    return ExecutiveReport(
        title="Negative app-review investigation",
        summary=[EvidenceClaim(
            claim_id="negative_review_rate_change",
            text=f"The negative-review rate changed by {negative_rate.percent_change:.1%}.",
            evidence_ids=[negative_rate.evidence_id],
        )],
        primary_driver=EvidenceClaim(
            claim_id="primary_driver",
            text=f"The leading review topic was {primary.segment}.",
            evidence_ids=[primary.evidence_id],
        ),
        contributing_factors=[], recommendations=recommendations,
        limitations=["Topic labels use an explicit keyword lexicon and do not infer intent or causality."],
    )
