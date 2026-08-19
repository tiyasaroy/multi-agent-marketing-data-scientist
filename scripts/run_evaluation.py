#!/usr/bin/env python3
"""Evaluate the deterministic agent workflow against ground truth."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.evaluation_runner import EvaluationRunner

runner = EvaluationRunner()
report = runner.run()
output = Path("data/processed/evaluation_report.json")
runner.write_report(report, output)
metrics = report.metrics

print("Agent benchmark v1.0")
print(f"Cases: {metrics.total_cases}")
print(f"Completed: {metrics.completed_cases}")
print(f"Unsupported: {metrics.unsupported_cases}")
print(f"Failed: {metrics.failed_cases}")
print(f"Workflow coverage: {metrics.workflow_coverage:.1%}")
print(f"Classification accuracy: {metrics.classification_accuracy:.1%}")
print(f"Primary-driver accuracy: {metrics.primary_driver_accuracy:.1%}")
print(f"Top-3 driver recall: {metrics.mean_top_three_driver_recall:.1%}")
print(f"Funnel accuracy: {metrics.funnel_accuracy:.1%}")
print(f"Root-cause accuracy: {metrics.root_cause_accuracy:.1%}")
print(f"Evidence validity: {metrics.evidence_validity_rate:.1%}")
print(f"Unsupported-claim rate: {metrics.unsupported_claim_rate:.1%}")
print(f"Tool success rate: {metrics.tool_success_rate:.1%}")
print(f"Average completed latency: {metrics.average_completed_latency_ms:.1f} ms")
print(f"Report written to {output}")
