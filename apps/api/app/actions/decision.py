"""One transaction after approval. createdAt is the API clock."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.domain.models import EvidenceItem
from app.graph.client import GraphGateway, GraphHandle, QueryOutcome, ToolFailure

_EXISTS = """
MATCH (d:Decision {id: $decisionId})
RETURN d.id AS decisionId, d.summary AS summary, d.rollbackCandidate AS rollbackCandidate,
       d.approvedBy AS approvedBy, d.episodeId AS episodeId, d.action AS action
"""

_WRITE = """
MATCH (i:Incident {id: $incidentId})
MATCH (p:Person {id: $personId})
CREATE (decision:Decision {
  id: $decisionId,
  summary: $summary,
  rollbackCandidate: $rollbackCandidate,
  createdAt: localdatetime($createdAt),
  approvedBy: $approvedBy,
  episodeId: $episodeId,
  action: $action
})
CREATE (i)-[:DECIDED]->(decision)
CREATE (decision)-[:ASSIGNED_TO]->(p)
RETURN decision.id AS decisionId
"""

_PROOF = """
MATCH (i:Incident {id: $incidentId})-[:DECIDED]->(d:Decision)-[:ASSIGNED_TO]->(p:Person)
WHERE d.id = $decisionId
RETURN d.id AS decisionId, d.summary AS summary, d.rollbackCandidate AS rollbackCandidate,
       d.approvedBy AS approvedBy, d.episodeId AS episodeId, d.action AS action,
       p.id AS personId, p.name AS personName
"""


@dataclass
class WriteResult:
    status: str
    notice: str | None
    decision: dict[str, Any] | None
    duration_ms: int
    already_existed: bool = False
    error_category: str | None = None


def record_decision(
    gateway: GraphGateway,
    handle: GraphHandle,
    proposal: dict[str, str],
    evidence: list[EvidenceItem],
) -> WriteResult:
    rollback = proposal["rollbackCandidate"]
    person_id = proposal["assigneeId"]
    if not _seen(evidence, rollback) or not _seen(evidence, person_id):
        return WriteResult("POLICY BLOCKED", None, None, 0, error_category="policy")

    existing = gateway.run_query(handle, _EXISTS, {"decisionId": proposal["decisionId"]})
    if isinstance(existing, ToolFailure):
        return WriteResult("TOOL FAILURE", None, None, existing.duration_ms, error_category=existing.error_category)
    if existing.rows:
        decision = _decision_from_row(existing)
        return WriteResult(
            "SUCCESS",
            f"{proposal['decisionId']} already exists. The write already happened.",
            decision,
            existing.duration_ms,
            already_existed=True,
        )

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    written = gateway.run_query(
        handle,
        _WRITE,
        {
            "incidentId": proposal["incidentId"],
            "personId": person_id,
            "decisionId": proposal["decisionId"],
            "summary": proposal["summary"],
            "rollbackCandidate": rollback,
            "createdAt": created_at,
            "approvedBy": proposal["approvedBy"],
            "episodeId": proposal["episodeId"],
            "action": proposal["action"],
        },
    )
    if isinstance(written, ToolFailure):
        return WriteResult("TOOL FAILURE", None, None, written.duration_ms, error_category=written.error_category)
    if not written.rows:
        return WriteResult("NO EVIDENCE", None, None, existing.duration_ms + written.duration_ms)

    proof = gateway.run_query(
        handle,
        _PROOF,
        {"incidentId": proposal["incidentId"], "decisionId": proposal["decisionId"]},
    )
    if isinstance(proof, ToolFailure):
        return WriteResult("TOOL FAILURE", None, None, proof.duration_ms, error_category=proof.error_category)
    decision = _proof_row(proof) or {
        "decisionId": proposal["decisionId"],
        "summary": proposal["summary"],
        "rollbackCandidate": rollback,
        "approvedBy": proposal["approvedBy"],
        "episodeId": proposal["episodeId"],
        "action": proposal["action"],
        "personId": person_id,
        "personName": proposal.get("assigneeName"),
    }
    notice = (
        f"SIMULATED notification to #{proposal.get('team') or 'payments-platform'}:\n"
        f"{proposal['decisionId']} recommends rollback of {rollback}.\n"
        f"Assignee: {proposal.get('assigneeName') or person_id} ({person_id}).\n"
        "This notification was not delivered to an external system."
    )
    duration = existing.duration_ms + written.duration_ms + proof.duration_ms
    return WriteResult("SUCCESS", notice, decision, duration)


def _seen(evidence: list[EvidenceItem], needle: str) -> bool:
    for item in evidence:
        if item.status in {"TOOL FAILURE", "POLICY BLOCKED"}:
            continue
        for row in item.rows:
            for value in row.values():
                if value == needle:
                    return True
        for hop in item.path:
            if hop.get("fromKey") == needle or hop.get("toKey") == needle:
                return True
    return False


def _decision_from_row(outcome: QueryOutcome) -> dict[str, Any]:
    row = outcome.rows[0]
    keys = (
        "decisionId",
        "summary",
        "rollbackCandidate",
        "approvedBy",
        "episodeId",
        "action",
    )
    return {key: row[index] if index < len(row) else None for index, key in enumerate(keys)}


def _proof_row(outcome: QueryOutcome) -> dict[str, Any] | None:
    if not outcome.rows:
        return None
    row = outcome.rows[0]
    keys = (
        "decisionId",
        "summary",
        "rollbackCandidate",
        "approvedBy",
        "episodeId",
        "action",
        "personId",
        "personName",
    )
    return {key: _text(row[index]) if index < len(row) else None for index, key in enumerate(keys)}


def _text(value: Any) -> Any:
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()
    return value
