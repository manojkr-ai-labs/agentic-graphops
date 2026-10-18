"""Bounded planner loop. The write tool is not offered here."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.agent.planner import ScriptedPlanner, question_kind
from app.agent.synthesizer import synthesize
from app.agent.validate import citation_errors
from app.config import Settings
from app.domain.models import EvidenceItem, Interpretation, Recommendation
from app.domain.status import investigation_status
from app.graph.client import GraphGateway, GraphHandle, PolicyBlocked, ToolFailure
from app.llm.client import LlmFailure
from app.tools.registry import execute, read_catalog


class Planner(Protocol):
    def plan(
        self,
        question: str,
        evidence: list[EvidenceItem],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return `{stop, calls}` or raise LlmFailure."""


@dataclass
class LoopResult:
    status: str
    evidence: list[EvidenceItem]
    path: list[dict[str, Any]]
    interpretation: list[Interpretation]
    recommendation: Recommendation | None
    uncertainty: list[str]
    proposal: dict[str, str] | None
    kind: str


def run_loop(
    gateway: GraphGateway,
    tenant: str,
    question: str,
    session_id: str,
    actor: str,
    settings: Settings,
    planner: Planner | None = None,
) -> LoopResult | PolicyBlocked | ToolFailure:
    opened = gateway.open_tenant(tenant)
    if isinstance(opened, (PolicyBlocked, ToolFailure)):
        return opened
    return _loop(gateway, opened, question, session_id, actor, settings, planner or ScriptedPlanner())


def _loop(
    gateway: GraphGateway,
    handle: GraphHandle,
    question: str,
    session_id: str,
    actor: str,
    settings: Settings,
    planner: Planner,
) -> LoopResult:
    kind = question_kind(question)
    evidence: list[EvidenceItem] = []
    counter = 0
    capped = False
    llm_failed = False
    catalog = read_catalog()
    for _iteration in range(settings.max_agent_iterations):
        try:
            plan = planner.plan(question, evidence, catalog)
        except LlmFailure:
            llm_failed = True
            break
        calls = plan.get("calls") if isinstance(plan, dict) else None
        if not isinstance(plan, dict) or plan.get("stop") or not calls:
            break
        for call in calls:
            counter += 1
            tool = call.get("tool") if isinstance(call, dict) else ""
            arguments = call.get("arguments") if isinstance(call, dict) else {}
            evidence.append(
                execute(gateway, handle, str(tool), arguments, f"q_{counter:02d}")
            )
    else:
        capped = True

    recommendation: Recommendation | None = None
    interpretation: list[Interpretation] = []
    uncertainty: list[str] = []
    validation_failed = False
    if not llm_failed:
        recommendation, interpretation, uncertainty = _synthesize(planner, question, evidence)
        if recommendation is not None:
            errors = citation_errors(recommendation, evidence)
            if errors:
                recommendation, interpretation, retry_uncertainty = _synthesize(planner, question, evidence)
                uncertainty = list(retry_uncertainty) + [f"Citation check failed: {error}" for error in errors]
                if recommendation is None or citation_errors(recommendation, evidence):
                    validation_failed = True
                    recommendation = None
                    interpretation = []
                    uncertainty.append("The recommendation failed citation checks twice.")

    status = investigation_status(
        kind,
        evidence,
        recommendation,
        capped=capped,
        llm_failed=llm_failed,
        validation_failed=validation_failed,
    )
    if llm_failed or validation_failed:
        recommendation = None
        interpretation = []
        if llm_failed:
            uncertainty = ["The model did not return a plan."]
    path: list[dict[str, Any]] = []
    for item in evidence:
        if item.tool == "find_decision_path" and item.path:
            path = item.path
    proposal = None
    if (
        status == "SUCCESS"
        and kind == "change"
        and recommendation is not None
        and recommendation.rollback_candidate
        and recommendation.assignee_id
    ):
        proposal = _proposal(recommendation, evidence, session_id, actor)
    return LoopResult(
        status=status,
        evidence=evidence,
        path=path,
        interpretation=interpretation,
        recommendation=recommendation,
        uncertainty=uncertainty,
        proposal=proposal,
        kind=kind,
    )


def _synthesize(
    planner: Planner,
    question: str,
    evidence: list[EvidenceItem],
) -> tuple[Recommendation | None, list[Interpretation], list[str]]:
    method = getattr(planner, "synthesize", None)
    if callable(method):
        result = method(question, evidence)
        if result is None:
            return None, [], []
        recommendation, interpretation, uncertainty = result
        return recommendation, interpretation, uncertainty
    return synthesize(question, evidence)


def _proposal(
    recommendation: Recommendation,
    evidence: list[EvidenceItem],
    session_id: str,
    actor: str,
) -> dict[str, str] | None:
    incident = _incident_id(evidence)
    if not incident or not recommendation.rollback_candidate or not recommendation.assignee_id:
        return None
    number = incident.removeprefix("INC-") if incident.startswith("INC-") else incident
    team = "payments-platform"
    for item in evidence:
        for row in item.rows:
            if isinstance(row.get("team"), str) and row["team"]:
                team = row["team"]
                break
    name = recommendation.assignee_name or recommendation.assignee_id
    return {
        "decisionId": f"DEC-{number}-1",
        "incidentId": incident,
        "summary": recommendation.summary,
        "rollbackCandidate": recommendation.rollback_candidate,
        "assigneeId": recommendation.assignee_id,
        "assigneeName": name,
        "action": "rollback",
        "episodeId": session_id,
        "approvedBy": actor,
        "team": team,
    }


def _incident_id(evidence: list[EvidenceItem]) -> str | None:
    for item in evidence:
        for row in item.rows:
            if item.tool == "trace_dependency" and isinstance(row.get("incidentId"), str):
                return row["incidentId"]
            labels = row.get("labels") or []
            if isinstance(labels, list) and "Incident" in labels and row.get("status") == "open":
                if isinstance(row.get("id"), str):
                    return row["id"]
    return None
