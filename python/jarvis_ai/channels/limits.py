"""Small in-process limiters. One API process serializes a Telegram chat."""

import time


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        moment = time.time() if now is None else now
        recent = [stamp for stamp in self._hits.get(key, []) if moment - stamp < self._window]
        if len(recent) >= self._limit:
            self._hits[key] = recent
            return False
        recent.append(moment)
        self._hits[key] = recent
        return True
