"""Investigation loop with the fake LLM. Rows still come from FalkorDB."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.agent.loop import LoopResult, run_loop
from app.agent.validate import citation_errors
from app.api.investigations import InvestigationService
from app.config import Settings
from app.domain.models import Recommendation
from app.graph.client import GraphGateway, GraphHandle, ToolFailure
from app.graph.seed import seed_graph
from app.llm.client import FakeLlm
from app.obs.log import configure_logging

QUESTION_1 = (
    "The payment service started failing after the latest deployment. "
    "Identify the likely change, the downstream systems, the engineer with "
    "the strongest relevant history, and the safest next action."
)


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "falkordb_host": "localhost",
        "falkordb_port": 6379,
        "falkordb_password": "",
        "graph_prefix": "graphops_",
        "llm_base_url": "http://localhost:11434/v1",
        "llm_api_key": "",
        "llm_model": "local",
        "query_timeout_ms": 2000,
        "max_depth": 4,
        "max_nodes": 50,
        "max_rels": 100,
        "max_agent_iterations": 8,
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
def env() -> tuple[Settings, GraphGateway, str]:
    prefix = f"graphops_a{uuid4().hex[:8]}_"
    settings = _settings(graph_prefix=prefix)
    gateway = GraphGateway(settings)
    graph_name = gateway.tenant_graph_name("acme")
    assert graph_name is not None
    seed_graph(gateway, graph_name, "acme", reset=True)
    try:
        yield settings, gateway, graph_name
    finally:
        gateway.discard(graph_name)


def _decisions(gateway: GraphGateway, graph_name: str) -> list[list[object]]:
    opened = gateway.open_graph(graph_name)
    assert isinstance(opened, GraphHandle)
    outcome = gateway.run_query(opened, "MATCH (d:Decision) RETURN count(d)")
    assert not isinstance(outcome, ToolFailure)
    return outcome.rows


def test_question_1_cites_ids_and_awaits_approval(
    env: tuple[Settings, GraphGateway, str],
) -> None:
    settings, gateway, graph_name = env
    service = InvestigationService(settings, gateway, configure_logging("INFO"))
    body = service.start(
        tenant="acme",
        actor="incident-commander",
        session_id="ses_01",
        question=QUESTION_1,
        request_id="req-q1",
        planner=FakeLlm(),
    )
    blob = json.dumps(body, default=str)
    assert "DEP-1042" in blob
    assert "E-17" in blob
    assert body["action"]["state"] == "AWAITING_APPROVAL"
    assert _decisions(gateway, graph_name) == [[0]]


def test_synthesizer_rollback_of_dep_1038_fails_validation(
    env: tuple[Settings, GraphGateway, str],
) -> None:
    settings, gateway, _graph_name = env
    outcome = run_loop(
        gateway,
        "acme",
        QUESTION_1,
        "ses_01",
        "incident-commander",
        settings,
        FakeLlm(),
    )
    assert isinstance(outcome, LoopResult)
    assert outcome.recommendation is not None
    bad = Recommendation(
        summary=outcome.recommendation.summary,
        based_on_query_ids=outcome.recommendation.based_on_query_ids,
        rollback_candidate="DEP-1038",
        assignee_id=outcome.recommendation.assignee_id,
        assignee_name=outcome.recommendation.assignee_name,
    )
    assert citation_errors(bad, outcome.evidence)

    failed = run_loop(
        gateway,
        "acme",
        QUESTION_1,
        "ses_01",
        "incident-commander",
        settings,
        FakeLlm(rollback="DEP-1038"),
    )
    assert isinstance(failed, LoopResult)
    assert failed.status == "SYSTEM ERROR"
    assert failed.recommendation is None
    assert failed.evidence


def test_iteration_cap_stops_the_loop(env: tuple[Settings, GraphGateway, str]) -> None:
    settings, gateway, _graph_name = env
    capped = _settings(graph_prefix=settings.graph_prefix, max_agent_iterations=2)
    outcome = run_loop(
        gateway,
        "acme",
        QUESTION_1,
        "ses_01",
        "incident-commander",
        capped,
        FakeLlm(never_stop=True),
    )
    assert isinstance(outcome, LoopResult)
    assert len(outcome.evidence) == 2
    assert outcome.status == "PARTIAL RESULT"
    assert outcome.proposal is None
