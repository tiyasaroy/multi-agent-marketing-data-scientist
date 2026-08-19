from pathlib import Path

from src.evaluation.evaluation_runner import EvaluationRunner


def test_benchmark_contains_all_injected_scenario_families():
    cases = EvaluationRunner.load_cases()
    assert len(cases) == 7
    assert len({case.case_id for case in cases}) == 7


def test_baseline_metrics_expose_supported_and_unsupported_cases():
    report = EvaluationRunner().run()
    assert report.metrics.total_cases == 7
    assert report.metrics.completed_cases == 2
    assert report.metrics.unsupported_cases == 5
    assert report.metrics.failed_cases == 0
    assert report.metrics.evidence_validity_rate == 1.0
    android = next(case for case in report.cases if case.case_id == "android_checkout_regression")
    assert android.primary_driver_correct is True
    assert android.funnel_transition_correct is True
    assert android.root_cause_correct is True


def test_evaluation_report_is_serializable(tmp_path: Path):
    runner = EvaluationRunner()
    report = runner.run()
    output = tmp_path / "report.json"
    runner.write_report(report, output)
    assert output.exists()
    assert '"benchmark_version": "1.0"' in output.read_text(encoding="utf-8")
