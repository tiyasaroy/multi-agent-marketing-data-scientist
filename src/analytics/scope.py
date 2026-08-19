"""Allowlisted SQL scope construction and stable evidence identity helpers."""

from __future__ import annotations

from typing import Mapping


SCOPE_COLUMNS = {
    "country": "sf.country",
    "device": "sf.device",
    "channel": "sf.traffic_source",
    "campaign": "COALESCE(c.campaign_name, 'Unattributed')",
    "customer_segment": "cu.customer_segment",
}


def scope_clause(scope: Mapping[str, str] | None) -> tuple[str, list[str]]:
    scope = scope or {}
    unknown = set(scope) - set(SCOPE_COLUMNS)
    if unknown:
        raise ValueError(f"Unsupported scope dimensions: {sorted(unknown)}")
    ordered = [(name, scope[name]) for name in SCOPE_COLUMNS if scope.get(name) is not None]
    if not ordered:
        return "", []
    return " AND " + " AND ".join(f"{SCOPE_COLUMNS[name]} = ?" for name, _ in ordered), [
        value for _, value in ordered
    ]


def scope_identity(scope: Mapping[str, str] | None) -> str:
    scope = scope or {}
    parts = [f"{name}={scope[name]}" for name in SCOPE_COLUMNS if scope.get(name) is not None]
    return ";".join(parts) if parts else "global"
