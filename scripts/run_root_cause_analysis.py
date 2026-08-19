#!/usr/bin/env python3
"""Run the deterministic analysis for the known July checkout incident."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.root_cause_analysis import investigate_revenue_decline
from src.database.connection import connect


with connect(read_only=True) as connection:
    report = investigate_revenue_decline(
        connection,
        current_start=date(2026, 7, 20), current_end=date(2026, 7, 27),
        previous_start=date(2026, 7, 13), previous_end=date(2026, 7, 20),
    )

revenue = report["kpis"]["revenue"]
conversion_rate = report["kpis"]["conversion_rate"]
print("Revenue root-cause analysis: 2026-07-20 to 2026-07-26")
print(f"Revenue change: {revenue['absolute_change']:.2f} ({revenue['percent_change']:.1%})")
print(f"Conversion-rate change: {conversion_rate['percent_change']:.1%}")
print("\nLeading evidence:")
for candidate in report["ranked_candidates"][:8]:
    label = candidate.get("transition") or f"{candidate['dimension']}={candidate['segment']}"
    print(f"- {label}: score={candidate['score']:.3f}")
print("\nRelated incidents:")
for incident in report["related_incidents"]:
    print(f"- {incident['title']}: {incident['root_cause']}")

output = Path("data/processed/root_cause_report.json")
output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
print(f"\nStructured report written to {output}")
