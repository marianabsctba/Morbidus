"""Cache e circuit breaker por provedor, para não martelar API paga nem fora do ar.

O cache é por processo. Com várias réplicas, a troca natural é Redis.
"""

import time


class TTLCache:
    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._data.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.monotonic():
            del self._data[key]
            return None
        return value

    def set(self, key: str, value: object) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)


class CircuitBreaker:
    def __init__(self, max_failures: int, reset_seconds: int) -> None:
        self._max = max_failures
        self._reset = reset_seconds
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self._reset:
            # Meio aberto: deixa uma tentativa passar.
            self._opened_at = None
            self._failures = self._max - 1
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._max:
            self._opened_at = time.monotonic()
