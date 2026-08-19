# Ollama Planner Validation

Validated on 2026-08-19 with local Ollama 0.32.0 and `qwen3:8b` across the seven-case
planning and workflow benchmark.

## Results

| Configuration | Valid plans | Exact plan agreement | Workflow coverage | Evidence validity |
| --- | ---: | ---: | ---: | ---: |
| Raw `qwen3:8b` after schema and scope hardening | 71.4% | 57.1% | 71.4% | 100.0% |
| Guarded `ConsensusPlanningProvider` | 100.0% | 100.0% | 100.0% | 100.0% |

In the guarded run, four of seven Ollama decisions exactly matched the deterministic
planner and were accepted. Three decisions were rejected and replaced with deterministic
plans. The raw mismatches involved a missing channel scope and invented country or customer
segment filters.

## Interpretation

`qwen3:8b` is useful as a free, local advisory classifier, but the raw model is not reliable
enough to control production planning on its own. The production configuration therefore
requires exact agreement on question type, primary metric, and scope. Dates, investigations,
and tool selection are always materialized by deterministic code. If Ollama is unavailable,
returns invalid output, or disagrees with the baseline, the deterministic plan is used.

This design preserves local-LLM experimentation while preventing model hallucinations from
changing filters, executing the wrong workflow, or contaminating validated evidence.

## Reproduction

```bash
python scripts/compare_ollama_planner.py --model qwen3:8b
python scripts/compare_ollama_planner.py --model qwen3:8b --consensus
```

The guarded configuration is the default when `PLANNING_PROVIDER=ollama`. Raw-model behavior
is available only when `OLLAMA_REQUIRE_CONSENSUS=false` is explicitly set.
