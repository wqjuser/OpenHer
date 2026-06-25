from __future__ import annotations

import time
from typing import Optional


class _CircuitBreaker:
    """Simple consecutive-failure circuit breaker."""

    def __init__(self, threshold: int = 5, recovery_sec: float = 60.0):
        self._threshold = threshold
        self._recovery_sec = recovery_sec
        self._failures = 0
        self._open_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        if self._open_at is None:
            return False
        if time.monotonic() - self._open_at > self._recovery_sec:
            self._open_at = None
            self._failures = 0
            print("  [evermemos] 🔄 circuit breaker reset (recovery timeout)")
            return False
        return True

    def record_success(self):
        self._failures = 0

    def record_failure(self):
        self._failures += 1
        if self._failures >= self._threshold and self._open_at is None:
            self._open_at = time.monotonic()
            print(f"  [evermemos] ⚡ circuit OPEN after {self._failures} failures")


class _NoOpBreaker:
    """No-op breaker for when circuit_breaker_enabled=false."""

    is_open = False

    def record_success(self):
        pass

    def record_failure(self):
        pass
