"""Start an investigation, refresh it, and approve the one write."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
from dataclasses import dataclass, field
from typing import Any

from app.actions.decision import record_decision
from app.agent.loop import Planner, run_loop
from app.agent.planner import question_kind
from app.config import Settings
from app.domain.models import EvidenceItem, Interpretation, Recommendation, TimelineEntry
from app.graph.client import GraphGateway, PolicyBlocked, ToolFailure
from app.obs.log import log_step
from app.policy.limits import RateLimiter

_SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ACTOR = re.compile(r"^[A-Za-z0-9_ .:-]{1,64}$")


@dataclass
class StoredInvestigation:
    investigation_id: str
    request_id: str
    tenant: str
    actor: str
    session_id: str
    question: str
    status: str
    evidence: list[EvidenceItem]
    path: list[dict[str, Any]]
    interpretation: list[Interpretation]
    recommendation: Recommendation | None
    uncertainty: list[str]
    action_state: str
    proposal: dict[str, str] | None
    token: str | None
    proposal_hash: str | None
    notice: str | None = None
    proof_query_id: str | None = None
    decision: dict[str, Any] | None = None
    timeline: list[TimelineEntry] = field(default_factory=list)


class InvestigationService:
    def __init__(self, settings: Settings, gateway: GraphGateway, logger: logging.Logger) -> None:
        self._settings = settings
        self._gateway = gateway
        self._logger = logger
        self._limiter = RateLimiter()
        self._items: dict[str, StoredInvestigation] = {}
        self._seq = 0
        self._lock = threading.Lock()

    def start(
        self,
        *,
        tenant: str,
        actor: str,
        session_id: str,
        question: str,
        request_id: str,
        planner: Planner | None = None,
    ) -> dict[str, Any]:
        if _ACTOR.fullmatch(actor or "") is None or _SESSION.fullmatch(session_id or "") is None:
            return _denied("POLICY BLOCKED", "The actor or session id was rejected.")
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            return _denied("POLICY BLOCKED", "The question was rejected.")
        if self._gateway.tenant_graph_name(tenant) is None:
            return _denied("POLICY BLOCKED", "The tenant id was rejected.")
        with self._lock:
            if not self._limiter.allow(tenant):
                log_step(
                    self._logger,
                    requestId=request_id,
                    tenant=tenant,
                    step="investigate",
                    status="POLICY BLOCKED",
                    errorCategory="rate",
                    resultCount=0,
                    durationMs=0,
                )
                return _denied("POLICY BLOCKED", "This tenant exceeded 30 investigation starts in a minute.")
            self._seq += 1
            investigation_id = f"inv_{self._seq:02d}"

        outcome = run_loop(
            self._gateway,
            tenant,
            question.strip(),
            session_id,
            actor,
            self._settings,
            planner,
        )
        if isinstance(outcome, PolicyBlocked):
            log_step(
                self._logger,
                requestId=request_id,
                investigationId=investigation_id,
                tenant=tenant,
                step="investigate",
                status="POLICY BLOCKED",
                errorCategory="policy",
                durationMs=outcome.duration_ms,
                resultCount=0,
            )
            return _denied("POLICY BLOCKED", "The tenant graph was rejected.")
        if isinstance(outcome, ToolFailure):
            log_step(
                self._logger,
                requestId=request_id,
                investigationId=investigation_id,
                tenant=tenant,
                step="investigate",
                tool="gateway",
                status="TOOL FAILURE",
                errorCategory=outcome.error_category,
                durationMs=outcome.duration_ms,
                resultCount=0,
            )
            stored = StoredInvestigation(
                investigation_id=investigation_id,
                request_id=request_id,
                tenant=tenant,
                actor=actor,
                session_id=session_id,
                question=question.strip(),
                status="TOOL FAILURE",
                evidence=[],
                path=[],
                interpretation=[],
                recommendation=None,
                uncertainty=["FalkorDB did not return rows."],
                action_state="NONE",
                proposal=None,
                token=None,
                proposal_hash=None,
            )
            with self._lock:
                self._items[investigation_id] = stored
            return _public(stored)

        timeline = [
            TimelineEntry(item.query_id, item.tool, item.duration_ms, item.result_count, item.status)
            for item in outcome.evidence
        ]
        for item in outcome.evidence:
            log_step(
                self._logger,
                requestId=request_id,
                investigationId=investigation_id,
                tenant=tenant,
                step="tool",
                tool=item.tool,
                queryId=item.query_id,
                durationMs=item.duration_ms,
                resultCount=item.result_count,
                status=item.status,
                errorCategory=item.error_category,
            )
        token = None
        proposal_hash = None
        action_state = "NONE"
        if outcome.proposal and outcome.status == "SUCCESS":
            token = secrets.token_urlsafe(32)
            proposal_hash = _hash_proposal(outcome.proposal)
            action_state = "AWAITING_APPROVAL"
        stored = StoredInvestigation(
            investigation_id=investigation_id,
            request_id=request_id,
            tenant=tenant,
            actor=actor,
            session_id=session_id,
            question=question.strip(),
            status=outcome.status,
            evidence=outcome.evidence,
            path=outcome.path,
            interpretation=outcome.interpretation,
            recommendation=outcome.recommendation,
            uncertainty=outcome.uncertainty,
            action_state=action_state,
            proposal=outcome.proposal,
            token=token,
            proposal_hash=proposal_hash,
            timeline=timeline,
        )
        with self._lock:
            self._items[investigation_id] = stored
        return _public(stored)

    def get(self, investigation_id: str) -> dict[str, Any] | None:
        with self._lock:
            stored = self._items.get(investigation_id)
        if stored is None:
            return None
        return _public(stored)

    def approve(
        self,
        investigation_id: str,
        token: object,
        actor: str,
        request_id: str,
    ) -> dict[str, Any] | None:
        with self._lock:
            stored = self._items.get(investigation_id)
        if stored is None:
            return None
        proposal = stored.proposal
        presented = token if isinstance(token, str) else ""
        expected = stored.token or ""
        actor_ok = hmac.compare_digest(actor, stored.actor)
        token_ok = bool(expected) and hmac.compare_digest(presented, expected)
        hash_ok = bool(proposal) and stored.proposal_hash == _hash_proposal(proposal or {})
        if not actor_ok or not token_ok or not hash_ok or proposal is None:
            log_step(
                self._logger,
                requestId=request_id,
                investigationId=investigation_id,
                tenant=stored.tenant,
                step="approve",
                status="POLICY BLOCKED",
                errorCategory="policy",
                resultCount=0,
                durationMs=0,
            )
            denied = _public(stored)
            denied["status"] = "POLICY BLOCKED"
            denied["uncertainty"] = list(stored.uncertainty) + ["Approval was rejected. Nothing was written."]
            return denied

        opened = self._gateway.open_tenant(stored.tenant)
        if isinstance(opened, PolicyBlocked):
            denied = _public(stored)
            denied["status"] = "POLICY BLOCKED"
            return denied
        if isinstance(opened, ToolFailure):
            denied = _public(stored)
            denied["status"] = "TOOL FAILURE"
            return denied

        result = record_decision(self._gateway, opened, proposal, stored.evidence)
        log_step(
            self._logger,
            requestId=request_id,
            investigationId=investigation_id,
            tenant=stored.tenant,
            step="approve",
            tool="record_agent_memory",
            durationMs=result.duration_ms,
            resultCount=1 if result.decision else 0,
            status=result.status,
            errorCategory=result.error_category,
        )
        if result.status != "SUCCESS":
            denied = _public(stored)
            denied["status"] = result.status
            denied["uncertainty"] = list(stored.uncertainty) + ["The write did not complete."]
            return denied

        with self._lock:
            current = self._items[investigation_id]
            current.token = None
            current.action_state = "RECORDED"
            current.notice = result.notice
            current.decision = result.decision
            current.proof_query_id = f"q_{len(current.timeline) + 1:02d}"
            current.timeline.append(
                TimelineEntry(
                    current.proof_query_id,
                    "record_agent_memory",
                    result.duration_ms,
                    1,
                    "SUCCESS",
                )
            )
            if current.status == "SUCCESS" or result.already_existed:
                current.status = "SUCCESS"
            snapshot = current
        return _public(snapshot)


def _hash_proposal(proposal: dict[str, str]) -> str:
    material = {
        key: proposal.get(key, "")
        for key in (
            "decisionId",
            "incidentId",
            "summary",
            "rollbackCandidate",
            "assigneeId",
            "action",
            "episodeId",
        )
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _denied(status: str, detail: str) -> dict[str, Any]:
    return {
        "investigationId": None,
        "status": status,
        "evidence": [],
        "path": [],
        "interpretation": [],
        "recommendation": None,
        "uncertainty": [detail],
        "action": {"state": "NONE", "proposal": None, "approvalToken": None, "notice": None},
        "timeline": [],
        "question": None,
        "sessionId": None,
    }


def _public(stored: StoredInvestigation) -> dict[str, Any]:
    recommendation = None
    if stored.recommendation is not None:
        recommendation = {
            "summary": stored.recommendation.summary,
            "rollbackCandidate": stored.recommendation.rollback_candidate,
            "assigneeId": stored.recommendation.assignee_id,
            "assigneeName": stored.recommendation.assignee_name,
            "basedOnQueryIds": stored.recommendation.based_on_query_ids,
        }
    return {
        "investigationId": stored.investigation_id,
        "status": stored.status,
        "question": stored.question,
        "sessionId": stored.session_id,
        "tenant": stored.tenant,
        "kind": question_kind(stored.question),
        "evidence": [_evidence(item) for item in stored.evidence],
        "path": stored.path,
        "interpretation": [
            {"text": item.text, "basedOnQueryIds": item.based_on_query_ids}
            for item in stored.interpretation
        ],
        "recommendation": recommendation,
        "uncertainty": stored.uncertainty,
        "action": {
            "state": stored.action_state,
            "proposal": stored.proposal,
            "approvalToken": stored.token if stored.action_state == "AWAITING_APPROVAL" else None,
            "notice": stored.notice,
            "proofQueryId": stored.proof_query_id,
            "decision": stored.decision,
        },
        "timeline": [
            {
                "queryId": entry.query_id,
                "tool": entry.tool,
                "durationMs": entry.duration_ms,
                "resultCount": entry.result_count,
                "status": entry.status,
            }
            for entry in stored.timeline
        ],
    }


def _evidence(item: EvidenceItem) -> dict[str, Any]:
    return {
        "queryId": item.query_id,
        "tool": item.tool,
        "kind": item.kind,
        "status": item.status,
        "rows": item.rows,
        "durationMs": item.duration_ms,
        "resultCount": item.result_count,
        "truncated": item.truncated,
        "untrusted": item.untrusted,
    }
