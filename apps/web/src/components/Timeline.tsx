import type { TimelineEntry } from "../api/types";

export function Timeline({ entries }: { entries: TimelineEntry[] }) {
  return (
    <div className="space-y-2.5 rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between border-b border-line pb-1.5">
        <h3 className="text-sm font-semibold text-ink">Timeline</h3>
        <span className="font-mono text-[11px] text-muted">
          {entries.length} {entries.length === 1 ? "step" : "steps"}
        </span>
      </div>
      {entries.length === 0 ? (
        <p className="font-mono text-[11px] text-muted">No tool calls yet.</p>
      ) : (
        <div className="space-y-1.5">
          {entries.map((entry) => (
            <div
              key={entry.queryId}
              id={`timeline-${entry.queryId}`}
              className="flex items-center justify-between rounded-md border border-line bg-panel-2 p-1.5 font-mono text-[11px]"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="text-[11px] text-muted">{entry.queryId}</span>
                <span className="truncate font-medium text-ink">{entry.tool}</span>
              </div>
              <div className="ml-2 flex shrink-0 items-center gap-2 text-[11px]">
                <span className="text-muted">{entry.durationMs}ms</span>
                <span className="text-faint">
                  {entry.resultCount} {entry.resultCount === 1 ? "row" : "rows"}
                </span>
                <span className={entry.status === "SUCCESS" ? "font-semibold text-ok" : "font-semibold text-crit"}>
                  {entry.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
