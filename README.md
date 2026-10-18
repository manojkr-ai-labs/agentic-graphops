# GraphOps Intelligence Agent

GraphOps answers a payment-service incident by traversing a tenant graph in FalkorDB. One agent plans six read tools, cites the rows they return, and proposes a single next action. A person approves that action. The API then writes one `Decision` back into the same graph. A later session reads that node from FalkorDB. It does not read the chat transcript.

The graph is required because the answer is a path: incident, service, dependency, deployment, commit, repository, author, team, prior incident, and resolution. There is no `CAUSED` edge. Timing and the commit message are an interpretation, shown apart from the rows.

## Run

FalkorDB is the only container. The API and the screen are host processes.

```text
docker compose up -d
```

From the repository root, with the Python environment that has `apps/api` installed:

```text
graphops-seed
graphops-api
```

The API listens on port 8000. In another shell:

```text
cd apps/web
npm install
npm run dev
```

The screen is http://localhost:5173. `LLM_MODEL=local` uses an evidence-bound planner: tool arguments are ids returned by earlier rows, and the recommendation is rejected when a citation is not in the log. Set `LLM_MODEL` to another name to call `LLM_BASE_URL` instead. Copy `.env.example` to `.env` if you have not already.

Demo principal: tenant `acme`, actor `incident-commander`, session `ses_01`. The header edits `X-Tenant-Id` and `X-Actor`. Use New session before question 2.

## Questions

1. Likely change. Expect `DEP-1042`, commit `C-8891` in `payments-repo`, downstream `checkout-api`, `billing-worker`, `merchant-portal`, projects `checkout-platform` and `billing-platform`, engineer Ava Shah (`E-17`). Approve writes `DEC-203-1`. The notice contains `SIMULATED` and says it was not delivered.
2. Last decision, new session. Expect `DEC-203-1`, rollback `DEP-1042`, assignee `E-17`, and the `RES-44` summary, read from FalkorDB.
3. What breaks. Expect the downstream services and projects, `payments-platform` current, `legacy-payments` stale, document `DOC-PAY-OWN` from `runbook/payment-service.md`. No write.

`globex` does not contain `INC-203` or `DEC-203-1`.

## Graph

Labels: `Incident`, `Service`, `Dependency`, `Deployment`, `Commit`, `Repository`, `Person`, `Team`, `Project`, `Resolution`, `Decision`, `Document`.

Relationships: `AFFECTS`, `DEPENDS_ON`, `DEPLOYED`, `CONTAINS`, `IN_REPO`, `AUTHORED`, `MEMBER_OF`, `OWNS`, `WORKED_ON`, `SIMILAR_TO`, `RESOLVED_BY`, `PERFORMED_BY`, `USES`, `DOCUMENTED_IN`, `DECIDED`, `ASSIGNED_TO`.

Queries that matter:

- `trace_dependency` keeps the latest deployment at or before the incident opened.
- `analyze_impact` uses `shortestPath` on `DEPENDS_ON`, depth 4, toward the failed service. `fraud-service` is upstream and is not a result.
- Expert score, computed in the tool and labeled derived: `incidentCount * 5 + commitCount + authoredSuspect * 10 + resolvedSimilar * 10`. Ties break by `personId` ascending.
- The `Decision` write runs only after approval, in one Cypher statement. `createdAt` is the API clock.
- Question 2 uses `find_decision_path` plus the session read of that `Decision`.

## Tracks

Track 01 is the investigation loop. Track 02 is session 2 reading the `Decision` from FalkorDB. Track 03 is question 3 on the same graph: impact, ownership, and the source document.

## Limits

Demo headers are not production authentication. The on-screen timeline is in memory and disappears when the API restarts. The `Decision` remains in FalkorDB. The notification is simulated. PageRank and extra agents are out of scope. the live palette is canvas #0E1217, panel #161C24, accent #4C8DFF, ok #22C55E, warn #EAB308, crit #EF4444.

## Tests

```text
pytest tests/graph tests/policy tests/agent tests/api
```

Graph tests need FalkorDB and use a disposable graph name.

An AI assistant implemented and verified the agent, the query templates, the approval write, and the investigation screen in this repository.
