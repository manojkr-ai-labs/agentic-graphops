import type { Health, Investigation } from "./types";

const base = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: string;

  constructor(status: string) {
    super(status);
    this.status = status;
  }
}

export async function fetchHealth(): Promise<Health | null> {
  try {
    const response = await fetch(`${base}/api/health`);
    return (await response.json()) as Health;
  } catch {
    return null;
  }
}

export async function startInvestigation(
  tenant: string,
  actor: string,
  sessionId: string,
  question: string,
): Promise<Investigation> {
  const response = await fetch(`${base}/api/investigations`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Tenant-Id": tenant,
      "X-Actor": actor,
    },
    body: JSON.stringify({ sessionId, question }),
  });
  return (await response.json()) as Investigation;
}

export async function approveInvestigation(
  id: string,
  actor: string,
  approvalToken: string,
): Promise<Investigation> {
  const response = await fetch(`${base}/api/investigations/${id}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Actor": actor,
    },
    body: JSON.stringify({ approvalToken }),
  });
  return (await response.json()) as Investigation;
}
