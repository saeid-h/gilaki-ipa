from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import time

from .settings import settings

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def allow(ip: str) -> bool:
    now = time()
    window = settings.rate_limit_window_sec
    cap = settings.rate_limit_max
    with _lock:
        bucket = _hits[ip]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= cap:
            return False
        bucket.append(now)
        return True
