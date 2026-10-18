# GraphOps Intelligence Agent

GraphOps investigates a payment-service incident by traversing a tenant graph in FalkorDB. One agent plans six read tools, cites the rows they return, and proposes a single next action. A person approves that action. The API then writes one `Decision` back into the same graph. A later session reads that node from FalkorDB.

This is a submission for [Graph Hacks: Context for AI Agents](https://www.wemakedevs.org/hackathons/falkordb) (15–18 October 2026). FalkorDB is the primary graph database. The seed data is synthetic.

The answer is a path: incident, service, dependency, deployment, commit, repository, author, team, prior incident, and resolution. Timing and the commit message are an interpretation, shown apart from the rows. There is no `CAUSED` edge. Removing `CONTAINS` or `SIMILAR_TO` changes the recommendation, because every cited id has to appear in a FalkorDB row from this investigation.

## Tracks

| Track | Name | How this repository meets it |
|---|---|---|
| 01 (primary) | Agents That Act on Connected Data | The agent traverses the payment incident, cites those rows, and writes one approved `Decision`. |
| 02 | Agent Memory and Coordination | Session 2 reads the session 1 `Decision`, the assignee, and the earlier resolution from FalkorDB. |
| 03 | Company Brain | Question 3 answers ownership, impact, projects, and the source document on the same graph. |

## Run

There is no public deployment. FalkorDB is the only container. The API and the screen are host processes. Python 3.11 or newer and a current Node.js are required.

From the repository root, copy `.env.example` to `.env`. `LLM_MODEL` and `LLM_BASE_URL` are required. The example file sets `LLM_MODEL=local`, which uses an evidence-bound planner: tool arguments are ids returned by earlier rows, and the recommendation is rejected when a citation is not in the log. Set `LLM_MODEL` to another name to call `LLM_BASE_URL` instead. Leave `VITE_API_BASE_URL` empty so the Vite dev server proxies `/api` to port 8000.

```text
docker compose up -d
python -m pip install -e "apps/api[dev]"
graphops-seed
graphops-api
```

`docker compose` starts `falkordb/falkordb:latest` on port 6379. `graphops-seed` loads `graphops_acme` and `graphops_globex`. The API listens on http://127.0.0.1:8000.

In another shell:

```text
cd apps/web
npm install
npm run dev
```

The screen is http://localhost:5173. It is the Calm SRE Precision workspace.

Demo principal: tenant `acme`, actor `incident-commander`, session `ses_01`. The header edits `X-Tenant-Id` and `X-Actor`. Use New session before question 2. `globex` does not contain `INC-203` or `DEC-203-1`.

The working demo video is [demo/graphops-demo.mp4](demo/graphops-demo.mp4). It is two to three minutes and follows the loop below.

## Questions

Paste these in order. Approve only question 1.

1. Session `ses_01`. *The payment service started failing after the latest deployment. Identify the likely change, the downstream systems, the engineer with the strongest relevant history, and the safest next action.* Expect `DEP-1042`, commit `C-8891` in `payments-repo`, downstream `checkout-api`, `billing-worker`, `merchant-portal`, projects `checkout-platform` and `billing-platform`, engineer Ava Shah (`E-17`). Approve writes `DEC-203-1`. The notice contains `SIMULATED` and says it was not delivered.
2. New session. *A new payment failure looks similar. What did we decide last time, and who should own this?* Expect `DEC-203-1`, rollback `DEP-1042`, assignee `E-17`, and the `RES-44` summary, read from FalkorDB.
3. *What breaks if the payment service goes down, and which document supports the ownership claim?* Expect the downstream services and projects, `payments-platform` current, `legacy-payments` stale, document `DOC-PAY-OWN` from `runbook/payment-service.md`. No write.

## How the agent uses FalkorDB

```text
Question → tool plan → policy check → FalkorDB template → evidence → recommendation → approval → Decision
```

The model receives a tool name and validated arguments. Cypher stays in server templates. The allowlist is `search_entity`, `trace_dependency`, `analyze_impact`, `find_previous_incidents`, `find_domain_experts`, `find_decision_path`, and `record_agent_memory`. This product does not use MCP.

Multi-hop reasoning is the section 41.3 chain:

```text
Incident → Service → Dependency → Deployment → Commit → Repository → Engineer → Team → Previous Incident → Resolution
```

`analyze_impact` uses `shortestPath` on `DEPENDS_ON`, depth 4, toward the failed service. `fraud-service` is upstream and is not a result.

Memory has three kinds, all stored in the tenant graph:

- Episodic: the investigation id on the `Decision` (`episodeId`).
- Semantic: the service, owner, dependency, and prior incident already linked in the graph.
- Procedural: the action taken (`rollbackCandidate`, `action`, `ASSIGNED_TO`).

One tenant graph cannot be read with another tenant’s header. A later session, or a later agent, reads this `Decision`. It does not read the chat transcript.

The only executed write is the approved `Decision`, plus `DECIDED` and `ASSIGNED_TO`, in one Cypher statement. `createdAt` is the API clock. Document text and ticket text cannot authorize that write. The channel notice is simulated.

The screen keeps facts, the traversed path, interpretation, the recommendation, uncertainty, and action status in separate panels. A score computed in the tool is labeled derived. User-visible status is one of `SUCCESS`, `NO EVIDENCE`, `PARTIAL RESULT`, `TOOL FAILURE`, `POLICY BLOCKED`, or `SYSTEM ERROR`. An empty or failed query keeps that status.

## Graph data model

Seeded labels and properties:

| Node | Properties |
|---|---|
| `Incident` | `id`, `title`, `openedAt`, `status` |
| `Service` | `name`, `tier` |
| `Dependency` | `name`, `kind` |
| `Deployment` | `id`, `deployedAt`, `environment` |
| `Commit` | `sha`, `message`, `committedAt` |
| `Repository` | `name` |
| `Person` | `name`, `role` |
| `Team` | `name` |
| `Project` | `name` |
| `Resolution` | `id`, `summary`, `successful`, `resolvedAt` |
| `Decision` | `id`, `summary`, `rollbackCandidate`, `createdAt`, `approvedBy` |
| `Document` | `title`, `source` |

Relationships: `AFFECTS`, `DEPENDS_ON`, `DEPLOYED`, `CONTAINS`, `IN_REPO`, `AUTHORED`, `MEMBER_OF`, `OWNS` (with `since`), `WORKED_ON`, `SIMILAR_TO`, `RESOLVED_BY`, `PERFORMED_BY`, `USES`, `DOCUMENTED_IN`, `DECIDED`, `ASSIGNED_TO`.

`DECIDED` and `ASSIGNED_TO` are created when the person approves. The seed also contains an older `OWNS` edge so question 3 can show `legacy-payments` as stale and `payments-platform` as current.

## Cypher the product depends on

Parameterized copies live in `apps/api/app/tools/queries.py` and `apps/api/app/actions/decision.py`. The queries that decide the demo are below.

`trace_dependency` keeps the latest deployment at or before the incident opened, then follows the commit into the repository and the author:

```cypher
MATCH (i:Incident {id: $incidentId})-[:AFFECTS]->(s:Service)-[:DEPENDS_ON]->(dep:Dependency)
MATCH (d:Deployment)-[:DEPLOYED]->(s)
WHERE d.deployedAt <= i.openedAt
WITH i, s, dep, d
ORDER BY d.deployedAt DESC, dep.name ASC
LIMIT 1
MATCH (d)-[:CONTAINS]->(c:Commit)-[:IN_REPO]->(repo:Repository)
MATCH (person:Person)-[:AUTHORED]->(c)
MATCH (person)-[:MEMBER_OF]->(team:Team)
RETURN i.id, s.name, dep.name, d.id, c.sha, c.id, repo.name, person.id, person.name, team.name
```

`analyze_impact` (services). Projects use the same `shortestPath` through `USES`:

```cypher
MATCH (down:Service {name: $service})
MATCH (s:Service)
WHERE s.name <> down.name
WITH down, s, shortestPath((s)-[:DEPENDS_ON*1..4]->(down)) AS p
WHERE p IS NOT NULL
RETURN s.name AS service, length(p) AS hops, [n IN nodes(p) | n.name] AS via
ORDER BY hops, service
```

`find_domain_experts` reads prior work, authorship of the suspect deployment, and resolution of the similar incident. The rank is computed in the tool and labeled derived:

```text
score = incidentCount * 5 + commitCount + authoredSuspect * 10 + resolvedSimilar * 10
```

Ties break by `personId` ascending.

The approved write and the proof query:

```cypher
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
```

```cypher
MATCH (i:Incident {id: $incidentId})-[:DECIDED]->(d:Decision)-[:ASSIGNED_TO]->(p:Person)
WHERE d.id = $decisionId
RETURN d.id, d.rollbackCandidate, d.approvedBy, p.id, p.name
```

Question 2 uses `find_decision_path` plus this session read:

```cypher
MATCH (d:Decision)<-[:DECIDED]-(i:Incident)-[:AFFECTS]->(s:Service)
WHERE d.episodeId IS NOT NULL AND i.id = $incidentId
MATCH (d)-[:ASSIGNED_TO]->(p:Person)
OPTIONAL MATCH (i)-[:SIMILAR_TO]->(prev:Incident)-[:RESOLVED_BY]->(r:Resolution)
RETURN d.id, d.rollbackCandidate, p.id, r.id, r.summary
ORDER BY d.createdAt DESC
LIMIT 5
```

## Limits

Demo headers are not production authentication. The on-screen timeline is in memory and disappears when the API restarts. The `Decision` remains in FalkorDB. The notification is simulated. PageRank and extra agents are out of scope.

## Tests

```text
pytest tests/graph tests/policy tests/agent tests/api
```

Graph tests need FalkorDB and use a disposable graph name.

## AI assistant disclosure

An AI coding assistant implemented the agent loop, the query templates, the approval write, and the investigation screen in this repository. The graph model, the three questions, the tool allowlist, the approval rule, and the expected ids were specified for this hackathon and checked against the seeded FalkorDB graphs.
