"""Prometheus metrics collection."""
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class Counter:
    """Simple counter metric."""
    name: str
    description: str
    _value: int = 0
    
    def inc(self, amount: int = 1):
        """Increment counter."""
        self._value += amount
    
    @property
    def value(self) -> int:
        return self._value
    
    def to_prometheus(self) -> str:
        return f"# HELP {self.name} {self.description}\n# TYPE {self.name} counter\n{self.name} {self._value}"


@dataclass
class Gauge:
    """Simple gauge metric."""
    name: str
    description: str
    _value: float = 0.0
    
    def set(self, value: float):
        """Set gauge value."""
        self._value = value
    
    def inc(self, amount: float = 1):
        """Increment gauge."""
        self._value += amount
    
    def dec(self, amount: float = 1):
        """Decrement gauge."""
        self._value -= amount
    
    @property
    def value(self) -> float:
        return self._value
    
    def to_prometheus(self) -> str:
        return f"# HELP {self.name} {self.description}\n# TYPE {self.name} gauge\n{self.name} {self._value}"


@dataclass
class Histogram:
    """Simple histogram metric."""
    name: str
    description: str
    buckets: list = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10])
    _values: list = field(default_factory=list)
    
    def observe(self, value: float):
        """Observe a value."""
        self._values.append(value)
    
    def to_prometheus(self) -> str:
        lines = [
            f"# HELP {self.name} {self.description}",
            f"# TYPE {self.name} histogram"
        ]
        
        # Calculate bucket counts
        total = len(self._values)
        for bucket in self.buckets:
            count = sum(1 for v in self._values if v <= bucket)
            lines.append(f'{self.name}_bucket{{le="{bucket}"}} {count}')
        
        # +Inf bucket
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {total}')
        lines.append(f"{self.name}_count {total}")
        
        if self._values:
            total_sum = sum(self._values)
            lines.append(f"{self.name}_sum {total_sum}")
        else:
            lines.append(f"{self.name}_sum 0")
        
        return "\n".join(lines)


class MetricsCollector:
    """Centralized metrics collection."""
    
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._initialize_default_metrics()
    
    def _initialize_default_metrics(self):
        """Initialize default metrics."""
        # Counters
        self._counters['stock_checks_total'] = Counter(
            'stock_checks_total',
            'Total number of stock checks performed'
        )
        self._counters['alerts_sent_total'] = Counter(
            'alerts_sent_total',
            'Total number of alerts sent'
        )
        self._counters['alerts_failed_total'] = Counter(
            'alerts_failed_total',
            'Total number of failed alerts'
        )
        self._counters['products_discovered_total'] = Counter(
            'products_discovered_total',
            'Total number of products discovered'
        )
        self._counters['scraper_requests_total'] = Counter(
            'scraper_requests_total',
            'Total number of scraper requests',
        )
        self._counters['scraper_errors_total'] = Counter(
            'scraper_errors_total',
            'Total number of scraper errors',
        )
        
        # Gauges
        self._gauges['products_in_stock'] = Gauge(
            'products_in_stock',
            'Current number of products in stock'
        )
        self._gauges['products_tracked'] = Gauge(
            'products_tracked',
            'Current number of tracked products'
        )
        self._gauges['discord_latency_ms'] = Gauge(
            'discord_latency_ms',
            'Discord gateway latency in milliseconds'
        )
        self._gauges['scheduler_running'] = Gauge(
            'scheduler_running',
            'Whether the scheduler is running (1) or not (0)'
        )
        
        # Histograms
        self._histograms['scraper_request_duration_seconds'] = Histogram(
            'scraper_request_duration_seconds',
            'Scraper request duration in seconds'
        )
        self._histograms['stock_check_duration_seconds'] = Histogram(
            'stock_check_duration_seconds',
            'Stock check duration in seconds'
        )
        self._histograms['alert_send_duration_seconds'] = Histogram(
            'alert_send_duration_seconds',
            'Alert send duration in seconds'
        )
    
    def counter(self, name: str) -> Counter:
        """Get a counter metric."""
        if name not in self._counters:
            self._counters[name] = Counter(name, f"Counter for {name}")
        return self._counters[name]
    
    def gauge(self, name: str) -> Gauge:
        """Get a gauge metric."""
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, f"Gauge for {name}")
        return self._gauges[name]
    
    def histogram(self, name: str) -> Histogram:
        """Get a histogram metric."""
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, f"Histogram for {name}")
        return self._histograms[name]
    
    @contextmanager
    def time_histogram(self, name: str):
        """Context manager to time operations.
        
        Usage:
            with metrics.time_histogram('my_operation'):
                do_something()
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.histogram(name).observe(duration)
    
    def to_prometheus(self) -> str:
        """Export all metrics in Prometheus format."""
        lines = []
        
        for counter in self._counters.values():
            lines.append(counter.to_prometheus())
            lines.append("")
        
        for gauge in self._gauges.values():
            lines.append(gauge.to_prometheus())
            lines.append("")
        
        for histogram in self._histograms.values():
            lines.append(histogram.to_prometheus())
            lines.append("")
        
        return "\n".join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        return {
            'counters': {name: counter.value for name, counter in self._counters.items()},
            'gauges': {name: gauge.value for name, gauge in self._gauges.items()},
            'histograms': {
                name: {
                    'count': len(hist._values),
                    'sum': sum(hist._values) if hist._values else 0
                }
                for name, hist in self._histograms.items()
            }
        }


# Global metrics instance
metrics = MetricsCollector()
