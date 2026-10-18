"""Citation checks. This module does not query the graph."""

from __future__ import annotations

from app.domain.models import EvidenceItem, Recommendation

_FAILED = {"TOOL FAILURE", "POLICY BLOCKED"}


def citation_errors(recommendation: Recommendation, evidence: list[EvidenceItem]) -> list[str]:
    errors: list[str] = []
    rollbacks = _trace_deployments(evidence)
    assignees = _allowed_people(evidence)
    if recommendation.rollback_candidate and recommendation.rollback_candidate not in rollbacks:
        errors.append("rollbackCandidate is not the deployment returned by trace_dependency")
    if recommendation.assignee_id and recommendation.assignee_id not in assignees:
        errors.append("assigneeId is not the top expert or trace author in the evidence log")
    usable = {item.query_id for item in evidence if item.status not in _FAILED}
    for query_id in recommendation.based_on_query_ids:
        if query_id not in usable:
            errors.append(f"{query_id} is missing or failed")
    return errors


def _trace_deployments(evidence: list[EvidenceItem]) -> set[str]:
    found: set[str] = set()
    for item in evidence:
        if item.tool != "trace_dependency" or item.status in _FAILED:
            continue
        for row in item.rows:
            deployment = row.get("deploymentId")
            if isinstance(deployment, str) and deployment:
                found.add(deployment)
    if found:
        return found
    for item in evidence:
        if item.status in _FAILED:
            continue
        for row in item.rows:
            deployment = row.get("deploymentId")
            if isinstance(deployment, str) and deployment:
                found.add(deployment)
        for hop in item.path:
            if hop.get("gap"):
                continue
            if hop.get("fromLabel") == "Deployment" and isinstance(hop.get("fromKey"), str):
                found.add(hop["fromKey"])
            if hop.get("toLabel") == "Deployment" and isinstance(hop.get("toKey"), str):
                found.add(hop["toKey"])
    return found


def _allowed_people(evidence: list[EvidenceItem]) -> set[str]:
    experts: list[dict[str, object]] = []
    for item in evidence:
        if item.tool == "find_domain_experts" and item.status not in _FAILED:
            experts.extend(item.rows)
    if experts:
        ordered = sorted(
            experts,
            key=lambda row: (-_score(row.get("score")), str(row.get("personId") or "")),
        )
        person_id = ordered[0].get("personId")
        return {str(person_id)} if isinstance(person_id, str) else set()
    found: set[str] = set()
    for item in evidence:
        if item.status in _FAILED:
            continue
        for row in item.rows:
            for key in ("authorId", "personId"):
                value = row.get(key)
                if isinstance(value, str) and value:
                    found.add(value)
    return found


def _score(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
