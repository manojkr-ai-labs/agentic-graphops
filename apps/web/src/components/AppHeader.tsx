import { Keyboard } from "lucide-react";

interface AppHeaderProps {
  tenant: string;
  actor: string;
  sessionId: string;
  graphUp: boolean | null;
  onTenant: (value: string) => void;
  onActor: (value: string) => void;
  onSession: (value: string) => void;
}

export function AppHeader({
  tenant,
  actor,
  sessionId,
  graphUp,
  onTenant,
  onActor,
  onSession,
}: AppHeaderProps) {
  const initials = actor
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");

  return (
    <header className="z-20 flex h-14 shrink-0 items-center justify-between border-b border-line bg-panel px-4">
      <div className="flex min-w-0 items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-base font-semibold tracking-tight text-ink">GraphOps</span>
          <span className="font-mono text-[11px] text-faint">/</span>
          <span className="text-[11px] font-semibold tracking-[0.04em] text-muted uppercase">
            Investigation agent
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-l border-line pl-3">
          <Chip label="Tenant" value={tenant} onChange={onTenant} />
          <Chip label="Actor" value={actor} onChange={onActor} />
          <Chip label="Session" value={sessionId} onChange={onSession} active />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex h-8 items-center gap-1.5 rounded-md border border-line bg-canvas px-2.5">
          <span className={`h-1.5 w-1.5 rounded-full ${graphUp ? "bg-ok" : "bg-crit"}`} />
          <span className="font-mono text-[11px] text-ink">
            {graphUp === null ? "FalkorDB checking" : graphUp ? "FalkorDB connected" : "FalkorDB unreachable"}
          </span>
        </div>
        <div className="hidden h-8 items-center gap-1.5 rounded-md border border-line bg-panel-2 px-2 text-muted sm:flex">
          <Keyboard size={14} />
          <span className="font-mono text-[11px] text-ink">1–3</span>
        </div>
        <div
          className="flex h-8 w-8 items-center justify-center rounded-full border border-line bg-panel-2 font-mono text-[11px] font-semibold text-ink"
          title={actor}
        >
          {initials || "OP"}
        </div>
      </div>
    </header>
  );
}

function Chip({
  label,
  value,
  onChange,
  active = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  active?: boolean;
}) {
  return (
    <label className="flex h-8 items-center gap-1 rounded-md border border-line bg-canvas px-2 font-mono text-[11px] text-muted focus-within:border-accent">
      <span>{label}</span>
      <input
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`w-28 bg-transparent outline-none placeholder:text-faint ${active ? "text-accent" : "text-ink"}`}
      />
    </label>
  );
}
