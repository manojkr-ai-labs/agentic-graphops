import type { EvidenceItem } from "../api/types";

const HIDDEN = new Set(["documentBody", "body", "via", "message"]);

export function EvidencePanel({ items }: { items: EvidenceItem[] }) {
  const visible = items.filter((item) => item.kind === "graph_fact" || item.kind === "derived");
  return (
    <div className="border-t border-line bg-canvas p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-ink">Evidence</h3>
        <span className="font-mono text-[11px] text-muted">{visible.length} queries</span>
      </div>
      {visible.length === 0 ? (
        <p className="font-mono text-[11px] text-muted">No graph rows yet.</p>
      ) : (
        <div className="space-y-2">
          {visible.map((item) => (
            <article key={item.queryId} id={`evidence-${item.queryId}`} className="rounded-xl border border-line bg-panel p-4">
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-accent">{item.queryId}</span>
                  <span className="font-mono text-[11px] text-ink">{item.tool}</span>
                </div>
                <span className="font-mono text-[11px] text-muted">
                  {item.kind === "derived" ? "derived" : "graph fact"}
                  {item.truncated ? " · truncated" : ""}
                  {item.untrusted ? " · untrusted" : ""}
                </span>
              </div>
              {item.rows.length === 0 ? (
                <p className="font-mono text-[11px] text-muted">{item.status}</p>
              ) : (
                <ul className="space-y-1">
                  {item.rows.map((row, index) => (
                    <li key={`${item.queryId}-${index}`} className="font-mono text-[11px] leading-relaxed text-muted">
                      {Object.entries(row)
                        .filter(([key, value]) => !HIDDEN.has(key) && value !== null && value !== "")
                        .map(([key, value]) => `${key} ${formatValue(value)}`)
                        .join(" · ")}
                    </li>
                  ))}
                </ul>
              )}
              {item.untrusted ? <UntrustedBody rows={item.rows} /> : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function UntrustedBody({ rows }: { rows: Record<string, unknown>[] }) {
  const body = rows.map((row) => row.documentBody).find((value) => typeof value === "string");
  if (typeof body !== "string" || body.length === 0) return null;
  return (
    <p className="mt-2 rounded-md border border-crit/40 bg-crit/10 p-2 font-mono text-[11px] text-crit">
      Untrusted document text: {body}
    </p>
  );
}

function formatValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}
