from pathlib import Path

from src.evaluation.evaluation_runner import EvaluationRunner


def test_benchmark_contains_all_injected_scenario_families():
    cases = EvaluationRunner.load_cases()
    assert len(cases) == 7
    assert len({case.case_id for case in cases}) == 7


def test_baseline_metrics_expose_supported_and_unsupported_cases():
    report = EvaluationRunner().run()
    assert report.metrics.total_cases == 7
    assert report.metrics.completed_cases == 5
    assert report.metrics.unsupported_cases == 2
    assert report.metrics.failed_cases == 0
    assert report.metrics.evidence_validity_rate == 1.0
    android = next(case for case in report.cases if case.case_id == "android_checkout_regression")
    assert android.primary_driver_correct is True
    assert android.funnel_transition_correct is True
    assert android.root_cause_correct is True
    india = next(case for case in report.cases if case.case_id == "india_revenue_decline")
    assert india.primary_driver_correct is True
    assert india.funnel_transition_correct is True
    assert india.root_cause_correct is True
    google = next(case for case in report.cases if case.case_id == "google_ads_cpc_increase")
    meta = next(case for case in report.cases if case.case_id == "meta_campaign_success")
    assert google.primary_driver_correct is True
    assert google.root_cause_correct is True
    assert meta.primary_driver_correct is True
    assert meta.root_cause_correct is True
    organic = next(case for case in report.cases if case.case_id == "organic_traffic_decline")
    assert organic.primary_driver_correct is True
    assert organic.root_cause_correct is True


def test_evaluation_report_is_serializable(tmp_path: Path):
    runner = EvaluationRunner()
    report = runner.run()
    output = tmp_path / "report.json"
    runner.write_report(report, output)
    assert output.exists()
    assert '"benchmark_version": "1.0"' in output.read_text(encoding="utf-8")
