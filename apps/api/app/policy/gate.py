"""A tool call runs only after its name and arguments are accepted."""

from __future__ import annotations

from typing import Any

READ_TOOLS = (
    "search_entity",
    "trace_dependency",
    "analyze_impact",
    "find_previous_incidents",
    "find_domain_experts",
    "find_decision_path",
)

_REQUIRED: dict[str, tuple[str, ...]] = {
    "search_entity": ("query",),
    "trace_dependency": ("incidentId",),
    "analyze_impact": ("service",),
    "find_previous_incidents": ("incidentId",),
    "find_domain_experts": ("service", "incidentId", "deploymentId"),
    "find_decision_path": ("incidentId", "service"),
}
_OPTIONAL: dict[str, tuple[str, ...]] = {
    "find_decision_path": ("deploymentId",),
}
_FORBIDDEN = {"tenant", "graph", "actor", "cypher"}
_STRING_CAP = 256


def catalog() -> list[dict[str, Any]]:
    """The six read tools. The write tool is not in this object."""

    described = []
    for name in READ_TOOLS:
        described.append(
            {
                "tool": name,
                "required": list(_REQUIRED[name]),
                "optional": list(_OPTIONAL.get(name, ())),
            }
        )
    return described


def reject_reason(tool: str, arguments: object) -> str | None:
    """Return a rejection reason, or None when the call may run."""

    if tool not in _REQUIRED:
        return "unknown tool"
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    keys = set(arguments)
    if keys & _FORBIDDEN:
        return "forbidden argument"
    allowed = set(_REQUIRED[tool]) | set(_OPTIONAL.get(tool, ()))
    if keys - allowed:
        return "unknown argument"
    for name in _REQUIRED[tool]:
        if _bad_string(arguments.get(name)):
            return "invalid argument"
    for name in _OPTIONAL.get(tool, ()):
        if name not in arguments or arguments[name] is None:
            continue
        if _bad_string(arguments[name]):
            return "invalid argument"
    return None


def _bad_string(value: object) -> bool:
    return not isinstance(value, str) or not value.strip() or len(value) > _STRING_CAP
