"""Phase 2: tenant selection, result caps, and the synthetic graphs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path as GraphPath

from app.config import Settings
from app.graph.client import GraphGateway, GraphHandle, PolicyBlocked, QueryOutcome, ToolFailure
from app.graph.seed import DOCUMENT_BODY, seed_graph

LATEST_DEPLOY = """
MATCH (i:Incident {id: 'INC-203'})-[:AFFECTS]->(s:Service)
MATCH (d:Deployment)-[:DEPLOYED]->(s)
WHERE d.deployedAt <= i.openedAt
RETURN i.id, s.name, d.id
ORDER BY d.deployedAt DESC
LIMIT 1
"""


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


class _Result:
    def __init__(self, rows: list[list[object]]) -> None:
        self.result_set = rows


class _Graph:
    def query(self, cypher: str, params: dict[str, object], timeout: int) -> object:
        return self.behavior


def test_tenant_name_rejects_anything_outside_the_pattern() -> None:
    gateway = GraphGateway(_settings(falkordb_port=1, query_timeout_ms=200))
    assert gateway.tenant_graph_name("acme") == "graphops_acme"
    assert gateway.tenant_graph_name("globex") == "graphops_globex"
    rejected = ("", "ACME", "acme!", "a" * 33, "acme/globex", "acme globex", "Acme")
    for tenant in rejected:
        assert gateway.tenant_graph_name(tenant) is None
        outcome = gateway.open_tenant(tenant)
        assert isinstance(outcome, PolicyBlocked)


def test_composed_name_with_an_illegal_prefix_is_blocked() -> None:
    gateway = GraphGateway(_settings(graph_prefix="!!!", falkordb_port=1, query_timeout_ms=200))
    assert gateway.tenant_graph_name("acme") is None
    assert isinstance(gateway.open_tenant("acme"), PolicyBlocked)


def test_handle_does_not_expose_the_graph_name() -> None:
    class _Named:
        name = "graphops_secret"
        client = object()

        def query(self, cypher: str, params: dict[str, object], timeout: int | None = None) -> object:
            raise AssertionError("query should not run")

    handle = GraphHandle(_Named())
    assert not hasattr(handle, "name")
    assert not hasattr(handle, "client")
    assert repr(handle) == "GraphHandle()"
    assert "graphops_secret" not in repr(handle)


def test_scalar_rows_slice_at_max_nodes() -> None:
    graph = _Graph()
    graph.behavior = _Result([[1], [2], [3], [4]])
    outcome = GraphGateway(_settings(max_nodes=2)).run_query(graph, "RETURN 1")
    assert isinstance(outcome, QueryOutcome)
    assert outcome.rows == [[1], [2]]
    assert outcome.result_count == 2
    assert outcome.truncated is True


def test_relationship_rows_slice_at_max_rels() -> None:
    left = Node(node_id=1, labels="Service")
    right = Node(node_id=2, labels="Service")
    other = Node(node_id=3, labels="Service")
    end = Node(node_id=4, labels="Service")
    first = Edge(left, "DEPENDS_ON", right, edge_id=10)
    second = Edge(other, "DEPENDS_ON", end, edge_id=11)
    graph = _Graph()
    graph.behavior = _Result([[first], [second]])
    outcome = GraphGateway(_settings(max_nodes=10, max_rels=1)).run_query(graph, "RETURN r")
    assert isinstance(outcome, QueryOutcome)
    assert outcome.truncated is True
    assert outcome.rows == [[first]]
    assert outcome.result_count == 1


def test_a_path_over_the_node_cap_is_dropped() -> None:
    first = Node(node_id=1, labels="Service")
    second = Node(node_id=2, labels="Service")
    third = Node(node_id=3, labels="Service")
    path = GraphPath(
        [first, second, third],
        [Edge(first, "DEPENDS_ON", second, edge_id=1), Edge(second, "DEPENDS_ON", third, edge_id=2)],
    )
    graph = _Graph()
    graph.behavior = _Result([[path]])
    outcome = GraphGateway(_settings(max_nodes=2, max_rels=10)).run_query(graph, "RETURN p")
    assert isinstance(outcome, QueryOutcome)
    assert outcome.rows == []
    assert outcome.truncated is True
    assert outcome.result_count == 0


def test_small_result_is_not_truncated() -> None:
    graph = _Graph()
    graph.behavior = _Result([[1]])
    outcome = GraphGateway(_settings()).run_query(graph, "RETURN 1", {"n": 1})
    assert isinstance(outcome, QueryOutcome)
    assert outcome.truncated is False
    assert outcome.rows == [[1]]


def test_seed_source_does_not_create_a_decision() -> None:
    source = (Path(__file__).resolve().parents[2] / "apps" / "api" / "app" / "graph" / "seed.py").read_text(
        encoding="utf-8"
    )
    assert "CREATE (decision" not in source
    assert "CREATE (d:Decision" not in source
    assert "CREATE (:Decision" not in source


def _disposable(prefix: str) -> str:
    return f"graphops_p2{prefix}{uuid4().hex[:8]}"


def _open(gateway: GraphGateway, graph_name: str) -> GraphHandle:
    opened = gateway.open_graph(graph_name)
    assert isinstance(opened, GraphHandle)
    return opened


def _rows(gateway: GraphGateway, graph: GraphHandle, cypher: str, params: dict[str, object] | None = None) -> list[list[object]]:
    outcome = gateway.run_query(graph, cypher, params)
    assert not isinstance(outcome, ToolFailure)
    assert outcome.truncated is False
    return outcome.rows


@pytest.fixture
def gateway() -> GraphGateway:
    return GraphGateway(_settings())


def test_acme_story_is_idempotent(gateway: GraphGateway, capsys: pytest.CaptureFixture[str]) -> None:
    graph_name = _disposable("acme")
    try:
        first = seed_graph(gateway, graph_name, "acme", reset=True)
        second = seed_graph(gateway, graph_name, "acme")
        assert first.stopped is False
        assert second.stopped is False
        assert first.node_count == second.node_count
        assert first.node_count > 0

        graph = _open(gateway, graph_name)
        latest = _rows(gateway, graph, LATEST_DEPLOY)
        assert latest == [["INC-203", "payment-service", "DEP-1042"]]
        trace = _rows(
            gateway,
            graph,
            """
            MATCH (i:Incident {id: $incidentId})-[:AFFECTS]->(s:Service)-[:DEPENDS_ON]->(dep:Dependency)
            MATCH (d:Deployment)-[:DEPLOYED]->(s)
            WHERE d.deployedAt <= i.openedAt
            WITH dep, d
            ORDER BY d.deployedAt DESC
            LIMIT 1
            RETURN dep.name, d.id
            """,
            {"incidentId": "INC-203"},
        )
        assert trace == [["ledger-db", "DEP-1042"]]
        commit = _rows(
            gateway,
            graph,
            "MATCH (c:Commit {id: 'C-8891'}) RETURN c.sha, c.message",
        )
        assert commit == [["a1b2c3d4", "retry ledger writes with unbounded backoff"]]

        deploys = _rows(
            gateway,
            graph,
            "MATCH (d:Deployment)-[:DEPLOYED]->(:Service {name: 'payment-service'}) RETURN d.id ORDER BY d.id",
        )
        assert [row[0] for row in deploys] == ["DEP-0901", "DEP-1038", "DEP-1042"]

        body = _rows(
            gateway,
            graph,
            "MATCH (d:Document {id: 'DOC-PAY-OWN'}) RETURN d.body, d.title, d.source",
        )
        assert body == [[
            DOCUMENT_BODY,
            "Payment service ownership",
            "runbook/payment-service.md",
        ]]

        decisions = _rows(gateway, graph, "MATCH (d:Decision) RETURN count(d)")
        assert decisions == [[0]]
        caused = _rows(gateway, graph, "MATCH ()-[r:CAUSED]->() RETURN count(r)")
        assert caused == [[0]]

        owners = _rows(
            gateway,
            graph,
            "MATCH (t:Team)-[o:OWNS]->(:Service {name: 'payment-service'}) "
            "RETURN t.name ORDER BY o.since DESC",
        )
        assert [row[0] for row in owners] == ["payments-platform", "legacy-payments"]

        history = _rows(
            gateway,
            graph,
            "MATCH (p:Person)-[w:WORKED_ON]->(:Service {name: 'payment-service'}) "
            "RETURN p.id, w.incidentCount, w.commitCount",
        )
        scores = {row[0]: row[1] * 5 + row[2] for row in history}
        assert set(scores) == {"E-17", "E-22", "E-09"}
        assert scores["E-17"] > scores["E-09"]
        assert scores["E-17"] > scores["E-22"]

        rels_first = _rows(gateway, graph, "MATCH ()-[r]->() RETURN count(r)")[0][0]
        third = seed_graph(gateway, graph_name, "acme")
        rels_second = _rows(gateway, _open(gateway, graph_name), "MATCH ()-[r]->() RETURN count(r)")[0][0]
        assert third.node_count == first.node_count
        assert rels_first == rels_second

        indexes = _rows(
            gateway,
            graph,
            "CALL db.indexes() YIELD label, properties, types, entitytype "
            "RETURN label, properties, types, entitytype",
        )
        keys = set()
        for label, _properties, types, entity in indexes:
            if entity != "NODE" or not isinstance(types, dict):
                continue
            for prop, kinds in types.items():
                for kind in kinds:
                    keys.add((label, prop, kind))
        for label, prop in (
            ("Incident", "id"),
            ("Service", "name"),
            ("Person", "id"),
            ("Deployment", "id"),
            ("Decision", "id"),
            ("Document", "id"),
        ):
            assert (label, prop, "RANGE") in keys
        for prop in ("name", "title", "id"):
            assert ("EntityText", prop, "FULLTEXT") in keys

        hits = _rows(
            gateway,
            graph,
            "CALL db.idx.fulltext.queryNodes('EntityText', $q) YIELD node "
            "RETURN node.name",
            {"q": "payment service"},
        )
        assert ["payment-service"] in hits

        captured = capsys.readouterr().out
        assert DOCUMENT_BODY not in captured
        assert "seed stopped" not in captured
    finally:
        gateway.discard(graph_name)


def test_globex_does_not_return_the_acme_incident(gateway: GraphGateway) -> None:
    graph_name = _disposable("globex")
    try:
        result = seed_graph(gateway, graph_name, "globex", reset=True)
        assert result.stopped is False
        graph = _open(gateway, graph_name)
        assert _rows(gateway, graph, LATEST_DEPLOY) == []
        absent = _rows(
            gateway,
            graph,
            "MATCH (n) WHERE n.id IN ['INC-203', 'DEC-203-1'] OR n.name = 'payment-service' RETURN count(n)",
        )
        assert absent == [[0]]
        billing = _rows(
            gateway,
            graph,
            "MATCH (t:Team)-[:OWNS]->(s:Service) RETURN t.name, s.name, s.tier",
        )
        assert billing == [["globex-platform", "globex-billing", 2]]
        assert _rows(gateway, graph, "MATCH (d:Decision) RETURN count(d)") == [[0]]
    finally:
        gateway.discard(graph_name)


def test_seed_stops_when_a_decision_exists(
    gateway: GraphGateway,
    capsys: pytest.CaptureFixture[str],
) -> None:
    graph_name = _disposable("stop")
    try:
        first = seed_graph(gateway, graph_name, "acme", reset=True)
        graph = _open(gateway, graph_name)
        created = gateway.run_query(
            graph,
            "CREATE (:Decision {id: 'DEC-203-1', action: 'rollback'})",
        )
        assert not isinstance(created, ToolFailure)
        before = _rows(gateway, graph, "MATCH (n) RETURN count(n)")[0][0]

        stopped = seed_graph(gateway, graph_name, "acme")
        after = _rows(gateway, _open(gateway, graph_name), "MATCH (n) RETURN count(n)")[0][0]
        services = _rows(
            gateway,
            _open(gateway, graph_name),
            "MATCH (s:Service {name: 'payment-service'}) RETURN count(s)",
        )
        assert stopped.stopped is True
        assert stopped.node_count == before == after
        assert services == [[1]]
        assert first.node_count + 1 == before
        captured = capsys.readouterr().out
        assert f"{graph_name} already contains a Decision; seed stopped." in captured
        assert DOCUMENT_BODY not in captured
    finally:
        gateway.discard(graph_name)


def test_reset_clears_a_decision_and_reseeds(gateway: GraphGateway) -> None:
    graph_name = _disposable("reset")
    try:
        first = seed_graph(gateway, graph_name, "acme", reset=True)
        graph = _open(gateway, graph_name)
        gateway.run_query(graph, "CREATE (:Decision {id: 'DEC-203-1'})")
        again = seed_graph(gateway, graph_name, "acme", reset=True)
        graph = _open(gateway, graph_name)
        assert again.stopped is False
        assert again.node_count == first.node_count
        assert _rows(gateway, graph, "MATCH (d:Decision) RETURN count(d)") == [[0]]
        assert _rows(gateway, graph, LATEST_DEPLOY) == [["INC-203", "payment-service", "DEP-1042"]]
    finally:
        gateway.discard(graph_name)
