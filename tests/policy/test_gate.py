"""Policy gate: blocked calls never query, and globex cannot see acme rows."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.config import Settings
from app.graph.client import GraphGateway, GraphHandle, QueryOutcome, ToolFailure
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
    return f"graphops_p{prefix}{uuid4().hex[:8]}"


class SpyGateway(GraphGateway):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.queries: list[str] = []

    def run_query(self, graph: object, cypher: str, params: dict[str, object] | None = None) -> QueryOutcome | ToolFailure:
        self.queries.append(cypher)
        return super().run_query(graph, cypher, params)


@pytest.fixture
def gateway() -> SpyGateway:
    return SpyGateway(_settings())


def test_unknown_tool_is_blocked_without_query(gateway: SpyGateway) -> None:
    handle = GraphHandle(object())
    item = execute(gateway, handle, "record_agent_memory", {"incidentId": "INC-203"}, "q_01")
    assert item.status == "POLICY BLOCKED"
    assert item.rows == []
    assert gateway.queries == []


def test_cypher_argument_is_blocked_without_query(gateway: SpyGateway) -> None:
    handle = GraphHandle(object())
    item = execute(
        gateway,
        handle,
        "trace_dependency",
        {"incidentId": "INC-203", "cypher": "MATCH (n) RETURN n"},
        "q_01",
    )
    assert item.status == "POLICY BLOCKED"
    assert item.rows == []
    assert gateway.queries == []


def test_tenant_argument_is_blocked_without_query(gateway: SpyGateway) -> None:
    handle = GraphHandle(object())
    item = execute(
        gateway,
        handle,
        "trace_dependency",
        {"incidentId": "INC-203", "tenant": "globex"},
        "q_01",
    )
    assert item.status == "POLICY BLOCKED"
    assert item.rows == []
    assert gateway.queries == []


def test_globex_does_not_return_inc_203(gateway: SpyGateway) -> None:
    graph_name = _disposable("globex")
    try:
        seed_graph(gateway, graph_name, "globex", reset=True)
        opened = gateway.open_graph(graph_name)
        assert isinstance(opened, GraphHandle)
        gateway.queries.clear()
        traced = execute(gateway, opened, "trace_dependency", {"incidentId": "INC-203"}, "q_01")
        searched = execute(gateway, opened, "search_entity", {"query": "INC-203"}, "q_02")
        blob = json.dumps([traced.rows, searched.rows], default=str)
        assert "INC-203" not in blob
        assert traced.rows == [] or traced.status == "NO EVIDENCE"
    finally:
        gateway.discard(graph_name)
