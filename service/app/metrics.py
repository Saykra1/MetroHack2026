"""Tiny per-process request counters (pure ASGI middleware, near-zero overhead)."""
from __future__ import annotations

import os
import time
from collections import defaultdict

STARTED = time.time()
COUNTS: dict[str, int] = defaultdict(int)
STATUS: dict[int, int] = defaultdict(int)
LAT_SUM: dict[str, float] = defaultdict(float)
LAT_BUCKETS = (5, 10, 25, 50, 100, 250, 500, 1000)
HIST: dict[str, int] = defaultdict(int)


class MetricsMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        t0 = time.perf_counter()
        status_box = [500]

        async def _send(msg):
            if msg["type"] == "http.response.start":
                status_box[0] = msg["status"]
            await send(msg)

        try:
            await self.app(scope, receive, _send)
        finally:
            path = scope.get("path", "")
            if path.startswith("/api/"):
                ms = (time.perf_counter() - t0) * 1000
                COUNTS[path] += 1
                STATUS[status_box[0]] += 1
                LAT_SUM[path] += ms
                for b in LAT_BUCKETS:
                    if ms <= b:
                        HIST[f"le_{b}ms"] += 1
                        break
                else:
                    HIST["gt_1000ms"] += 1


def snapshot() -> dict:
    total = sum(COUNTS.values())
    return {
        "worker_pid": os.getpid(),
        "uptime_s": round(time.time() - STARTED, 1),
        "requests_total": total,
        "by_status": {str(k): v for k, v in sorted(STATUS.items())},
        "by_path": {p: {"count": c, "avg_ms": round(LAT_SUM[p] / c, 3)} for p, c in sorted(COUNTS.items())},
        "latency_histogram": dict(HIST),
        "note": "Счётчики ведутся отдельно в каждом worker-процессе uvicorn.",
    }
