# Agent Evaluation Baseline

Benchmark version: **1.0**  
Baseline recorded: **2026-08-19**

This benchmark measures the deterministic Manager → analytics tool → reporter → Critic workflow
against seven known scenarios injected into the synthetic dataset. Unsupported questions count as
coverage failures instead of being silently excluded from accuracy metrics.

## Aggregate results

| Metric | Result |
|---|---:|
| Benchmark cases | 7 |
| Completed cases | 2 |
| Unsupported cases | 5 |
| Failed executions | 0 |
| Workflow coverage | 28.6% |
| Classification accuracy | 28.6% |
| Primary-driver accuracy | 14.3% |
| Mean top-three driver recall | 14.3% |
| Funnel-transition accuracy | 28.6% |
| Root-cause accuracy | 14.3% |
| Evidence validity among completed cases | 100.0% |
| Unsupported-claim rate among completed cases | 0.0% |
| Tool success rate | 28.6% |

Latency is intentionally not treated as a fixed golden value because it varies by machine. Local
completed-case runs are currently measured in tens of milliseconds.

## Case-level analysis

| Case | Status | Primary driver | Funnel | Root cause | Interpretation |
|---|---|---:|---:|---:|---|
| Android checkout regression | Completed | Pass | Pass | Pass | The baseline correctly identifies Android, the checkout-to-payment deterioration, and the payment SDK incident. |
| Google Ads CPC increase | Unsupported | — | — | — | A campaign performance workflow and paid-media KPI tools are not implemented yet. |
| Organic traffic decline | Unsupported | — | — | — | The Manager cannot yet route traffic and acquisition questions. |
| Attribution tracking failure | Unsupported | — | — | — | Attribution-completeness and data-quality tools are not available yet. |
| Negative review spike | Unsupported | — | — | — | Review topic and sentiment analysis are not implemented yet. |
| Meta campaign success | Unsupported | — | — | — | Campaign lift and experimentation analysis are not implemented yet. |
| India revenue decline | Completed | Fail | Pass | Fail | The revenue workflow runs globally and does not yet apply the geographic scope expressed in the question. |

## What the baseline proves

- The supported Android incident executes without runtime failures.
- Every completed executive claim references validated evidence.
- The Critic produces a 0% unsupported-claim rate.
- Unsupported question families fail explicitly instead of generating fabricated analyses.
- Low end-to-end accuracy is caused primarily by limited workflow coverage, not evidence integrity.

## Recommended implementation priorities

1. **Scoped revenue investigations** — add explicit country, device, channel, and campaign filters to
   the request, Manager plan, analytics tool, and evidence output. This should address the India case
   without weakening the successful Android case.
2. **Campaign performance workflow** — implement CPC, CTR, CPA, and ROAS comparisons for Google Ads
   and Meta campaign questions.
3. **Traffic and attribution workflows** — support organic-session changes and missing campaign IDs.
4. **Sentiment workflow** — classify review topics and quantify negative-review changes.
5. **Experiment workflow** — evaluate campaign and experiment conversion lift with statistical tests.

The benchmark should be rerun after every new workflow. Coverage and task accuracy should improve
while evidence validity remains at 100% and unsupported-claim rate remains at 0%.
