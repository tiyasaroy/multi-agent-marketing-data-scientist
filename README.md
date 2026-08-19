# Multi-Agent Marketing Data Scientist

An evidence-backed marketing analytics project designed to investigate business questions such as
why revenue, conversions, or campaign performance changed.

This initial foundation includes:

- reproducible synthetic e-commerce and marketing data;
- deliberately injected, machine-readable business anomalies;
- a DuckDB analytical schema and repeatable data loader;
- canonical revenue and conversion KPI calculations;
- current-period versus previous-period comparisons; and
- root-cause decomposition by device, country, channel, campaign, and customer segment;
- sequential funnel-drop analysis and ranked evidence candidates; and
- automated tests for KPI correctness and the known checkout incident.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/initialize_database.py
python scripts/run_kpi_example.py
python scripts/run_root_cause_analysis.py
python -m pytest -q
```

The generated CSV files are stored in `data/synthetic/`. The local DuckDB database is created at
`data/processed/marketing.duckdb` and is intentionally excluded from version control because it can
be rebuilt from the committed source data.

## Known synthetic incident

The week beginning 2026-07-20 contains an Android checkout regression concentrated in India. It is
expected to produce a material decline in conversion rate and revenue while sessions remain broadly
stable. Ground-truth scenario definitions are available in
`data/synthetic/anomaly_ground_truth.csv` for future agent evaluation.

## Root-cause example

`scripts/run_root_cause_analysis.py` compares 2026-07-20–26 with the preceding week and writes a
structured evidence report to `data/processed/root_cause_report.json`. Generated reports remain local
because they can be reproduced from the committed data.
