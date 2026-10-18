"""Choose the next read tool from evidence already returned. Ids come from rows."""

from __future__ import annotations

from typing import Any

from app.domain.models import EvidenceItem


def question_kind(question: str) -> str:
    text = question.lower()
    if "what did we decide" in text or "last time" in text:
        return "memory"
    if "what breaks" in text or "ownership" in text or "which document" in text:
        return "impact"
    return "change"


class ScriptedPlanner:
    """Offline planner for LLM_MODEL=local. It does not invent node keys."""

    def plan(
        self,
        question: str,
        evidence: list[EvidenceItem],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        allowed = {item["tool"] for item in catalog}
        kind = question_kind(question)
        ran = {item.tool for item in evidence if item.status != "POLICY BLOCKED"}
        service = _service(question, evidence)
        incident = _incident(evidence)
        deployment = _field(evidence, "deploymentId")

        call = _next(kind, ran, service, incident, deployment, question)
        if call is None or call["tool"] not in allowed:
            return {"stop": True, "calls": []}
        return {"stop": False, "calls": [call]}


def _next(
    kind: str,
    ran: set[str],
    service: str | None,
    incident: str | None,
    deployment: str | None,
    question: str,
) -> dict[str, Any] | None:
    if "search_entity" not in ran:
        return {"tool": "search_entity", "arguments": {"query": _search_text(question)}}
    if kind == "memory":
        if "find_decision_path" not in ran and incident and service:
            return {
                "tool": "find_decision_path",
                "arguments": {"incidentId": incident, "service": service},
            }
        return None
    if kind == "impact":
        if "analyze_impact" not in ran and service:
            return {"tool": "analyze_impact", "arguments": {"service": service}}
        if "find_decision_path" not in ran and incident and service:
            return {
                "tool": "find_decision_path",
                "arguments": {"incidentId": incident, "service": service},
            }
        return None
    if "trace_dependency" not in ran and incident:
        return {"tool": "trace_dependency", "arguments": {"incidentId": incident}}
    if "analyze_impact" not in ran and service:
        return {"tool": "analyze_impact", "arguments": {"service": service}}
    if "find_previous_incidents" not in ran and incident:
        return {"tool": "find_previous_incidents", "arguments": {"incidentId": incident}}
    if "find_domain_experts" not in ran and service and incident and deployment:
        return {
            "tool": "find_domain_experts",
            "arguments": {
                "service": service,
                "incidentId": incident,
                "deploymentId": deployment,
            },
        }
    if "find_decision_path" not in ran and incident and service:
        arguments: dict[str, str] = {"incidentId": incident, "service": service}
        if deployment:
            arguments["deploymentId"] = deployment
        return {"tool": "find_decision_path", "arguments": arguments}
    return None


def _search_text(question: str) -> str:
    text = question.lower()
    if "payment service" in text or "payment" in text:
        return "payment service"
    compact = " ".join(question.split())
    return compact[:200] if compact else "unknown"


def _service(question: str, evidence: list[EvidenceItem]) -> str | None:
    names: list[str] = []
    for item in evidence:
        if item.tool != "search_entity":
            continue
        for row in item.rows:
            labels = row.get("labels") or []
            name = row.get("name")
            if isinstance(labels, list) and "Service" in labels and isinstance(name, str):
                names.append(name)
    if not names:
        return None
    normalized = question.lower().replace(" ", "-")
    spoken = question.lower()
    for name in names:
        if name in normalized or name.replace("-", " ") in spoken:
            return name
    return names[0]


def _incident(evidence: list[EvidenceItem]) -> str | None:
    open_ids: list[str] = []
    any_ids: list[str] = []
    for item in evidence:
        if item.tool != "search_entity":
            continue
        for row in item.rows:
            labels = row.get("labels") or []
            incident_id = row.get("id")
            if not isinstance(labels, list) or "Incident" not in labels or not isinstance(incident_id, str):
                continue
            any_ids.append(incident_id)
            if row.get("status") == "open":
                open_ids.append(incident_id)
    if open_ids:
        return open_ids[0]
    return any_ids[0] if any_ids else None


def _field(evidence: list[EvidenceItem], key: str) -> str | None:
    for item in evidence:
        if item.status in {"TOOL FAILURE", "POLICY BLOCKED"}:
            continue
        for row in item.rows:
            value = row.get(key)
            if isinstance(value, str) and value:
                return value
    return None
