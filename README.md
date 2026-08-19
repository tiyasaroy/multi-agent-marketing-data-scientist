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
- a FastAPI service with validated Pydantic request and evidence contracts; and
- a deterministic Manager, controlled tool registry, executive reporter, and evidence Critic; and
- validated country, device, channel, campaign, and customer-segment scopes for revenue investigations;
- deterministic campaign CPC, CTR, CPA, ROAS, and conversion-rate comparisons;
- scoped traffic analysis across channel, device, country, and landing page;
- deterministic campaign-attribution completeness and missing-ID analysis;
- deterministic negative-review rate and keyword-topic analysis;
- treatment-versus-control experiment lift, confidence interval, significance, and power analysis;
- provider-neutral structured LLM planning with immutable-date and allowlisted-tool validation;
- deterministic-versus-provider plan agreement and workflow benchmark comparison;
- a seven-case ground-truth evaluation benchmark with coverage and evidence-integrity metrics; and
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
python scripts/run_evaluation.py
python -m pytest -q
uvicorn src.api.main:app --reload
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

## API

After starting Uvicorn, open `http://127.0.0.1:8000/docs` for interactive API documentation.
Available endpoints include `GET /health`, `GET /metrics`, `GET /incidents`,
`POST /investigations/revenue`, and `POST /investigations/ask`.

The `/investigations/ask` workflow is API-key-free: the Manager creates a validated plan, an
allowlisted read-only tool executes the analysis, the reporter attaches evidence IDs to every claim,
and the Critic rejects unsupported references before a response is returned.
Explicit scope values in a question (for example, `revenue decline in India`) are applied to every
KPI, decomposition, funnel, and related-anomaly query and are included in evidence identity.

## Evaluation

`scripts/run_evaluation.py` evaluates the workflow against seven injected scenario families. The
report intentionally counts unsupported questions as coverage gaps. Revenue and campaign
performance, traffic, attribution-quality, review-sentiment, and controlled experiment questions
are supported.
The initial results and case-level analysis are documented in
[`docs/evaluation_baseline.md`](docs/evaluation_baseline.md).

## Optional planning providers

The default workflow uses the deterministic Manager. A vendor SDK can be adapted through
`StructuredLLMPlanningProvider` by supplying a structured-output callable. The provider may classify
questions and propose validated plans, but it cannot change request dates, select unregistered tools,
or calculate evidence. Analytics execution, report generation, and Critic validation remain
deterministic.

Use `python scripts/compare_planners.py` for a baseline smoke comparison, or provide
`--replay plans.json` to evaluate previously captured structured LLM plans without making paid API
calls. The resulting report compares plan agreement, workflow coverage, and evidence validity.

### Ollama

Ollama can provide local structured plans through its `/api/chat` endpoint. Install and start Ollama,
then download a model appropriate for the machine:

```bash
ollama serve
ollama pull qwen3:8b
```

Enable it for the API while retaining deterministic analytics execution:

```bash
PLANNING_PROVIDER=ollama OLLAMA_MODEL=qwen3:8b uvicorn src.api.main:app --reload
```

`OLLAMA_HOST` defaults to `http://127.0.0.1:11434`, and `OLLAMA_TIMEOUT_SECONDS` defaults to `120`.
Set `OLLAMA_DETERMINISTIC_FALLBACK=true` to fall back only when the Ollama service is unavailable;
invalid model output is still rejected. Run a full comparison with:

```bash
python scripts/compare_ollama_planner.py --model qwen3:8b
```
