"""Validate executive claims against collected evidence."""

from typing import Iterable, Set

from src.orchestration.state import CriticReview, EvidenceClaim, ExecutiveReport


class CriticAgent:
    """Reject claims with missing or fabricated evidence references."""

    def review(self, report: ExecutiveReport, valid_evidence_ids: Set[str]) -> CriticReview:
        errors = []
        unsupported = set()
        for claim in self._claims(report):
            if not claim.evidence_ids:
                errors.append(f"Claim {claim.claim_id} has no evidence references")
            unknown = set(claim.evidence_ids) - valid_evidence_ids
            if unknown:
                unsupported.update(unknown)
                errors.append(
                    f"Claim {claim.claim_id} references unknown evidence: {sorted(unknown)}"
                )
        return CriticReview(
            approved=not errors,
            errors=errors,
            unsupported_evidence_ids=sorted(unsupported),
        )

    @staticmethod
    def _claims(report: ExecutiveReport) -> Iterable[EvidenceClaim]:
        yield from report.summary
        yield report.primary_driver
        yield from report.contributing_factors
        yield from report.recommendations
