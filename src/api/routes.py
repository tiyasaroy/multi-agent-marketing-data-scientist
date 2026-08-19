"""HTTP routes for deterministic marketing investigations."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from src.agents.manager_agent import UnsupportedQuestionError
from src.analytics.root_cause_analysis import investigate_revenue_decline
from src.database.connection import connect
from src.orchestration.state import WorkflowResponse
from src.orchestration.workflow import InvestigationWorkflow

from .schemas import (
    HealthResponse,
    IncidentEvidence,
    InvestigationReport,
    InvestigationRequest,
    MetricDefinition,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    try:
        with connect(read_only=True) as connection:
            session_count = connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Analytics database is unavailable") from exc
    return HealthResponse(status="ok", database="duckdb", session_count=session_count)


@router.get("/metrics", response_model=List[MetricDefinition], tags=["metadata"])
def list_metrics() -> List[MetricDefinition]:
    with connect(read_only=True) as connection:
        result = connection.execute("SELECT * FROM metric_definitions ORDER BY metric_name")
        columns = [column[0] for column in result.description]
        return [MetricDefinition.model_validate(dict(zip(columns, row))) for row in result.fetchall()]


@router.get("/incidents", response_model=List[IncidentEvidence], tags=["metadata"])
def list_incidents() -> List[IncidentEvidence]:
    with connect(read_only=True) as connection:
        result = connection.execute(
            """SELECT 'inc_' || incident_id AS evidence_id,
                      incident_id, incident_date, title, root_cause, resolution, impact
               FROM marketing_incidents ORDER BY incident_date"""
        )
        columns = [column[0] for column in result.description]
        return [IncidentEvidence.model_validate(dict(zip(columns, row))) for row in result.fetchall()]


@router.post(
    "/investigations/revenue",
    response_model=InvestigationReport,
    tags=["investigations"],
)
def investigate_revenue(request: InvestigationRequest) -> InvestigationReport:
    with connect(read_only=True) as connection:
        report = investigate_revenue_decline(
            connection,
            request.current_start,
            request.current_end,
            request.previous_start,
            request.previous_end,
        )
    return InvestigationReport.model_validate(report)


@router.post(
    "/investigations/ask",
    response_model=WorkflowResponse,
    tags=["investigations"],
)
def ask(request: InvestigationRequest) -> WorkflowResponse:
    try:
        return InvestigationWorkflow().run(request)
    except UnsupportedQuestionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
