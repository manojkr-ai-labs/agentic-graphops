"""HTTP investigation start, rejected approve, recorded write, and session 2."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.graph.client import GraphGateway, GraphHandle, ToolFailure
from app.graph.seed import seed_graph
from app.main import create_app

QUESTION_1 = (
    "The payment service started failing after the latest deployment. "
    "Identify the likely change, the downstream systems, the engineer with "
    "the strongest relevant history, and the safest next action."
)
QUESTION_2 = (
    "A new payment failure looks similar. What did we decide last time, and who should own this?"
)
HEADERS = {"X-Tenant-Id": "acme", "X-Actor": "incident-commander"}


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
def client() -> tuple[TestClient, GraphGateway, str]:
    prefix = f"graphops_i{uuid4().hex[:8]}_"
    settings = _settings(graph_prefix=prefix)
    gateway = GraphGateway(settings)
    graph_name = gateway.tenant_graph_name("acme")
    assert graph_name is not None
    seed_graph(gateway, graph_name, "acme", reset=True)
    try:
        yield TestClient(create_app(settings)), gateway, graph_name
    finally:
        gateway.discard(graph_name)


def _decision_count(gateway: GraphGateway, graph_name: str) -> int:
    opened = gateway.open_graph(graph_name)
    assert isinstance(opened, GraphHandle)
    outcome = gateway.run_query(opened, "MATCH (d:Decision) RETURN count(d)")
    assert not isinstance(outcome, ToolFailure)
    return int(outcome.rows[0][0])


def test_post_question_1_returns_evidence(
    client: tuple[TestClient, GraphGateway, str],
) -> None:
    api, _gateway, _graph_name = client
    response = api.post(
        "/api/investigations",
        json={"sessionId": "ses_01", "question": QUESTION_1},
        headers=HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"]
    blob = json.dumps(body["evidence"], default=str)
    assert "DEP-1042" in blob or "E-17" in blob


def test_approve_without_token_writes_nothing(
    client: tuple[TestClient, GraphGateway, str],
) -> None:
    api, gateway, graph_name = client
    started = api.post(
        "/api/investigations",
        json={"sessionId": "ses_01", "question": QUESTION_1},
        headers=HEADERS,
    )
    investigation_id = started.json()["investigationId"]
    denied = api.post(
        f"/api/investigations/{investigation_id}/approve",
        json={},
        headers={"X-Actor": "incident-commander"},
    )
    assert denied.json()["status"] == "POLICY BLOCKED"
    assert _decision_count(gateway, graph_name) == 0


def test_approve_with_token_returns_recorded_simulated_notice(
    client: tuple[TestClient, GraphGateway, str],
) -> None:
    api, gateway, graph_name = client
    started = api.post(
        "/api/investigations",
        json={"sessionId": "ses_01", "question": QUESTION_1},
        headers=HEADERS,
    )
    body = started.json()
    token = body["action"]["approvalToken"]
    recorded = api.post(
        f"/api/investigations/{body['investigationId']}/approve",
        json={"approvalToken": token},
        headers={"X-Actor": "incident-commander"},
    )
    payload = recorded.json()
    assert payload["action"]["state"] == "RECORDED"
    assert payload["action"]["notice"] is not None
    assert "SIMULATED" in payload["action"]["notice"]
    assert _decision_count(gateway, graph_name) == 1


def test_new_session_reads_decision_from_graph(
    client: tuple[TestClient, GraphGateway, str],
) -> None:
    api, _gateway, _graph_name = client
    started = api.post(
        "/api/investigations",
        json={"sessionId": "ses_01", "question": QUESTION_1},
        headers=HEADERS,
    )
    first = started.json()
    api.post(
        f"/api/investigations/{first['investigationId']}/approve",
        json={"approvalToken": first["action"]["approvalToken"]},
        headers={"X-Actor": "incident-commander"},
    )
    later = api.post(
        "/api/investigations",
        json={"sessionId": "ses_02", "question": QUESTION_2},
        headers=HEADERS,
    )
    blob = json.dumps(later.json(), default=str)
    assert "DEC-203-1" in blob
    assert "DEP-1042" in blob
    assert "E-17" in blob
    assert "RES-44" in blob
