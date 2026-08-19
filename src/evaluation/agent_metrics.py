"""Case-level comparison helpers for agent outputs."""

from typing import Iterable

from src.evaluation.models import BenchmarkCase, ExpectedDriver
from src.orchestration.state import WorkflowResponse


def driver_matches(actual_dimension: str, actual_segment: str, expected: ExpectedDriver) -> bool:
    return (
        actual_dimension.casefold() == expected.dimension.casefold()
        and actual_segment.casefold() == expected.segment.casefold()
    )


def top_driver_recall(result: WorkflowResponse, expected: Iterable[ExpectedDriver]) -> float:
    expected_list = list(expected)
    if not expected_list:
        return 1.0
    actual = result.evidence.ranked_candidates[:3]
    matched = sum(
        any(driver_matches(candidate.dimension, candidate.segment, driver) for candidate in actual)
        for driver in expected_list
    )
    return matched / len(expected_list)


def funnel_match(result: WorkflowResponse, case: BenchmarkCase) -> bool:
    if case.expected_funnel_transition is None:
        return True
    return any(
        candidate.transition == case.expected_funnel_transition
        for candidate in result.evidence.ranked_candidates
        if candidate.candidate_type == "funnel_driver"
    )


def root_cause_match(result: WorkflowResponse, case: BenchmarkCase) -> bool:
    expected = case.expected_root_cause_contains.casefold()
    return any(expected in incident.root_cause.casefold() for incident in result.evidence.related_incidents)
