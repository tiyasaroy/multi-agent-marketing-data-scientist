"""Compare replayed structured plans with the deterministic Manager baseline."""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.planning_comparison import compare_planning_providers
from src.planning.providers import DeterministicPlanningProvider, ReplayPlanningProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, help="JSON mapping question text to plan payload")
    parser.add_argument("--output", type=Path, default=Path("data/processed/planning_comparison.json"))
    args = parser.parse_args()
    if args.replay:
        candidate = ReplayPlanningProvider(json.loads(args.replay.read_text(encoding="utf-8")))
    else:
        candidate = DeterministicPlanningProvider(name="deterministic_candidate")
    report = compare_planning_providers(candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Candidate: {report.candidate_provider}")
    print(f"Valid plans: {report.valid_plan_rate:.1%}")
    print(f"Exact plan agreement: {report.exact_plan_agreement_rate:.1%}")
    print(f"Candidate workflow coverage: {report.candidate_benchmark_metrics['workflow_coverage']:.1%}")
    print(f"Candidate evidence validity: {report.candidate_benchmark_metrics['evidence_validity_rate']:.1%}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
