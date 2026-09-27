"""Closed-loop HTTP load test (aiohttp, multi-process client).

Usage:
  python scripts/loadtest.py --url http://localhost:8000 --duration 30 --procs 4 --conc 32 [--container tram-forecast]

Request mix mimics the dashboard: forecast (30 % of them with correction coefficients)/history/kpi/map/
stop/fleet/routes with random routes,
dates, hours and granularities (so not everything is a cache hit on the first pass).
If --container is given, `docker stats` is sampled during the run (CPU %, RAM).
Prints a markdown table row and writes JSON to docs/loadtest_<name>.json.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing as mp
import random
import statistics
import subprocess
import threading
import time
from datetime import date, timedelta
from pathlib import Path

ROUTES = ["1", "7", "11", "12", "17", "25", "26", "28", "50", "all"]
GEO = ["1", "7", "11", "12"]
STOPS = ["8630", "8605", "3693", "6164", "4173", "2594"]


def rand_day(lo=date(2025, 11, 1), n=61) -> str:
    return (lo + timedelta(days=random.randrange(n))).isoformat()


def make_request() -> str:
    r = random.random()
    route = random.choice(ROUTES)
    if r < 0.30:
        d = rand_day()
        adj = ""
        if random.random() < 0.3:  # dispatcher corrections: level / event / weather what-if
            adj = random.choice([f"&k_level={random.choice([0.9, 0.95, 1.05, 1.1])}",
                                 f"&k_event={route if route != 'all' else 'all'}:{d}:{d}:{random.choice([0, 0.5, 1.2])}",
                                 f"&w_scenario={d}:{random.randint(1, 15)}:{random.randint(-20, 0)}"])
        g = random.choice(["hour", "hour", "day", "month"])
        d2 = d if g == "hour" else (date.fromisoformat(d) + timedelta(days=random.randrange(0, 20))).isoformat()
        d2 = min(d2, "2025-12-31")
        h0 = random.choice([0, 0, 6, 7]); h1 = random.choice([23, 23, 10, 21])
        return f"/api/v1/forecast?route={route}&date_from={d}&date_to={d2}&granularity={g}&hour_from={h0}&hour_to={h1}{adj}"
    if r < 0.45:
        d = rand_day(date(2025, 1, 1), 304)
        return f"/api/v1/history?route={route}&date_from={d}&date_to={d}&granularity=hour"
    if r < 0.65:
        d = rand_day()
        return f"/api/v1/kpi?route={route}&date_from={d}&date_to={d}"
    if r < 0.80:
        return f"/api/v1/map?route={random.choice(GEO)}&date={rand_day()}"
    if r < 0.88:
        d = rand_day()
        return f"/api/v1/forecast/stop?stop_id={random.choice(STOPS)}&date_from={d}&date_to={d}"
    if r < 0.93:
        return f"/api/v1/fleet?route={random.choice(ROUTES[:-1])}&date={rand_day()}"
    if r < 0.95:
        return "/api/v1/routes"
    return f"/api/v1/forecast?route={route}&date_from=2025-13-01"  # expected 400 (validation path)


async def worker(session, base, deadline, lat, codes):
    while time.perf_counter() < deadline:
        path = make_request()
        t0 = time.perf_counter()
        try:
            async with session.get(base + path) as resp:
                await resp.read()
                codes[resp.status] = codes.get(resp.status, 0) + 1
        except Exception:
            codes[-1] = codes.get(-1, 0) + 1
            continue
        lat.append((time.perf_counter() - t0) * 1000)


def proc_main(base, duration, conc, seed, q):
    import aiohttp

    random.seed(seed)

    async def run():
        lat, codes = [], {}
        conn = aiohttp.TCPConnector(limit=conc, force_close=False)
        async with aiohttp.ClientSession(connector=conn) as s:
            # warmup
            for _ in range(20):
                async with s.get(base + make_request()) as r:
                    await r.read()
            deadline = time.perf_counter() + duration
            await asyncio.gather(*(worker(s, base, deadline, lat, codes) for _ in range(conc)))
        return lat, codes

    q.put(asyncio.run(run()))


def sample_docker(container, stop_evt, out):
    while not stop_evt.is_set():
        try:
            line = subprocess.run(
                ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}};{{.MemUsage}}", container],
                capture_output=True, text=True, timeout=10).stdout.strip()
            cpu, mem = line.split(";")
            used = mem.split("/")[0].strip()
            mb = float(used[:-3]) * (1024 if used.endswith("GiB") else 1) if used[-3:] in ("MiB", "GiB") else float("nan")
            out.append((float(cpu.rstrip("%")), mb))
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--conc", type=int, default=32, help="concurrent connections per process")
    ap.add_argument("--container", default="")
    ap.add_argument("--name", default="run")
    a = ap.parse_args()

    stats, stop_evt = [], threading.Event()
    th = None
    if a.container:
        th = threading.Thread(target=sample_docker, args=(a.container, stop_evt, stats), daemon=True)
        th.start()
    q = mp.Queue()
    ps = [mp.Process(target=proc_main, args=(a.url, a.duration, a.conc, i, q)) for i in range(a.procs)]
    t0 = time.perf_counter()
    for p in ps:
        p.start()
    results = [q.get() for _ in ps]
    for p in ps:
        p.join()
    elapsed = time.perf_counter() - t0 - 0.0
    stop_evt.set()
    if th:
        th.join(timeout=15)

    lat = sorted(x for r in results for x in r[0])
    codes: dict = {}
    for _, c in results:
        for k, v in c.items():
            codes[k] = codes.get(k, 0) + v
    n = len(lat)
    pct = lambda p: lat[min(n - 1, int(p / 100 * n))]
    res = {
        "name": a.name, "url": a.url, "duration_s": a.duration, "connections": a.procs * a.conc,
        "requests": n, "rps": round(n / a.duration, 1),
        "p50_ms": round(pct(50), 1), "p95_ms": round(pct(95), 1), "p99_ms": round(pct(99), 1),
        "mean_ms": round(statistics.fmean(lat), 1), "status_codes": {str(k): v for k, v in sorted(codes.items())},
    }
    if stats:
        cpus = [s[0] for s in stats]
        mems = [s[1] for s in stats]
        res.update({"cpu_avg_pct": round(statistics.fmean(cpus), 1), "cpu_max_pct": round(max(cpus), 1),
                    "mem_max_mb": round(max(mems), 1), "samples": len(stats)})
    out = Path(__file__).resolve().parents[1] / "docs" / f"loadtest_{a.name}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"| {a.name} | {res['connections']} | {res['rps']} | {res['p50_ms']} | {res['p95_ms']} | {res['p99_ms']} | "
          f"{res.get('cpu_avg_pct', '—')} / {res.get('cpu_max_pct', '—')} | {res.get('mem_max_mb', '—')} | {res['status_codes']} |")


if __name__ == "__main__":
    main()
