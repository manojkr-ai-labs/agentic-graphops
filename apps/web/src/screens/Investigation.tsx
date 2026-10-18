import { useEffect, useState } from "react";
import { approveInvestigation, fetchHealth, startInvestigation } from "../api/client";
import type { Investigation } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { EvidencePanel } from "../components/EvidencePanel";
import { PathPanel } from "../components/PathPanel";
import { QuestionPanel } from "../components/QuestionPanel";
import { RecommendationPanel } from "../components/RecommendationPanel";
import { StatusCard } from "../components/StatusCard";
import { Timeline } from "../components/Timeline";

const FAILED = new Set(["TOOL FAILURE", "POLICY BLOCKED", "SYSTEM ERROR", "NO EVIDENCE", "PARTIAL RESULT"]);

export function Investigation() {
  const [tenant, setTenant] = useState("acme");
  const [actor, setActor] = useState("incident-commander");
  const [sessionId, setSessionId] = useState("ses_01");
  const [question, setQuestion] = useState("");
  const [preset, setPreset] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [approving, setApproving] = useState(false);
  const [graphUp, setGraphUp] = useState<boolean | null>(null);
  const [result, setResult] = useState<Investigation | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => {
      void fetchHealth().then((health) => {
        if (!cancelled) setGraphUp(health?.status === "healthy" && health.graph === "up");
      });
    };
    load();
    const timer = window.setInterval(load, 10000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  function clearResult() {
    setResult(null);
  }

  async function run() {
    if (!question.trim() || running) return;
    setRunning(true);
    try {
      const body = await startInvestigation(tenant.trim(), actor.trim(), sessionId.trim(), question.trim());
      setResult(body);
    } catch {
      setResult({
        investigationId: null,
        status: "SYSTEM ERROR",
        question,
        sessionId,
        evidence: [],
        path: [],
        interpretation: [],
        recommendation: null,
        uncertainty: ["The API could not be reached."],
        action: { state: "NONE", proposal: null, approvalToken: null, notice: null },
        timeline: [],
      });
    } finally {
      setRunning(false);
    }
  }

  async function approve() {
    const token = result?.action.approvalToken;
    const id = result?.investigationId;
    if (!token || !id || approving) return;
    setApproving(true);
    try {
      const body = await approveInvestigation(id, actor.trim(), token);
      setResult(body);
    } finally {
      setApproving(false);
    }
  }

  function newSession() {
    const match = /^ses_(\d+)$/.exec(sessionId);
    const next = match ? `ses_${String(Number(match[1]) + 1).padStart(2, "0")}` : "ses_02";
    setSessionId(next);
    clearResult();
  }

  const failed = result ? FAILED.has(result.status) && result.recommendation === null : false;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-canvas text-ink">
      <AppHeader
        tenant={tenant}
        actor={actor}
        sessionId={sessionId}
        graphUp={graphUp}
        onTenant={(value) => {
          setTenant(value);
          clearResult();
        }}
        onActor={setActor}
        onSession={setSessionId}
      />
      <main className="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4 xl:flex-row xl:overflow-hidden">
        <div className="flex w-full flex-col gap-3 lg:w-[340px] lg:shrink-0">
          <QuestionPanel
            question={question}
            activeId={preset}
            running={running}
            onQuestion={(value, id) => {
              setQuestion(value);
              setPreset(id || null);
            }}
            onRun={() => void run()}
            onNewSession={newSession}
          />
          <StatusCard
            status={result?.status ?? null}
            investigationId={result?.investigationId ?? null}
            sessionId={sessionId}
          />
          <Timeline entries={result?.timeline ?? []} />
        </div>
        <div className="flex min-h-[70vh] min-w-0 flex-1 flex-col gap-3 xl:min-h-0">
          <PathPanel hops={result?.path ?? []} />
          <div className="max-h-72 overflow-y-auto rounded-xl border border-line bg-panel xl:max-h-[34%]">
            <EvidencePanel items={result?.evidence ?? []} />
          </div>
        </div>
        <RecommendationPanel
          recommendation={result?.recommendation ?? null}
          interpretation={result?.interpretation ?? []}
          uncertainty={result?.uncertainty ?? []}
          evidence={result?.evidence ?? []}
          actionState={result?.action.state ?? "NONE"}
          proposal={result?.action.proposal ?? null}
          notice={result?.action.notice ?? null}
          approving={approving}
          failed={failed}
          onApprove={() => void approve()}
          onCite={(queryId) => {
            document.getElementById(`evidence-${queryId}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            document.getElementById(`timeline-${queryId}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
          }}
        />
      </main>
    </div>
  );
}
