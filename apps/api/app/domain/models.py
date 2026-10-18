"""Investigation records. Interpretation is never stored as an evidence row."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    query_id: str
    tool: str
    kind: str
    status: str
    rows: list[dict[str, Any]]
    duration_ms: int
    result_count: int
    truncated: bool = False
    untrusted: bool = False
    error_category: str | None = None
    path: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """Compact planner view. Document text is omitted."""

        services: list[str] = []
        incidents: list[dict[str, Any]] = []
        fields: dict[str, Any] = {}
        hidden = {"documentBody", "body", "message"}
        for row in self.rows:
            labels = row.get("labels") or []
            if isinstance(labels, list) and "Service" in labels and isinstance(row.get("name"), str):
                services.append(row["name"])
            if isinstance(labels, list) and "Incident" in labels and isinstance(row.get("id"), str):
                incidents.append({"id": row["id"], "status": row.get("status")})
            for key, value in row.items():
                if key in hidden or key in fields:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    fields[key] = value
            if row.get("kind") == "service" and isinstance(row.get("service"), str):
                services.append(row["service"])
        return {
            "queryId": self.query_id,
            "tool": self.tool,
            "status": self.status,
            "count": self.result_count,
            "fields": fields,
            "services": services,
            "incidents": incidents,
        }


@dataclass
class Interpretation:
    text: str
    based_on_query_ids: list[str]


@dataclass
class Recommendation:
    summary: str
    based_on_query_ids: list[str]
    rollback_candidate: str | None = None
    assignee_id: str | None = None
    assignee_name: str | None = None


@dataclass
class TimelineEntry:
    query_id: str
    tool: str
    duration_ms: int
    result_count: int
    status: str
