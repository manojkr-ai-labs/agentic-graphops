import { CheckCircle2 } from "lucide-react";
import type { Proposal } from "../api/types";

interface ActionPanelProps {
  state: string;
  proposal: Proposal | null;
  notice: string | null;
  approving: boolean;
  onApprove: () => void;
}

export function ActionPanel({ state, proposal, notice, approving, onApprove }: ActionPanelProps) {
  if (!proposal && state !== "RECORDED") {
    return (
      <button
        type="button"
        disabled
        className="flex h-8 w-full cursor-not-allowed items-center justify-center gap-1.5 rounded-md border border-line bg-panel-2 text-[11px] font-medium text-ink disabled:opacity-50"
      >
        Awaiting a proposed decision
      </button>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-[11px] font-semibold tracking-[0.04em] text-ink uppercase">Proposed decision</h4>
        <span
          className={`inline-flex h-5 items-center rounded border px-1.5 font-mono text-[11px] font-semibold uppercase ${
            state === "RECORDED"
              ? "border-ok text-ok"
              : "border-warn text-warn"
          }`}
        >
          {state === "AWAITING_APPROVAL" ? "AWAITING APPROVAL" : state}
        </span>
      </div>
      {proposal ? (
        <dl className="space-y-1.5 border-y border-line py-2 font-mono text-[11px]">
          <Row label="ID / Decision" value={proposal.decisionId} />
          <Row label="Summary" value={proposal.summary} />
          <Row label="Action" value={proposal.action} />
          <Row label="Episode" value={proposal.episodeId} />
          <Row label="Approved by" value={proposal.approvedBy} />
        </dl>
      ) : null}
      <button
        type="button"
        onClick={onApprove}
        disabled={state !== "AWAITING_APPROVAL" || approving}
        className="flex h-8 w-full items-center justify-center gap-2 rounded-md bg-accent text-sm font-semibold text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        <CheckCircle2 size={16} />
        {approving ? "Writing" : "Approve decision"}
      </button>
      <p className="text-center font-mono text-[11px] text-muted">Writes one Decision to the graph after approval.</p>
      {notice ? (
        <div className="space-y-1 rounded-md border border-line bg-canvas p-2.5">
          <p className="font-mono text-[11px] tracking-[0.04em] text-muted uppercase">Recorded notice</p>
          <p className="font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap text-muted">{notice}</p>
        </div>
      ) : null}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <dt className="shrink-0 tracking-[0.04em] text-muted uppercase">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
