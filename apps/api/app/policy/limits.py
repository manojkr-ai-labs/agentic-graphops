"""Depth, size, time, and iteration caps live in settings. This is the start rate."""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """30 investigation starts per tenant per minute, in process memory."""

    def __init__(self, limit: int = 30, window_s: float = 60.0) -> None:
        self._limit = limit
        self._window_s = window_s
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, tenant: str) -> bool:
        now = time.monotonic()
        recent = [stamp for stamp in self._hits[tenant] if now - stamp < self._window_s]
        if len(recent) >= self._limit:
            self._hits[tenant] = recent
            return False
        recent.append(now)
        self._hits[tenant] = recent
        return True
