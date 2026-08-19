# Synthetic marketing dataset

This directory contains reproducible dummy data for the Multi-Agent Marketing Data Scientist project.

Generate it from the repository root:

```bash
python3 scripts/generate_data.py
```

The files cover customers, sessions, conversions, campaigns, daily campaign metrics, funnel events,
reviews, experiments, incidents, official KPI definitions, and injected anomaly ground truth.

The generator uses a fixed seed (`20260819`) and covers 2026-02-01 through 2026-07-31.
All data is fictional and contains no personal information.
