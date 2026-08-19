#!/usr/bin/env python3
"""Run the planner benchmark against a local Ollama model."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.planning_comparison import compare_planning_providers
from src.planning.providers import ConsensusPlanningProvider, OllamaPlanningProvider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument(
        "--consensus", action="store_true",
        help="Fall back to the deterministic plan whenever Ollama disagrees or is invalid.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/ollama_planning_comparison.json")
    )
    args = parser.parse_args()
    ollama = OllamaPlanningProvider(
        model=args.model, host=args.host, timeout_seconds=args.timeout
    )
    provider = ConsensusPlanningProvider(ollama) if args.consensus else ollama
    report = compare_planning_providers(provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"Candidate: {report.candidate_provider}")
    print(f"Valid plans: {report.valid_plan_rate:.1%}")
    print(f"Exact plan agreement: {report.exact_plan_agreement_rate:.1%}")
    print(f"Workflow coverage: {report.candidate_benchmark_metrics['workflow_coverage']:.1%}")
    print(f"Evidence validity: {report.candidate_benchmark_metrics['evidence_validity_rate']:.1%}")
    if isinstance(provider, ConsensusPlanningProvider):
        print(f"Ollama decisions accepted: {provider.accepted}")
        print(f"Deterministic fallbacks: {provider.fallbacks}")
    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
