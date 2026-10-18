"""Name to template to handler. The write tool is not registered here."""

from __future__ import annotations

from typing import Any

from app.domain.models import EvidenceItem
from app.graph.client import GraphGateway, GraphHandle
from app.policy.gate import catalog, reject_reason
from app.tools.queries import run_tool


def read_catalog() -> list[dict[str, Any]]:
    return catalog()


def execute(
    gateway: GraphGateway,
    handle: GraphHandle,
    tool: str,
    arguments: object,
    query_id: str,
) -> EvidenceItem:
    """Run a read tool, or return an empty blocked item. No query on rejection."""

    reason = reject_reason(tool, arguments)
    if reason is not None:
        return EvidenceItem(
            query_id=query_id,
            tool=tool,
            kind="graph_fact",
            status="POLICY BLOCKED",
            rows=[],
            duration_ms=0,
            result_count=0,
            error_category="policy",
        )
    assert isinstance(arguments, dict)
    return run_tool(gateway, handle, tool, arguments, query_id)
