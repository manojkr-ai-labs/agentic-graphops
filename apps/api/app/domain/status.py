"""Map tool results onto the six user-visible statuses."""

from __future__ import annotations

from app.domain.models import EvidenceItem, Recommendation

VISIBLE = (
    "SUCCESS",
    "NO EVIDENCE",
    "PARTIAL RESULT",
    "TOOL FAILURE",
    "POLICY BLOCKED",
    "SYSTEM ERROR",
)

_REQUIRED = {
    "change": (
        "search_entity",
        "trace_dependency",
        "analyze_impact",
        "find_previous_incidents",
        "find_domain_experts",
        "find_decision_path",
    ),
    "memory": ("search_entity", "find_decision_path"),
    "impact": ("search_entity", "analyze_impact", "find_decision_path"),
}


def investigation_status(
    kind: str,
    evidence: list[EvidenceItem],
    recommendation: Recommendation | None,
    *,
    capped: bool,
    llm_failed: bool,
    validation_failed: bool,
) -> str:
    """One of the six names in section 22. Internal states stay off this value."""

    if llm_failed or validation_failed:
        return "SYSTEM ERROR"
    if evidence and all(item.status == "TOOL FAILURE" for item in evidence):
        return "TOOL FAILURE"
    if any(item.status == "TOOL FAILURE" for item in evidence):
        return "PARTIAL RESULT"
    if capped:
        return "PARTIAL RESULT"
    if not evidence or not any(item.rows or item.path for item in evidence):
        if any(item.status == "POLICY BLOCKED" for item in evidence):
            return "POLICY BLOCKED"
        return "NO EVIDENCE"
    if kind == "memory" and not _decision_rows(evidence):
        return "NO EVIDENCE"
    if _missing_required(kind, evidence) or any(item.truncated for item in evidence):
        return "PARTIAL RESULT"
    if recommendation is None:
        return "PARTIAL RESULT"
    return "SUCCESS"


def _missing_required(kind: str, evidence: list[EvidenceItem]) -> bool:
    by_tool = {item.tool: item for item in evidence}
    for name in _REQUIRED.get(kind, ()):
        item = by_tool.get(name)
        if item is None or item.status in {"TOOL FAILURE", "POLICY BLOCKED"}:
            return True
        if name == "find_previous_incidents" and not item.rows:
            return True
        if name == "trace_dependency" and not item.rows:
            return True
        if name == "analyze_impact" and not item.rows:
            return True
        if name == "find_domain_experts" and not item.rows:
            return True
        if name == "find_decision_path" and not item.path and not item.rows:
            return True
    return False


def _decision_rows(evidence: list[EvidenceItem]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for item in evidence:
        for row in item.rows:
            if row.get("rowType") == "decision" and row.get("decisionId"):
                found.append(row)
    return found
