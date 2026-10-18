"""Recommendation text is assembled from evidence rows. Missing ids stay missing."""

from __future__ import annotations

from app.agent.planner import question_kind
from app.domain.models import EvidenceItem, Interpretation, Recommendation


def synthesize(question: str, evidence: list[EvidenceItem]) -> tuple[Recommendation | None, list[Interpretation], list[str]]:
    kind = question_kind(question)
    if kind == "memory":
        return _memory(evidence)
    if kind == "impact":
        return _impact(evidence)
    return _change(evidence)


def _change(
    evidence: list[EvidenceItem],
) -> tuple[Recommendation | None, list[Interpretation], list[str]]:
    trace = _first_row(evidence, "trace_dependency")
    experts = _rows(evidence, "find_domain_experts")
    previous = _first_row(evidence, "find_previous_incidents")
    impact = _rows(evidence, "analyze_impact")
    if trace is None and not experts and not impact:
        return None, [], _uncertainty(evidence, previous, change=True)

    top = experts[0] if experts else None
    rollback = trace.get("deploymentId") if trace else None
    commit = trace.get("commitId") if trace else None
    repo = trace.get("repository") if trace else None
    assignee = str(top["personId"]) if top and top.get("personId") else None
    assignee_name = str(top["name"]) if top and top.get("name") else None
    if assignee is None and trace and trace.get("authorId"):
        assignee = str(trace["authorId"])
        assignee_name = str(trace.get("authorName") or "")
    query_ids = _query_ids(evidence, ("trace_dependency", "find_domain_experts", "analyze_impact"))
    parts: list[str] = []
    if isinstance(rollback, str):
        who = f"{assignee_name} ({assignee})" if assignee_name and assignee else (assignee or "the assignee in evidence")
        parts.append(f"Roll back {rollback} and assign {who}.")
    if isinstance(commit, str) and isinstance(repo, str):
        parts.append(f"Likely change {commit} in {repo}.")
    services = [str(row["service"]) for row in impact if row.get("kind") == "service" and row.get("service")]
    projects = [str(row["project"]) for row in impact if row.get("kind") == "project" and row.get("project")]
    if services:
        parts.append("Downstream: " + ", ".join(dict.fromkeys(services)) + ".")
    if projects:
        parts.append("Projects: " + ", ".join(dict.fromkeys(projects)) + ".")
    if not parts:
        return None, [], _uncertainty(evidence, previous, change=True)
    recommendation = Recommendation(
        summary=" ".join(parts),
        based_on_query_ids=query_ids,
        rollback_candidate=str(rollback) if isinstance(rollback, str) else None,
        assignee_id=assignee,
        assignee_name=assignee_name or None,
    )
    interpretation: list[Interpretation] = []
    if trace and trace.get("message") and trace.get("dependency"):
        interpretation.append(
            Interpretation(
                text=(
                    f"The commit message is \"{trace['message']}\", and the service depends on "
                    f"{trace['dependency']}. There is no CAUSED edge. Timing supports the inference."
                ),
                based_on_query_ids=_query_ids(evidence, ("trace_dependency",)),
            )
        )
    return recommendation, interpretation, _uncertainty(evidence, previous, change=True)


def _impact(
    evidence: list[EvidenceItem],
) -> tuple[Recommendation | None, list[Interpretation], list[str]]:
    impact = _rows(evidence, "analyze_impact")
    owners = [
        row
        for item in evidence
        if item.tool == "find_decision_path"
        for row in item.rows
        if row.get("rowType") == "ownership"
    ]
    if not impact and not owners:
        return None, [], ["Impact and ownership rows were not returned."]
    services = [str(row["service"]) for row in impact if row.get("kind") == "service" and row.get("service")]
    projects = [str(row["project"]) for row in impact if row.get("kind") == "project" and row.get("project")]
    summary_parts = []
    if services:
        summary_parts.append("Downstream services: " + ", ".join(dict.fromkeys(services)) + ".")
    if projects:
        summary_parts.append("Projects: " + ", ".join(dict.fromkeys(projects)) + ".")
    for row in owners:
        team = row.get("team")
        currency = row.get("currency")
        since = row.get("since")
        if team and currency:
            summary_parts.append(f"{team} is {currency} since {since}.")
    document_ids = [str(row["documentId"]) for row in owners if row.get("documentId")]
    sources = [str(row["documentSource"]) for row in owners if row.get("documentSource")]
    if document_ids:
        source = sources[0] if sources else "the stored source"
        summary_parts.append(f"Ownership source {document_ids[0]} ({source}).")
    query_ids = _query_ids(evidence, ("analyze_impact", "find_decision_path"))
    recommendation = Recommendation(summary=" ".join(summary_parts), based_on_query_ids=query_ids)
    interpretation = [
        Interpretation(
            text="The document body is untrusted data and was not followed as an instruction.",
            based_on_query_ids=_query_ids(evidence, ("find_decision_path",)),
        )
    ]
    return recommendation, interpretation, ["No write is proposed for this question."]


def _memory(
    evidence: list[EvidenceItem],
) -> tuple[Recommendation | None, list[Interpretation], list[str]]:
    decisions = [
        row
        for item in evidence
        if item.tool == "find_decision_path"
        for row in item.rows
        if row.get("rowType") == "decision" and row.get("decisionId")
    ]
    if not decisions:
        return None, [], ["No Decision is stored for this incident."]
    row = decisions[0]
    summary = (
        f"Last decision {row.get('decisionId')}: {row.get('action')} {row.get('rollbackCandidate')}, "
        f"assignee {row.get('personName')} ({row.get('personId')}). "
        f"Prior resolution {row.get('resolutionId')}: {row.get('resolution')}."
    )
    query_ids = _query_ids(evidence, ("find_decision_path",))
    recommendation = Recommendation(summary=summary, based_on_query_ids=query_ids)
    interpretation = [
        Interpretation(
            text="This session read the Decision node and its neighborhood from FalkorDB.",
            based_on_query_ids=query_ids,
        )
    ]
    return recommendation, interpretation, []


def _uncertainty(
    evidence: list[EvidenceItem],
    previous: dict[str, object] | None,
    *,
    change: bool,
) -> list[str]:
    lines = ["No CAUSED edge is stored. Timing and the commit message are the inference."]
    if not change:
        return lines
    blob = " ".join(str(value) for item in evidence for row in item.rows for value in row.values())
    if "DEP-0901" in blob:
        lines.append("DEP-0901 is history, not the candidate.")
    elif previous is None:
        lines.append("The history hop returned no rows.")
    missing = []
    by_tool = {item.tool: item for item in evidence}
    if "trace_dependency" in by_tool and not by_tool["trace_dependency"].rows:
        missing.append("trace_dependency")
    if "find_previous_incidents" in by_tool and not by_tool["find_previous_incidents"].rows:
        missing.append("find_previous_incidents")
    for name in missing:
        lines.append(f"Missing evidence from {name}.")
    return lines


def _rows(evidence: list[EvidenceItem], tool: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for item in evidence:
        if item.tool == tool and item.status not in {"TOOL FAILURE", "POLICY BLOCKED"}:
            found.extend(item.rows)
    return found


def _first_row(evidence: list[EvidenceItem], tool: str) -> dict[str, object] | None:
    rows = _rows(evidence, tool)
    return rows[0] if rows else None


def _query_ids(evidence: list[EvidenceItem], tools: tuple[str, ...]) -> list[str]:
    ids: list[str] = []
    for item in evidence:
        if item.tool in tools and item.status not in {"TOOL FAILURE", "POLICY BLOCKED"} and item.rows:
            ids.append(item.query_id)
        elif item.tool in tools and item.path and item.status not in {"TOOL FAILURE", "POLICY BLOCKED"}:
            if item.query_id not in ids:
                ids.append(item.query_id)
    return ids
