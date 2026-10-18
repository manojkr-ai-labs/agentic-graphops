interface StatusCardProps {
  status: string | null;
  investigationId: string | null;
  sessionId: string;
  detail?: string;
}

export function StatusCard({ status, investigationId, sessionId, detail }: StatusCardProps) {
  return (
    <div className="space-y-2 rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between">
        {status ? <StatusBadge status={status} /> : <span className="font-mono text-[11px] text-muted">IDLE</span>}
        <span className="font-mono text-[11px] tracking-[0.04em] text-muted uppercase">STATUS</span>
      </div>
      <p className="font-mono text-[11px] leading-relaxed break-words text-muted">
        {investigationId ? `${investigationId} · session ${sessionId}` : `session ${sessionId}`}
        {detail ? ` · ${detail}` : ""}
      </p>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone = toneFor(status);
  return (
    <span className={`inline-flex h-5 items-center rounded border px-1.5 font-mono text-[11px] font-semibold uppercase ${tone}`}>
      {status}
    </span>
  );
}

function toneFor(status: string): string {
  if (status === "SUCCESS" || status === "RECORDED") {
    return "border-ok text-ok";
  }
  if (status === "PARTIAL RESULT" || status === "AWAITING_APPROVAL" || status === "AWAITING APPROVAL") {
    return "border-warn text-warn";
  }
  if (status === "NO EVIDENCE") {
    return "border-line bg-panel text-muted";
  }
  return "border-crit text-crit";
}
