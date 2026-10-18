"""Parameterized templates from architecture section 7, plus row mappers."""

from __future__ import annotations

import re
from typing import Any

from falkordb.node import Node

from app.domain.models import EvidenceItem
from app.graph.client import GraphGateway, GraphHandle, QueryOutcome, ToolFailure

_FULLTEXT = """
CALL db.idx.fulltext.queryNodes('EntityText', $q)
YIELD node, score
RETURN labels(node) AS labels, node.id AS id, node.name AS name,
       node.title AS title, node.status AS status, score
LIMIT 15
"""

_EXACT = """
MATCH (n)
WHERE (n:Service AND (n.name = $q OR n.name = $normalized))
   OR (n:Incident AND n.id = $q)
   OR (n:Person AND (n.name = $q OR n.name = $normalized))
RETURN labels(n) AS labels, n.id AS id, n.name AS name,
       n.title AS title, n.status AS status, 1 AS score
LIMIT 15
"""

_INCIDENTS_FOR_SERVICE = """
MATCH (i:Incident)-[:AFFECTS]->(s:Service {name: $service})
RETURN labels(i) AS labels, i.id AS id, i.name AS name,
       i.title AS title, i.status AS status, 1 AS score
"""

_TRACE = """
MATCH (i:Incident {id: $incidentId})-[:AFFECTS]->(s:Service)-[:DEPENDS_ON]->(dep:Dependency)
MATCH (d:Deployment)-[:DEPLOYED]->(s)
WHERE d.deployedAt <= i.openedAt
WITH i, s, dep, d
ORDER BY d.deployedAt DESC, dep.name ASC
LIMIT 1
MATCH (d)-[:CONTAINS]->(c:Commit)-[:IN_REPO]->(repo:Repository)
MATCH (person:Person)-[:AUTHORED]->(c)
MATCH (person)-[:MEMBER_OF]->(team:Team)
RETURN i.id AS incidentId, i.openedAt AS openedAt,
       s.name AS service, dep.name AS dependency, dep.kind AS dependencyKind,
       d.id AS deploymentId, d.deployedAt AS deployedAt, d.environment AS environment,
       c.sha AS sha, c.id AS commitId, c.message AS message, c.committedAt AS committedAt,
       repo.name AS repository,
       person.id AS authorId, person.name AS authorName,
       team.name AS team
"""

_IMPACT_SERVICES = """
MATCH (down:Service {name: $service})
MATCH (s:Service)
WHERE s.name <> down.name
WITH down, s, shortestPath((s)-[:DEPENDS_ON*1..4]->(down)) AS p
WHERE p IS NOT NULL
RETURN s.name AS service, s.tier AS tier, length(p) AS hops,
       [n IN nodes(p) | n.name] AS via
ORDER BY hops, service
LIMIT 25
"""

_IMPACT_PROJECTS = """
MATCH (down:Service {name: $service})
MATCH (proj:Project)-[:USES]->(s:Service)
WITH down, proj, s, shortestPath((s)-[:DEPENDS_ON*0..4]->(down)) AS p
WHERE p IS NOT NULL
RETURN proj.name AS project, s.name AS throughService, length(p) AS hops
ORDER BY hops, project
LIMIT 25
"""

_PREVIOUS = """
MATCH (i:Incident {id: $incidentId})-[:SIMILAR_TO]->(prev:Incident)
MATCH (prev)-[:RESOLVED_BY]->(r:Resolution)-[:PERFORMED_BY]->(p:Person)
RETURN prev.id AS incidentId, prev.title AS title, prev.status AS status,
       r.id AS resolutionId, r.summary AS summary, r.successful AS successful,
       r.resolvedAt AS resolvedAt, p.id AS personId, p.name AS personName
"""

_EXPERTS = """
MATCH (p:Person)-[w:WORKED_ON]->(:Service {name: $service})
OPTIONAL MATCH (p)-[:AUTHORED]->(:Commit)<-[:CONTAINS]-(d:Deployment {id: $deploymentId})
WITH p, w, d
OPTIONAL MATCH (p)<-[:PERFORMED_BY]-(r:Resolution)<-[:RESOLVED_BY]-(:Incident)
               <-[:SIMILAR_TO]-(:Incident {id: $incidentId})
WITH p, w,
     max(CASE WHEN d IS NULL THEN 0 ELSE 1 END) AS authoredSuspect,
     max(CASE WHEN r IS NULL THEN 0 ELSE 1 END) AS resolvedSimilar
OPTIONAL MATCH (p)-[:MEMBER_OF]->(team:Team)
RETURN p.id AS personId, p.name AS name, p.role AS role,
       w.commitCount AS commitCount, w.incidentCount AS incidentCount,
       authoredSuspect, resolvedSimilar, team.name AS team
"""

_LATEST_DEPLOY = """
MATCH (i:Incident {id: $incidentId})-[:AFFECTS]->(s:Service {name: $service})
MATCH (d:Deployment)-[:DEPLOYED]->(s)
WHERE d.deployedAt <= i.openedAt
RETURN d.id AS deploymentId
ORDER BY d.deployedAt DESC
LIMIT 1
"""

_PATH = """
MATCH (i:Incident {id: $incidentId})-[:AFFECTS]->(s:Service)
OPTIONAL MATCH (s)-[:DEPENDS_ON]->(dep:Dependency)
OPTIONAL MATCH (d:Deployment)-[:DEPLOYED]->(s)
  WHERE d.id = $deploymentId
OPTIONAL MATCH (d)-[:CONTAINS]->(c:Commit)-[:IN_REPO]->(repo:Repository)
OPTIONAL MATCH (person:Person)-[:AUTHORED]->(c)
OPTIONAL MATCH (person)-[:MEMBER_OF]->(team:Team)
OPTIONAL MATCH (i)-[:SIMILAR_TO]->(prev:Incident)-[:RESOLVED_BY]->(r:Resolution)
RETURN i, s, dep, d, c, repo, person, team, prev, r
"""

_OWNERSHIP = """
MATCH (t:Team)-[o:OWNS]->(s:Service {name: $service})
OPTIONAL MATCH (s)-[:DOCUMENTED_IN]->(doc:Document)
RETURN t.name AS team, o.since AS since, doc.id AS documentId,
       doc.title AS documentTitle, doc.source AS documentSource,
       doc.body AS documentBody
ORDER BY o.since DESC
"""

_SESSION = """
MATCH (d:Decision)<-[:DECIDED]-(i:Incident)-[:AFFECTS]->(s:Service)
WHERE d.episodeId IS NOT NULL AND i.id = $incidentId
MATCH (d)-[:ASSIGNED_TO]->(p:Person)
OPTIONAL MATCH (i)-[:SIMILAR_TO]->(prev:Incident)-[:RESOLVED_BY]->(r:Resolution)
RETURN d.id AS decisionId, d.summary AS summary, d.action AS action,
       d.rollbackCandidate AS rollbackCandidate, d.createdAt AS createdAt,
       d.episodeId AS episodeId, d.approvedBy AS approvedBy,
       i.id AS incidentId, s.name AS service,
       p.id AS personId, p.name AS personName,
       prev.id AS previousIncidentId, r.id AS resolutionId, r.summary AS resolution,
       r.successful AS successful
ORDER BY d.createdAt DESC
LIMIT 5
"""

_PATH_COLUMNS = ("i", "s", "dep", "d", "c", "repo", "person", "team", "prev", "r")
_HOPS = (
    ("AFFECTS", "i", "s"),
    ("DEPENDS_ON", "s", "dep"),
    ("DEPLOYED", "d", "s"),
    ("CONTAINS", "d", "c"),
    ("IN_REPO", "c", "repo"),
    ("AUTHORED", "person", "c"),
    ("MEMBER_OF", "person", "team"),
    ("SIMILAR_TO", "i", "prev"),
    ("RESOLVED_BY", "prev", "r"),
)
_FTS_CLEAN = re.compile(r"[^A-Za-z0-9 \-]+")


def run_tool(
    gateway: GraphGateway,
    handle: GraphHandle,
    tool: str,
    arguments: dict[str, Any],
    query_id: str,
) -> EvidenceItem:
    """Execute one allowlisted read. The caller has already passed the gate."""

    if tool == "search_entity":
        return _search(gateway, handle, arguments, query_id)
    if tool == "trace_dependency":
        return _named(
            gateway,
            handle,
            tool,
            _TRACE,
            arguments,
            query_id,
            "graph_fact",
            (
                "incidentId",
                "openedAt",
                "service",
                "dependency",
                "dependencyKind",
                "deploymentId",
                "deployedAt",
                "environment",
                "sha",
                "commitId",
                "message",
                "committedAt",
                "repository",
                "authorId",
                "authorName",
                "team",
            ),
        )
    if tool == "analyze_impact":
        return _impact(gateway, handle, arguments, query_id)
    if tool == "find_previous_incidents":
        return _named(
            gateway,
            handle,
            tool,
            _PREVIOUS,
            arguments,
            query_id,
            "graph_fact",
            (
                "incidentId",
                "title",
                "status",
                "resolutionId",
                "summary",
                "successful",
                "resolvedAt",
                "personId",
                "personName",
            ),
        )
    if tool == "find_domain_experts":
        return _experts(gateway, handle, arguments, query_id)
    if tool == "find_decision_path":
        return _path(gateway, handle, arguments, query_id)
    return _blocked(query_id, tool, "unknown tool")


def _search(
    gateway: GraphGateway,
    handle: GraphHandle,
    arguments: dict[str, Any],
    query_id: str,
) -> EvidenceItem:
    raw = str(arguments.get("query") or "")
    cleaned = _FTS_CLEAN.sub(" ", raw).strip()[:200]
    normalized = raw.strip().lower().replace(" ", "-")
    duration = 0
    truncated = False
    rows: list[dict[str, Any]] = []
    if cleaned:
        outcome = gateway.run_query(handle, _FULLTEXT, {"q": cleaned})
        if isinstance(outcome, ToolFailure):
            if outcome.error_category != "query":
                return _failure("search_entity", query_id, outcome)
        else:
            duration += outcome.duration_ms
            truncated = outcome.truncated
            rows = _dicts(outcome, ("labels", "id", "name", "title", "status", "score"))
    if not rows:
        outcome = gateway.run_query(
            handle,
            _EXACT,
            {"q": raw.strip(), "normalized": normalized},
        )
        if isinstance(outcome, ToolFailure):
            return _failure("search_entity", query_id, outcome)
        duration += outcome.duration_ms
        truncated = truncated or outcome.truncated
        rows = _dicts(outcome, ("labels", "id", "name", "title", "status", "score"))
    service_names = [
        row["name"]
        for row in rows
        if isinstance(row.get("labels"), list) and "Service" in row["labels"] and row.get("name")
    ]
    for service in service_names:
        outcome = gateway.run_query(handle, _INCIDENTS_FOR_SERVICE, {"service": service})
        if isinstance(outcome, ToolFailure):
            if outcome.error_category != "query":
                return _failure("search_entity", query_id, outcome)
            continue
        duration += outcome.duration_ms
        extra = _dicts(outcome, ("labels", "id", "name", "title", "status", "score"))
        rows = _dedupe_entities(rows + extra)
    if not rows:
        return _empty("search_entity", query_id, duration, "graph_fact")
    return _item(
        "search_entity",
        query_id,
        "graph_fact",
        "PARTIAL RESULT" if truncated else "SUCCESS",
        rows,
        duration,
        truncated=truncated,
    )


def _impact(
    gateway: GraphGateway,
    handle: GraphHandle,
    arguments: dict[str, Any],
    query_id: str,
) -> EvidenceItem:
    params = {"service": arguments["service"]}
    services = gateway.run_query(handle, _IMPACT_SERVICES, params)
    if isinstance(services, ToolFailure):
        return _failure("analyze_impact", query_id, services)
    projects = gateway.run_query(handle, _IMPACT_PROJECTS, params)
    if isinstance(projects, ToolFailure):
        return _failure("analyze_impact", query_id, projects)
    rows = _dicts(services, ("service", "tier", "hops", "via"))
    for row in rows:
        row["kind"] = "service"
    project_rows = _dicts(projects, ("project", "throughService", "hops"))
    for row in project_rows:
        row["kind"] = "project"
    rows.extend(project_rows)
    duration = services.duration_ms + projects.duration_ms
    truncated = services.truncated or projects.truncated
    if not rows:
        return _empty("analyze_impact", query_id, duration, "graph_fact", truncated)
    return _item(
        "analyze_impact",
        query_id,
        "graph_fact",
        "PARTIAL RESULT" if truncated else "SUCCESS",
        rows,
        duration,
        truncated=truncated,
    )


def _experts(
    gateway: GraphGateway,
    handle: GraphHandle,
    arguments: dict[str, Any],
    query_id: str,
) -> EvidenceItem:
    outcome = gateway.run_query(
        handle,
        _EXPERTS,
        {
            "service": arguments["service"],
            "incidentId": arguments["incidentId"],
            "deploymentId": arguments["deploymentId"],
        },
    )
    if isinstance(outcome, ToolFailure):
        return _failure("find_domain_experts", query_id, outcome)
    columns = (
        "personId",
        "name",
        "role",
        "commitCount",
        "incidentCount",
        "authoredSuspect",
        "resolvedSimilar",
        "team",
    )
    merged: dict[str, dict[str, Any]] = {}
    for row in _dicts(outcome, columns):
        person_id = str(row.get("personId") or "")
        if not person_id:
            continue
        current = merged.get(person_id)
        if current is None or _flag(row.get("authoredSuspect")) > _flag(current.get("authoredSuspect")):
            merged[person_id] = row
    ranked: list[dict[str, Any]] = []
    for row in merged.values():
        commits = _number(row.get("commitCount"))
        incidents = _number(row.get("incidentCount"))
        authored = _flag(row.get("authoredSuspect"))
        resolved = _flag(row.get("resolvedSimilar"))
        score = incidents * 5 + commits + authored * 10 + resolved * 10
        row["commitCount"] = commits
        row["incidentCount"] = incidents
        row["authoredSuspect"] = bool(authored)
        row["resolvedSimilar"] = bool(resolved)
        row["score"] = score
        row["scoreKind"] = "derived"
        row["reason"] = _expert_reason(authored, resolved)
        ranked.append(row)
    ranked.sort(key=lambda item: (-int(item["score"]), str(item["personId"])))
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    if not ranked:
        return _empty("find_domain_experts", query_id, outcome.duration_ms, "derived", outcome.truncated)
    return _item(
        "find_domain_experts",
        query_id,
        "derived",
        "PARTIAL RESULT" if outcome.truncated else "SUCCESS",
        ranked,
        outcome.duration_ms,
        truncated=outcome.truncated,
    )


def _path(
    gateway: GraphGateway,
    handle: GraphHandle,
    arguments: dict[str, Any],
    query_id: str,
) -> EvidenceItem:
    deployment_id = arguments.get("deploymentId")
    duration = 0
    if not isinstance(deployment_id, str) or not deployment_id.strip():
        latest = gateway.run_query(
            handle,
            _LATEST_DEPLOY,
            {"incidentId": arguments["incidentId"], "service": arguments["service"]},
        )
        if isinstance(latest, ToolFailure):
            return _failure("find_decision_path", query_id, latest)
        duration += latest.duration_ms
        found = _dicts(latest, ("deploymentId",))
        deployment_id = found[0]["deploymentId"] if found else ""
    path_outcome = gateway.run_query(
        handle,
        _PATH,
        {"incidentId": arguments["incidentId"], "deploymentId": deployment_id or ""},
    )
    if isinstance(path_outcome, ToolFailure):
        return _failure("find_decision_path", query_id, path_outcome)
    duration += path_outcome.duration_ms
    hops = _hops(path_outcome.rows, query_id)
    ownership = gateway.run_query(handle, _OWNERSHIP, {"service": arguments["service"]})
    if isinstance(ownership, ToolFailure):
        return _failure("find_decision_path", query_id, ownership)
    duration += ownership.duration_ms
    owner_rows = _ownership_rows(_dicts(
        ownership,
        ("team", "since", "documentId", "documentTitle", "documentSource", "documentBody"),
    ))
    session = gateway.run_query(handle, _SESSION, {"incidentId": arguments["incidentId"]})
    if isinstance(session, ToolFailure):
        return _failure("find_decision_path", query_id, session)
    duration += session.duration_ms
    decision_rows = _dicts(
        session,
        (
            "decisionId",
            "summary",
            "action",
            "rollbackCandidate",
            "createdAt",
            "episodeId",
            "approvedBy",
            "incidentId",
            "service",
            "personId",
            "personName",
            "previousIncidentId",
            "resolutionId",
            "resolution",
            "successful",
        ),
    )
    for row in decision_rows:
        row["rowType"] = "decision"
    rows = owner_rows + decision_rows
    truncated = path_outcome.truncated or ownership.truncated or session.truncated
    untrusted = any(isinstance(row.get("documentBody"), str) and row["documentBody"] for row in rows)
    if not hops and not rows:
        return _empty("find_decision_path", query_id, duration, "graph_fact", truncated)
    filled = [hop for hop in hops if not hop.get("gap")]
    status = "SUCCESS" if filled else "NO EVIDENCE"
    if truncated:
        status = "PARTIAL RESULT"
    return _item(
        "find_decision_path",
        query_id,
        "graph_fact",
        status,
        rows,
        duration,
        truncated=truncated,
        untrusted=untrusted,
        path=hops,
    )


def _named(
    gateway: GraphGateway,
    handle: GraphHandle,
    tool: str,
    cypher: str,
    arguments: dict[str, Any],
    query_id: str,
    kind: str,
    columns: tuple[str, ...],
) -> EvidenceItem:
    outcome = gateway.run_query(handle, cypher, dict(arguments))
    if isinstance(outcome, ToolFailure):
        return _failure(tool, query_id, outcome)
    rows = _dicts(outcome, columns)
    if not rows:
        return _empty(tool, query_id, outcome.duration_ms, kind, outcome.truncated)
    return _item(
        tool,
        query_id,
        kind,
        "PARTIAL RESULT" if outcome.truncated else "SUCCESS",
        rows,
        outcome.duration_ms,
        truncated=outcome.truncated,
    )


def _table(
    gateway: GraphGateway,
    handle: GraphHandle,
    tool: str,
    cypher: str,
    arguments: dict[str, Any],
    query_id: str,
    kind: str,
) -> EvidenceItem:
    outcome = gateway.run_query(handle, cypher, dict(arguments))
    if isinstance(outcome, ToolFailure):
        return _failure(tool, query_id, outcome)
    rows = _zip_headers(outcome)
    if not rows:
        return _empty(tool, query_id, outcome.duration_ms, kind, outcome.truncated)
    return _item(
        tool,
        query_id,
        kind,
        "PARTIAL RESULT" if outcome.truncated else "SUCCESS",
        rows,
        outcome.duration_ms,
        truncated=outcome.truncated,
    )


def _hops(rows: list[list[Any]], query_id: str) -> list[dict[str, Any]]:
    chosen: dict[str, Any] = {}
    best_dep_name: str | None = None
    best_dep: Any = None
    for row in rows:
        if len(row) < len(_PATH_COLUMNS):
            continue
        mapped = dict(zip(_PATH_COLUMNS, row, strict=False))
        dep = mapped.get("dep")
        dep_name = _node_key(dep)
        if dep_name and (best_dep_name is None or dep_name < best_dep_name):
            best_dep_name = dep_name
            best_dep = dep
        for key, node in mapped.items():
            if key == "dep":
                continue
            if node is not None and key not in chosen:
                chosen[key] = node
    if best_dep is not None:
        chosen["dep"] = best_dep
    hops: list[dict[str, Any]] = []
    for index, (relationship, source, target) in enumerate(_HOPS):
        left = chosen.get(source)
        right = chosen.get(target)
        if left is None or right is None:
            hops.append(
                {
                    "index": index,
                    "relationship": relationship,
                    "gap": True,
                    "queryId": query_id,
                }
            )
            continue
        hops.append(
            {
                "index": index,
                "fromLabel": _node_label(left),
                "fromKey": _node_key(left),
                "fromName": _node_name(left),
                "relationship": relationship,
                "toLabel": _node_label(right),
                "toKey": _node_key(right),
                "toName": _node_name(right),
                "gap": False,
                "queryId": query_id,
            }
        )
    return hops


def _ownership_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: str(row.get("since") or ""), reverse=True)
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for row in ordered:
        team = str(row.get("team") or "")
        if not team or team in seen:
            continue
        seen.add(team)
        currency = "current" if not result else "stale"
        result.append(
            {
                "rowType": "ownership",
                "team": team,
                "since": row.get("since"),
                "currency": currency,
                "documentId": row.get("documentId"),
                "documentTitle": row.get("documentTitle"),
                "documentSource": row.get("documentSource"),
                "documentBody": row.get("documentBody"),
            }
        )
    return result


def _dicts(outcome: QueryOutcome, columns: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in outcome.rows:
        rows.append({name: _plain(raw[index]) for index, name in enumerate(columns) if index < len(raw)})
    return rows


def _zip_headers(outcome: QueryOutcome) -> list[dict[str, Any]]:
    headers = outcome.headers
    rows: list[dict[str, Any]] = []
    for raw in outcome.rows:
        if headers and len(headers) == len(raw):
            rows.append({headers[index]: _plain(value) for index, value in enumerate(raw)})
        else:
            rows.append({f"c{index}": _plain(value) for index, value in enumerate(raw)})
    return rows


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Node):
        return _node_key(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    return str(value)


def _node_props(node: Any) -> dict[str, Any]:
    if not isinstance(node, Node):
        return {}
    props = node.properties or {}
    return dict(props)


def _node_key(node: Any) -> str | None:
    props = _node_props(node)
    if isinstance(props.get("id"), str) and props["id"]:
        return props["id"]
    if isinstance(props.get("name"), str) and props["name"]:
        return props["name"]
    return None


def _node_name(node: Any) -> str | None:
    props = _node_props(node)
    name = props.get("name")
    if isinstance(name, str) and name and name != _node_key(node):
        return name
    return None


def _node_label(node: Any) -> str | None:
    if not isinstance(node, Node) or not node.labels:
        return None
    labels = [label for label in node.labels if label != "EntityText"]
    return labels[0] if labels else None


def _dedupe_entities(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    kept: list[dict[str, Any]] = []
    for row in rows:
        labels = row.get("labels") if isinstance(row.get("labels"), list) else []
        label = next((item for item in labels if item != "EntityText"), "")
        key = str(row.get("id") or row.get("name") or "")
        marker = (str(label), key)
        if marker in seen:
            continue
        seen.add(marker)
        kept.append(row)
    return kept


def _expert_reason(authored: int, resolved: int) -> str:
    if authored and resolved:
        return "authored the suspect commit and resolved the similar incident"
    if authored:
        return "authored the suspect commit"
    if resolved:
        return "resolved the similar incident"
    return "history on the service"


def _flag(value: Any) -> int:
    if value is True:
        return 1
    if value is False or value is None:
        return 0
    try:
        return 1 if int(value) else 0
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _item(
    tool: str,
    query_id: str,
    kind: str,
    status: str,
    rows: list[dict[str, Any]],
    duration_ms: int,
    *,
    truncated: bool = False,
    untrusted: bool = False,
    path: list[dict[str, Any]] | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        query_id=query_id,
        tool=tool,
        kind=kind,
        status=status,
        rows=rows,
        duration_ms=duration_ms,
        result_count=len(rows),
        truncated=truncated,
        untrusted=untrusted,
        path=path or [],
    )


def _empty(
    tool: str,
    query_id: str,
    duration_ms: int,
    kind: str,
    truncated: bool = False,
) -> EvidenceItem:
    status = "PARTIAL RESULT" if truncated else "NO EVIDENCE"
    return _item(tool, query_id, kind, status, [], duration_ms, truncated=truncated)


def _failure(tool: str, query_id: str, failure: ToolFailure) -> EvidenceItem:
    return EvidenceItem(
        query_id=query_id,
        tool=tool,
        kind="graph_fact",
        status="TOOL FAILURE",
        rows=[],
        duration_ms=failure.duration_ms,
        result_count=0,
        error_category=failure.error_category,
    )


def _blocked(query_id: str, tool: str, _reason: str) -> EvidenceItem:
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
