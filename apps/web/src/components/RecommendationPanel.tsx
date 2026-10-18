import { Sparkles } from "lucide-react";
import type { EvidenceItem, Interpretation, Proposal, Recommendation } from "../api/types";
import { ActionPanel } from "./ActionPanel";
import { OwnershipCard } from "./OwnershipCard";

interface RecommendationPanelProps {
  recommendation: Recommendation | null;
  interpretation: Interpretation[];
  uncertainty: string[];
  evidence: EvidenceItem[];
  actionState: string;
  proposal: Proposal | null;
  notice: string | null;
  approving: boolean;
  failed: boolean;
  onApprove: () => void;
  onCite: (queryId: string) => void;
}

export function RecommendationPanel({
  recommendation,
  interpretation,
  uncertainty,
  evidence,
  actionState,
  proposal,
  notice,
  approving,
  failed,
  onApprove,
  onCite,
}: RecommendationPanelProps) {
  const experts = evidence.find((item) => item.tool === "find_domain_experts")?.rows ?? [];
  const owners = evidence.flatMap((item) =>
    item.rows.filter((row) => row.rowType === "ownership"),
  ) as {
    team?: string;
    since?: string;
    currency?: string;
    documentId?: string;
    documentSource?: string;
    documentTitle?: string;
  }[];

  return (
    <section className="flex w-full shrink-0 flex-col overflow-hidden rounded-xl border border-line bg-panel xl:w-[360px]">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-muted" />
          <h2 className="text-base font-semibold">Recommendation</h2>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        <div className="space-y-3">
          <div className="space-y-3 rounded-xl border border-line bg-panel p-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Recommendation</h3>
              <div className="flex gap-1">
                {recommendation?.basedOnQueryIds.map((queryId) => (
                  <button
                    key={queryId}
                    type="button"
                    onClick={() => onCite(queryId)}
                    className="flex h-8 items-center rounded-md border border-line bg-canvas px-1.5 font-mono text-[11px] text-accent"
                  >
                    {queryId}
                  </button>
                ))}
              </div>
            </div>
            <p className="rounded-xl border border-line bg-canvas p-4 text-[13px] leading-relaxed text-ink">
              {recommendation?.summary ??
                (failed
                  ? "No recommendation generated. The investigation ended before a cited answer."
                  : "Waiting for graph traversal.")}
            </p>
            {recommendation?.rollbackCandidate ? (
              <p className="font-mono text-[11px] text-muted">
                Rollback candidate <span className="text-ok">{recommendation.rollbackCandidate}</span>
                {recommendation.assigneeId ? (
                  <>
                    {" "}
                    · assignee <span className="text-accent">{recommendation.assigneeId}</span>{" "}
                    {recommendation.assigneeName}
                  </>
                ) : null}
              </p>
            ) : null}
          </div>
          {interpretation.map((item) => (
            <div key={item.text} className="rounded-xl border border-line border-l-2 border-l-accent bg-panel p-4">
              <h4 className="mb-1 text-[11px] font-semibold tracking-[0.04em] text-ink uppercase">Interpretation</h4>
              <p className="text-xs leading-relaxed text-muted">{item.text}</p>
            </div>
          ))}
          {uncertainty.length > 0 ? (
            <div className="rounded-xl border border-line bg-panel p-4">
              <h4 className="mb-1 text-[11px] font-semibold tracking-[0.04em] text-ink uppercase">Uncertainty</h4>
              <ul className="space-y-1">
                {uncertainty.map((line) => (
                  <li key={line} className="text-xs leading-relaxed text-muted">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {experts.length > 0 ? (
            <div className="space-y-2 rounded-xl border border-line bg-panel p-4">
              <h4 className="text-[11px] font-semibold tracking-[0.04em] text-ink uppercase">Strongest history</h4>
              <p className="text-[11px] text-muted">Derived score from graph counts. Not a stored property.</p>
              {experts.map((row) => (
                <div key={String(row.personId)} className="flex gap-2 rounded-md border border-line bg-canvas p-2">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-warn font-mono text-[11px] text-warn">
                    {String(row.rank)}
                  </span>
                  <div className="min-w-0 text-[11px] leading-snug">
                    <p className="text-ink">
                      {String(row.name)} · <span className="font-mono text-accent">{String(row.personId)}</span> ·{" "}
                      {String(row.role ?? "")}
                    </p>
                    <p className="text-muted">
                      score {String(row.score)} · commits {String(row.commitCount)} · incidents {String(row.incidentCount)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
          <OwnershipCard rows={owners} />
        </div>
        <div className="mt-auto border-t border-line pt-3">
          <ActionPanel
            state={actionState}
            proposal={proposal}
            notice={notice}
            approving={approving}
            onApprove={onApprove}
          />
        </div>
      </div>
    </section>
  );
}
