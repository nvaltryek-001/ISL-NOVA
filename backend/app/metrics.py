"""Minimal Prometheus text-format metrics (no extra dependency).

Exposed at GET /metrics. Access: requests from localhost, or with
`Authorization: Bearer $METRICS_TOKEN` when METRICS_TOKEN is set.
"""

from __future__ import annotations

import threading
from collections import Counter

BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.requests: Counter = Counter()          # (method, route_group, status_class)
        self.latency = [0] * (len(BUCKETS) + 1)
        self.latency_sum = 0.0
        self.latency_count = 0
        self.predictions: Counter = Counter()       # state

    @staticmethod
    def group(path: str) -> str:
        parts = path.split("/")
        return "/".join(parts[:4]) if path.startswith("/api/v1/") else "other"

    def observe(self, method: str, path: str, status: int, seconds: float) -> None:
        with self.lock:
            self.requests[(method, self.group(path), f"{status // 100}xx")] += 1
            self.latency_sum += seconds
            self.latency_count += 1
            for i, b in enumerate(BUCKETS):
                if seconds <= b:
                    self.latency[i] += 1
            self.latency[-1] += 1

    def prediction(self, state: str) -> None:
        with self.lock:
            self.predictions[state] += 1

    def render(self, gauges: dict[str, float]) -> str:
        out = ["# HELP isl_nova_http_requests_total HTTP API requests", "# TYPE isl_nova_http_requests_total counter"]
        with self.lock:
            for (m, g, s), n in sorted(self.requests.items()):
                out.append(f'isl_nova_http_requests_total{{method="{m}",route="{g}",status="{s}"}} {n}')
            out += ["# HELP isl_nova_http_request_seconds API latency", "# TYPE isl_nova_http_request_seconds histogram"]
            for b, n in zip(BUCKETS, self.latency[:-1], strict=True):
                out.append(f'isl_nova_http_request_seconds_bucket{{le="{b}"}} {n}')
            out.append(f'isl_nova_http_request_seconds_bucket{{le="+Inf"}} {self.latency[-1]}')
            out.append(f"isl_nova_http_request_seconds_sum {self.latency_sum:.6f}")
            out.append(f"isl_nova_http_request_seconds_count {self.latency_count}")
            out += ["# HELP isl_nova_predictions_total Recognition answers by state", "# TYPE isl_nova_predictions_total counter"]
            for st, n in sorted(self.predictions.items()):
                out.append(f'isl_nova_predictions_total{{state="{st}"}} {n}')
        for name, v in gauges.items():
            out += [f"# TYPE {name} gauge", f"{name} {v}"]
        return "\n".join(out) + "\n"


METRICS = Metrics()
