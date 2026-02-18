"""Lightweight Prometheus-compatible metrics collection."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock


class _Counter:
    def __init__(self) -> None:
        self._value: float = 0
        self._lock = Lock()

    def inc(self, amount: float = 1) -> None:
        with self._lock:
            self._value += amount

    @property
    def value(self) -> float:
        return self._value


class _Gauge:
    def __init__(self) -> None:
        self._value: float = 0
        self._lock = Lock()

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value

    def inc(self, amount: float = 1) -> None:
        with self._lock:
            self._value += amount

    def dec(self, amount: float = 1) -> None:
        with self._lock:
            self._value -= amount

    @property
    def value(self) -> float:
        return self._value


class _Histogram:
    def __init__(self) -> None:
        self._sum: float = 0
        self._count: int = 0
        self._lock = Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._count += 1

    @property
    def count(self) -> int:
        return self._count

    @property
    def avg(self) -> float:
        return self._sum / self._count if self._count else 0


class MetricsRegistry:
    """Simple in-memory metrics store."""

    def __init__(self) -> None:
        self._counters: dict[str, _Counter] = defaultdict(_Counter)
        self._gauges: dict[str, _Gauge] = defaultdict(_Gauge)
        self._histograms: dict[str, _Histogram] = defaultdict(_Histogram)

    def counter(self, name: str) -> _Counter:
        return self._counters[name]

    def gauge(self, name: str) -> _Gauge:
        return self._gauges[name]

    def histogram(self, name: str) -> _Histogram:
        return self._histograms[name]

    def snapshot(self) -> dict:
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges": {k: v.value for k, v in self._gauges.items()},
            "histograms": {
                k: {"count": v.count, "avg": round(v.avg, 4)}
                for k, v in self._histograms.items()
            },
        }


# Singleton registry
metrics = MetricsRegistry()
