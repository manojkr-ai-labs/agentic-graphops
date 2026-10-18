"""FalkorDB access. Timeouts become a typed tool failure, not result rows."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path

from app.config import Settings

_TIMEOUT_MARKERS = ("timed out", "timeout")
# Tenant ids are the only caller-supplied part of a graph name.
_TENANT = re.compile(r"^[a-z0-9-]{1,32}$")
# Composed names stay inside what GRAPH.QUERY will accept as a key.
_GRAPH_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class ToolFailure:
    """A query that did not return rows. Carries a category, never a message."""

    error_category: str
    duration_ms: int

    def __post_init__(self) -> None:
        if self.error_category not in {"timeout", "connection", "query"}:
            raise ValueError("unknown error category")


@dataclass(frozen=True)
class PolicyBlocked:
    """The graph name was rejected before a connection was used."""

    duration_ms: int


@dataclass(frozen=True)
class QueryOutcome:
    rows: list[list[Any]]
    result_count: int
    duration_ms: int
    truncated: bool = False
    headers: tuple[str, ...] = ()


class GraphHandle:
    """An already-selected graph. The name and the connection stay on the gateway."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def query(
        self,
        cypher: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> Any:
        bound = params or {}
        if timeout is None:
            return self._graph.query(cypher, bound)
        return self._graph.query(cypher, bound, timeout=timeout)

    def __repr__(self) -> str:
        return "GraphHandle()"


class GraphGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._db: Any = None

    def tenant_graph_name(self, tenant: str) -> str | None:
        """`{GRAPH_PREFIX}{tenant}` when the tenant matches `^[a-z0-9-]{1,32}$`."""

        if not isinstance(tenant, str) or _TENANT.fullmatch(tenant) is None:
            return None
        name = f"{self._settings.graph_prefix}{tenant}"
        if _GRAPH_NAME.fullmatch(name) is None:
            return None
        return name

    def open_tenant(self, tenant: str) -> GraphHandle | PolicyBlocked | ToolFailure:
        """Select the tenant graph. Anything else is policy blocked, before a query."""

        started = time.perf_counter()
        name = self.tenant_graph_name(tenant)
        if name is None:
            return PolicyBlocked(_elapsed_ms(started))
        return self.open_graph(name)

    def open_graph(self, graph_name: str) -> GraphHandle | PolicyBlocked | ToolFailure:
        """Select a graph the caller already named. Tools use `open_tenant` instead."""

        started = time.perf_counter()
        if not isinstance(graph_name, str) or _GRAPH_NAME.fullmatch(graph_name) is None:
            return PolicyBlocked(_elapsed_ms(started))
        try:
            graph = self.select_graph(graph_name)
        except Exception as exc:
            return ToolFailure(_error_category(exc), _elapsed_ms(started))
        return GraphHandle(graph)

    def discard(self, graph_name: str) -> PolicyBlocked | ToolFailure | None:
        """Delete a graph. A missing graph is not an error. Tests use this to reset."""

        started = time.perf_counter()
        if not isinstance(graph_name, str) or _GRAPH_NAME.fullmatch(graph_name) is None:
            return PolicyBlocked(_elapsed_ms(started))
        try:
            if self._db is None:
                self.connect()
            self._db.select_graph(graph_name).delete()
        except Exception as exc:
            text = str(exc).lower()
            if "empty key" in text or "invalid graph" in text:
                return None
            return ToolFailure(_error_category(exc), _elapsed_ms(started))
        return None

    def connect(self) -> None:
        from falkordb import FalkorDB

        password = self._settings.falkordb_password.get_secret_value()
        timeout_s = self._settings.query_timeout_ms / 1000
        self._db = FalkorDB(
            host=self._settings.falkordb_host,
            port=self._settings.falkordb_port,
            password=password or None,
            socket_connect_timeout=min(timeout_s, 2.0),
            socket_timeout=timeout_s + 1.0,
        )

    def select_graph(self, name: str) -> Any:
        if self._db is None:
            self.connect()
        return self._db.select_graph(name)

    def run_query(
        self,
        graph: Any,
        cypher: str,
        params: dict[str, Any] | None = None,
    ) -> QueryOutcome | ToolFailure:
        """Run a parameterized query. User text stays in `params`, not in the string."""

        started = time.perf_counter()
        if not isinstance(cypher, str) or not cypher.strip():
            return ToolFailure("query", _elapsed_ms(started))
        if params is None:
            bound: dict[str, Any] = {}
        elif isinstance(params, dict):
            bound = params
        else:
            return ToolFailure("query", _elapsed_ms(started))

        try:
            result = graph.query(
                cypher,
                bound,
                timeout=self._settings.query_timeout_ms,
            )
        except Exception as exc:
            return ToolFailure(_error_category(exc), _elapsed_ms(started))

        rows = getattr(result, "result_set", None) or []
        copied = [list(row) for row in rows]
        kept, truncated = _slice_rows(
            copied,
            self._settings.max_nodes,
            self._settings.max_rels,
        )
        return QueryOutcome(
            rows=kept,
            result_count=len(kept),
            duration_ms=_elapsed_ms(started),
            truncated=truncated,
            headers=_header_names(getattr(result, "header", None)),
        )

    def ping(self) -> QueryOutcome | ToolFailure:
        """GRAPH.QUERY against the configured prefix. A down server is a failure."""

        started = time.perf_counter()
        try:
            graph = self.select_graph(f"{self._settings.graph_prefix}health")
        except Exception as exc:
            return ToolFailure(_error_category(exc), _elapsed_ms(started))
        return self.run_query(graph, "RETURN 1")


def _slice_rows(
    rows: list[list[Any]],
    max_nodes: int,
    max_rels: int,
) -> tuple[list[list[Any]], bool]:
    """Keep a prefix of rows that fits both caps. A sliced result is truncated.

    A row of only scalars occupies one node slot, so a large id list is capped
    the same way a large node list is. Depth limits are not applied here:
    later templates write them as integer literals, not parameters.
    """

    kept: list[list[Any]] = []
    nodes = 0
    rels = 0
    for row in rows:
        row_nodes, row_rels = _count_entities(row)
        if row_nodes == 0 and row_rels == 0:
            row_nodes = 1
        if nodes + row_nodes > max_nodes or rels + row_rels > max_rels:
            return kept, True
        kept.append(row)
        nodes += row_nodes
        rels += row_rels
    return kept, False


def _count_entities(value: object) -> tuple[int, int]:
    if isinstance(value, Node):
        return 1, 0
    if isinstance(value, Edge):
        nodes = 0
        for end in (value.src_node, value.dest_node):
            if isinstance(end, Node):
                nodes += 1
        return nodes, 1
    if isinstance(value, Path):
        return len(value.nodes()), len(value.edges())
    if isinstance(value, dict):
        nodes = 0
        rels = 0
        for item in value.values():
            item_nodes, item_rels = _count_entities(item)
            nodes += item_nodes
            rels += item_rels
        return nodes, rels
    if isinstance(value, (list, tuple)):
        nodes = 0
        rels = 0
        for item in value:
            item_nodes, item_rels = _count_entities(item)
            nodes += item_nodes
            rels += item_rels
        return nodes, rels
    return 0, 0


def _header_names(header: object) -> tuple[str, ...]:
    if not isinstance(header, (list, tuple)):
        return ()
    names: list[str] = []
    for column in header:
        if isinstance(column, (list, tuple)) and column:
            names.append(str(column[0]))
        elif isinstance(column, str):
            names.append(column)
    return tuple(names)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _error_category(exc: BaseException) -> str:
    """Query timeouts stay `timeout`. A server that cannot be reached is `connection`."""

    text = str(exc).lower()
    if "query timed out" in text:
        return "timeout"
    if isinstance(exc, OSError) or "Connection" in type(exc).__name__:
        return "connection"
    if type(exc).__name__ == "TimeoutError" or text.startswith("network:"):
        return "connection"
    if "connection" in text or "refused" in text:
        return "connection"
    if any(marker in text for marker in _TIMEOUT_MARKERS):
        return "timeout"
    return "query"
