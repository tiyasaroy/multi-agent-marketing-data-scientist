import json
from datetime import date

import pytest

from src.agents.manager_agent import ManagerAgent
from src.api.schemas import InvestigationRequest
from src.planning.providers import (
    ConsensusPlanningProvider,
    DeterministicPlanningProvider,
    OllamaPlanningProvider,
    PlanningDecision,
    PlanningProviderUnavailableError,
)


def request():
    return InvestigationRequest(
        question="Why did revenue decline in India from July 20 to July 26?",
        current_start=date(2026, 7, 20), current_end=date(2026, 7, 27),
        previous_start=date(2026, 7, 13), previous_end=date(2026, 7, 20),
    )


def test_ollama_provider_sends_schema_constrained_non_streaming_request():
    captured = {}

    def transport(url, payload, timeout):
        captured.update(url=url, payload=payload, timeout=timeout)
        plan = ManagerAgent().create_plan(request()).model_dump(mode="json")
        decision = PlanningDecision(
            question_type=plan["question_type"], primary_metric=plan["primary_metric"],
            scope=plan["scope"],
        ).model_dump(mode="json")
        return {"message": {"role": "assistant", "content": json.dumps(decision)}}

    provider = OllamaPlanningProvider(
        model="test-model", host="http://localhost:11434/", timeout_seconds=9, transport=transport
    )
    plan = provider.create_plan(request())
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["payload"]["model"] == "test-model"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["think"] is False
    assert captured["payload"]["options"]["temperature"] == 0
    assert captured["payload"]["format"]["title"] == "PlanningDecision"
    assert captured["timeout"] == 9
    assert plan.scope.country == "India"


def test_ollama_falls_back_only_when_service_is_unavailable():
    def unavailable(*_):
        raise PlanningProviderUnavailableError("offline")

    provider = OllamaPlanningProvider(
        transport=unavailable, fallback=DeterministicPlanningProvider()
    )
    assert provider.create_plan(request()).question_type == "root_cause_analysis"


def test_ollama_invalid_content_is_not_hidden_by_fallback():
    provider = OllamaPlanningProvider(
        transport=lambda *_: {"message": {"content": "not json"}},
        fallback=DeterministicPlanningProvider(),
    )
    with pytest.raises(ValueError, match="invalid structured decision"):
        provider.create_plan(request())


def test_planning_provider_environment_switch(monkeypatch):
    from src.planning.providers import planning_provider_from_env

    monkeypatch.setenv("PLANNING_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "local-test")
    provider = planning_provider_from_env()
    assert isinstance(provider, ConsensusPlanningProvider)
    assert isinstance(provider.candidate, OllamaPlanningProvider)
    assert provider.candidate.model == "local-test"


def test_consensus_rejects_candidate_that_omits_explicit_scope():
    class MissingScopeProvider:
        name = "missing-scope"

        def create_plan(self, investigation_request):
            plan = ManagerAgent().create_plan(investigation_request)
            return plan.model_copy(update={"scope": plan.scope.model_copy(update={"country": None})})

    provider = ConsensusPlanningProvider(MissingScopeProvider())
    plan = provider.create_plan(request())
    assert plan.scope.country == "India"
    assert provider.accepted == 0
    assert provider.fallbacks == 1


def test_consensus_accepts_matching_candidate():
    provider = ConsensusPlanningProvider(DeterministicPlanningProvider(name="candidate"))
    assert provider.create_plan(request()).scope.country == "India"
    assert provider.accepted == 1
    assert provider.fallbacks == 0
