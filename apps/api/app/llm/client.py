"""Chat completion against LLM_BASE_URL. Timeouts and 5xx are a system error."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.config import Settings


class LlmFailure(RuntimeError):
    """The model did not return a usable object. The message is a category."""

    def __init__(self, error_category: str) -> None:
        super().__init__(error_category)
        self.error_category = error_category


class HttpLlm:
    """Used when LLM_MODEL is not the offline `local` planner."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def complete(self, system: str, user: str) -> dict[str, Any]:
        url = self._settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self._settings.llm_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method="POST")
        request.add_header("Content-Type", "application/json")
        key = self._settings.llm_api_key.get_secret_value()
        if key:
            request.add_header("Authorization", f"Bearer {key}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", 200)
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            if exc.code >= 500:
                raise LlmFailure("upstream") from None
            raise LlmFailure("query") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise LlmFailure("timeout") from None
        if status >= 500:
            raise LlmFailure("upstream")
        try:
            body = json.loads(raw)
            content = body["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise LlmFailure("query") from None
        if not isinstance(parsed, dict):
            raise LlmFailure("query")
        return parsed


class FakeLlm:
    """Test planner and synthesizer. It cannot return graph rows."""

    def __init__(
        self,
        *,
        rollback: str | None = None,
        assignee: str | None = None,
        never_stop: bool = False,
        fail: str | None = None,
    ) -> None:
        self._rollback = rollback
        self._assignee = assignee
        self._never_stop = never_stop
        self._fail = fail

    def plan(
        self,
        question: str,
        evidence: list[Any],
        catalog: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._fail:
            raise LlmFailure(self._fail)
        if self._never_stop:
            return {
                "stop": False,
                "calls": [{"tool": "search_entity", "arguments": {"query": "payment service"}}],
            }
        from app.agent.planner import ScriptedPlanner

        return ScriptedPlanner().plan(question, evidence, catalog)

    def synthesize(self, question: str, evidence: list[Any]) -> Any:
        from app.agent.synthesizer import synthesize

        recommendation, interpretation, uncertainty = synthesize(question, evidence)
        if recommendation is not None and self._rollback is not None:
            recommendation.rollback_candidate = self._rollback
        if recommendation is not None and self._assignee is not None:
            recommendation.assignee_id = self._assignee
        return recommendation, interpretation, uncertainty

    def complete(self, system: str, user: str) -> dict[str, Any]:
        raise LlmFailure("query")
