"""Sliding-window in-memory rate limiter keyed by a hashed client id."""

from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        q = self._hits[key]
        while q and q[0] <= now - self.window_s:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        if len(self._hits) > 10_000:  # bound memory
            for k in [k for k, v in self._hits.items() if not v][:5000]:
                del self._hits[k]
        return True
