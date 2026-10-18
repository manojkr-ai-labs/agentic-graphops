"""Read tools against a disposable acme graph in FalkorDB."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.config import Settings
from app.graph.client import GraphGateway, GraphHandle, ToolFailure
from app.graph.seed import seed_graph
from app.tools.registry import execute


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


def _disposable(prefix: str) -> str:
    return f"graphops_t{prefix}{uuid4().hex[:8]}"


def _blob(value: object) -> str:
    return json.dumps(value, default=str)


@pytest.fixture
def gateway() -> GraphGateway:
    return GraphGateway(_settings())


@pytest.fixture
def acme(gateway: GraphGateway) -> tuple[str, GraphHandle]:
    graph_name = _disposable("acme")
    try:
        seed_graph(gateway, graph_name, "acme", reset=True)
        opened = gateway.open_graph(graph_name)
        assert isinstance(opened, GraphHandle)
        yield graph_name, opened
    finally:
        gateway.discard(graph_name)


def test_trace_dependency_keeps_latest_deploy(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    item = execute(gateway, handle, "trace_dependency", {"incidentId": "INC-203"}, "q_01")
    blob = _blob(item.rows)
    assert item.status == "SUCCESS"
    assert "DEP-1042" in blob
    assert "C-8891" in blob
    assert "payments-repo" in blob
    assert "E-17" in blob
    assert "DEP-1038" not in blob


def test_analyze_impact_shortest_path_omits_upstream(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    item = execute(gateway, handle, "analyze_impact", {"service": "payment-service"}, "q_01")
    hops = {
        row["service"]: row["hops"]
        for row in item.rows
        if row.get("kind") == "service" and row.get("service")
    }
    assert hops["checkout-api"] == 1
    assert hops["billing-worker"] == 1
    assert hops["merchant-portal"] == 2
    assert "fraud-service" not in hops


def test_find_domain_experts_ranks_e17_first(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    item = execute(
        gateway,
        handle,
        "find_domain_experts",
        {"service": "payment-service", "incidentId": "INC-203", "deploymentId": "DEP-1042"},
        "q_01",
    )
    assert item.rows
    top = item.rows[0]
    assert top["personId"] == "E-17"
    expected = (
        int(top["incidentCount"]) * 5
        + int(top["commitCount"])
        + int(bool(top["authoredSuspect"])) * 10
        + int(bool(top["resolvedSimilar"])) * 10
    )
    assert top["score"] == expected
    assert top["scoreKind"] == "derived"
    assert top["rank"] == 1


def test_find_previous_incidents_returns_history(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    item = execute(
        gateway,
        handle,
        "find_previous_incidents",
        {"incidentId": "INC-203"},
        "q_01",
    )
    blob = _blob(item.rows)
    assert "INC-118" in blob
    assert "RES-44" in blob


def test_deleting_similar_to_empties_previous_incidents(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    deleted = gateway.run_query(
        handle,
        "MATCH (:Incident {id: $id})-[r:SIMILAR_TO]->() DELETE r RETURN count(r)",
        {"id": "INC-203"},
    )
    assert not isinstance(deleted, ToolFailure)
    item = execute(
        gateway,
        handle,
        "find_previous_incidents",
        {"incidentId": "INC-203"},
        "q_01",
    )
    assert item.rows == []
    assert "RES-44" not in _blob(item.rows)


def test_deleting_contains_omits_commit_from_trace(
    gateway: GraphGateway,
    acme: tuple[str, GraphHandle],
) -> None:
    _name, handle = acme
    deleted = gateway.run_query(
        handle,
        "MATCH (:Deployment {id: $d})-[r:CONTAINS]->(:Commit {id: $c}) DELETE r RETURN count(r)",
        {"d": "DEP-1042", "c": "C-8891"},
    )
    assert not isinstance(deleted, ToolFailure)
    item = execute(gateway, handle, "trace_dependency", {"incidentId": "INC-203"}, "q_01")
    blob = _blob(item.rows)
    assert "C-8891" not in blob
    assert "C-7702" not in blob
