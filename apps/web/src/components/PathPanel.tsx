import { Minus, Plus, Route, Waypoints } from "lucide-react";
import { useMemo, useState } from "react";
import type { Hop } from "../api/types";

export function PathPanel({ hops }: { hops: Hop[] }) {
  const [scale, setScale] = useState(1);
  const filled = hops.filter((hop) => !hop.gap);
  const layout = useMemo(() => layoutHops(hops), [hops]);

  return (
    <section className="flex min-h-[420px] min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-line bg-panel">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Waypoints size={16} className="text-muted" />
          <h2 className="text-base font-semibold">Path</h2>
          <span className="font-mono text-[11px] text-muted">{filled.length} hops</span>
        </div>
        <div className="flex h-8 items-center overflow-hidden rounded-md border border-line bg-canvas">
          <button type="button" aria-label="Zoom in" className="flex h-8 w-8 items-center justify-center text-muted hover:bg-hover hover:text-ink" onClick={() => setScale((value) => Math.min(1.6, value + 0.1))}>
            <Plus size={14} />
          </button>
          <button type="button" aria-label="Zoom out" className="flex h-8 w-8 items-center justify-center border-x border-line text-muted hover:bg-hover hover:text-ink" onClick={() => setScale((value) => Math.max(0.6, value - 0.1))}>
            <Minus size={14} />
          </button>
          <button type="button" className="flex h-8 items-center px-2 font-mono text-[11px] text-muted hover:bg-hover hover:text-ink" onClick={() => setScale(1)}>
            Reset
          </button>
        </div>
      </div>
      {hops.length === 0 ? (
        <div className="dot-pattern flex flex-1 items-center justify-center p-6">
          <div className="max-w-md text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-line bg-panel-2 text-muted">
              <Route size={24} />
            </div>
            <h3 className="mb-1.5 text-base font-semibold">No investigation path loaded</h3>
            <p className="text-[13px] leading-relaxed text-muted">
              Run a question to load the traversed path from FalkorDB.
            </p>
          </div>
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col">
          <div className="shrink-0 border-b border-line bg-canvas p-4">
            <div className="mb-2 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-ink">Traversed path</h3>
              <span className="rounded border border-line bg-panel-2 px-2 py-0.5 font-mono text-[11px] text-muted">
                {filled.length} hops
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {hops.map((hop) =>
                hop.gap ? (
                  <span key={hop.index} className="rounded border border-dashed border-line px-2 py-1 font-mono text-[11px] text-faint">
                    gap {hop.relationship}
                  </span>
                ) : (
                  <span key={hop.index} className="flex items-center gap-1.5">
                    <NodeChip label={hop.fromLabel} id={hop.fromKey} name={hop.fromName} />
                    <span className="font-mono text-[11px] text-accent">{hop.relationship}</span>
                    {hop.index === hops.length - 1 || hops[hop.index + 1]?.gap ? (
                      <NodeChip label={hop.toLabel} id={hop.toKey} name={hop.toName} />
                    ) : null}
                  </span>
                ),
              )}
            </div>
          </div>
          <div className="dot-pattern relative min-h-[220px] flex-1 overflow-auto bg-canvas">
            <svg
              width={layout.width * scale}
              height={layout.height * scale}
              viewBox={`0 0 ${layout.width} ${layout.height}`}
              role="img"
              aria-label="Investigation path"
              className="block"
            >
              {layout.edges.map((edge) => (
                <line
                  key={edge.id}
                  x1={edge.x1}
                  y1={edge.y1}
                  x2={edge.x2}
                  y2={edge.y2}
                  stroke="#4C8DFF"
                  strokeWidth="1.5"
                />
              ))}
              {layout.nodes.map((node) => (
                <g key={node.id} transform={`translate(${node.x}, ${node.y})`}>
                  <rect width="148" height="48" rx="8" fill="#161C24" stroke="#2A3340" />
                  <rect width="3" height="48" rx="1" fill="#4C8DFF" />
                  <text x="12" y="20" fill="#8E9AAB" fontSize="10" fontFamily="JetBrains Mono, monospace">
                    {node.label}
                  </text>
                  <text x="12" y="36" fill="#E8EEF5" fontSize="12" fontFamily="JetBrains Mono, monospace">
                    {trim(node.id, 16)}
                  </text>
                </g>
              ))}
            </svg>
          </div>
        </div>
      )}
    </section>
  );
}

function NodeChip({ label, id, name }: { label?: string; id?: string; name?: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-line bg-panel px-2 py-1">
      <span className="font-mono text-[11px] text-muted">{label}</span>
      <span className="font-mono text-[11px] text-ink">{id}</span>
      {name ? <span className="text-[11px] text-muted">{name}</span> : null}
    </span>
  );
}

function layoutHops(hops: Hop[]) {
  const nodes: { id: string; label: string; x: number; y: number }[] = [];
  const index = new Map<string, number>();
  const add = (key?: string, label?: string) => {
    if (!key || index.has(key)) return;
    const position = nodes.length;
    index.set(key, position);
    const column = position % 4;
    const row = Math.floor(position / 4);
    nodes.push({ id: key, label: label ?? "node", x: 24 + column * 180, y: 24 + row * 88 });
  };
  for (const hop of hops) {
    if (hop.gap) continue;
    add(hop.fromKey, hop.fromLabel);
    add(hop.toKey, hop.toLabel);
  }
  const edges = hops.flatMap((hop) => {
    if (hop.gap || !hop.fromKey || !hop.toKey) return [];
    const from = index.get(hop.fromKey);
    const to = index.get(hop.toKey);
    if (from === undefined || to === undefined) return [];
    const source = nodes[from];
    const target = nodes[to];
    return [
      {
        id: `${hop.index}-${hop.relationship}`,
        x1: source.x + 148,
        y1: source.y + 24,
        x2: target.x,
        y2: target.y + 24,
      },
    ];
  });
  const rows = Math.max(1, Math.ceil(nodes.length / 4));
  return { nodes, edges, width: 24 + 4 * 180, height: 48 + rows * 88 };
}

function trim(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}
