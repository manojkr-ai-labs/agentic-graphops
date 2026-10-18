export type StatusName =
  | "SUCCESS"
  | "NO EVIDENCE"
  | "PARTIAL RESULT"
  | "TOOL FAILURE"
  | "POLICY BLOCKED"
  | "SYSTEM ERROR";

export interface EvidenceItem {
  queryId: string;
  tool: string;
  kind: "graph_fact" | "derived";
  status: string;
  rows: Record<string, unknown>[];
  durationMs: number;
  resultCount: number;
  truncated: boolean;
  untrusted: boolean;
}

export interface Hop {
  index: number;
  relationship: string;
  gap?: boolean;
  queryId: string;
  fromLabel?: string;
  fromKey?: string;
  fromName?: string;
  toLabel?: string;
  toKey?: string;
  toName?: string;
}

export interface Interpretation {
  text: string;
  basedOnQueryIds: string[];
}

export interface Recommendation {
  summary: string;
  rollbackCandidate: string | null;
  assigneeId: string | null;
  assigneeName: string | null;
  basedOnQueryIds: string[];
}

export interface Proposal {
  decisionId: string;
  incidentId: string;
  summary: string;
  rollbackCandidate: string;
  assigneeId: string;
  assigneeName: string;
  action: string;
  episodeId: string;
  approvedBy: string;
  team: string;
}

export interface TimelineEntry {
  queryId: string;
  tool: string;
  durationMs: number;
  resultCount: number;
  status: string;
}

export interface Investigation {
  investigationId: string | null;
  status: StatusName | string;
  question: string | null;
  sessionId: string | null;
  tenant?: string;
  kind?: string;
  evidence: EvidenceItem[];
  path: Hop[];
  interpretation: Interpretation[];
  recommendation: Recommendation | null;
  uncertainty: string[];
  action: {
    state: string;
    proposal: Proposal | null;
    approvalToken: string | null;
    notice: string | null;
    proofQueryId?: string | null;
    decision?: Record<string, unknown> | null;
  };
  timeline: TimelineEntry[];
}

export interface Health {
  status: "healthy" | "unhealthy";
  api: "up";
  graph: "up" | "down";
}
