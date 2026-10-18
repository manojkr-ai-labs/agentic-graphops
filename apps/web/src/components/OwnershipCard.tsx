interface OwnerRow {
  team?: string;
  since?: string;
  currency?: string;
  documentId?: string;
  documentSource?: string;
  documentTitle?: string;
}

export function OwnershipCard({ rows }: { rows: OwnerRow[] }) {
  if (rows.length === 0) return null;
  const document = rows.find((row) => row.documentId);
  return (
    <div className="space-y-2.5 rounded-xl border border-line bg-panel p-4">
      <div className="flex items-center justify-between">
        <h4 className="text-[11px] font-semibold tracking-[0.04em] text-ink uppercase">Ownership and provenance</h4>
        <span className="font-mono text-[11px] text-muted">{rows.length} teams</span>
      </div>
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.team} className="flex items-center justify-between rounded-md border border-line bg-canvas p-2">
            <div className="flex flex-col">
              <span className="font-mono text-xs text-ink">{row.team}</span>
              <span className="font-mono text-[11px] text-muted">since {formatSince(row.since)}</span>
            </div>
            <span
              className={`inline-flex h-5 items-center rounded border px-1.5 font-mono text-[11px] font-semibold uppercase ${
                row.currency === "current"
                  ? "border-ok text-ok"
                  : "border-line text-muted"
              }`}
            >
              {row.currency}
            </span>
          </div>
        ))}
      </div>
      {document?.documentId ? (
        <p className="font-mono text-[11px] text-muted">
          {document.documentId}
          {document.documentTitle ? ` · ${document.documentTitle}` : ""} · {document.documentSource}
        </p>
      ) : null}
    </div>
  );
}

function formatSince(value: string | undefined): string {
  if (!value) return "unknown";
  return value.slice(0, 10);
}
