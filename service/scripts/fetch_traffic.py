"""Live road traffic near tram stops: TomTom Traffic Flow Segment Data → data/traffic_live.json.

Usage (from service/):  python scripts/fetch_traffic.py [--max 400] [--zoom 10] [--pause 0.12]

The key is read from the TOMTOM_API_KEY environment variable or from service/.env (gitignored). It is never printed
or written anywhere. For each unique stop of the routes with geometry (data/stops.json) the script asks
  GET https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/{zoom}/json?point={lat},{lon}&unit=KMPH
and stores current speed, free-flow speed, their ratio (1 = free flow), confidence and road closure. The service
serves the file at /api/v1/traffic/live and the dashboard shows a «Пробки TomTom (сейчас)» map layer only when it
exists. It is a live snapshot for the dispatcher, not a model feature: the model uses the historical ЦОДД scores.

Exit codes: 0 = written; 2 = key missing or rejected (HTTP 401/403, e.g. the key is not activated for the Traffic API;
the old file, if any, is left untouched); 3 = network errors for every stop.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[1]
DATA = SERVICE / "data"
URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/{zoom}/json"


def read_key() -> str | None:
    key = os.getenv("TOMTOM_API_KEY")
    env = SERVICE / ".env"
    if not key and env.is_file():
        for line in env.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "TOMTOM_API_KEY":
                key = v.strip().strip('"').strip("'")
    return key or None


def fetch(point: tuple[float, float], key: str, zoom: int, timeout: float = 10.0) -> dict:
    q = urllib.parse.urlencode({"point": f"{point[0]},{point[1]}", "unit": "KMPH", "key": key})
    with urllib.request.urlopen(f"{URL.format(zoom=zoom)}?{q}", timeout=timeout) as r:  # noqa: S310 (fixed https host)
        return json.loads(r.read().decode("utf-8"))["flowSegmentData"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=400, help="max stops to query (free tier: 2 500 requests/day)")
    ap.add_argument("--zoom", type=int, default=10)
    ap.add_argument("--pause", type=float, default=0.12, help="seconds between requests")
    args = ap.parse_args()

    key = read_key()
    if not key:
        print("TomTom: ключ не задан (TOMTOM_API_KEY в окружении или service/.env) — живой слой пробок не строится.")
        return 2
    stops = json.loads((DATA / "stops.json").read_text(encoding="utf-8"))
    seen, todo = set(), []
    for s in stops:
        if s["stop_id"] not in seen:
            seen.add(s["stop_id"])
            todo.append(s)
    todo = todo[: args.max]
    points, errors = [], 0
    for n, s in enumerate(todo):
        try:
            f = fetch((s["lat"], s["lon"]), key, args.zoom)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                print(f"TomTom: ключ не принят (HTTP {e.code}). Проверьте, что ключ активен для Traffic API "
                      f"(developer.tomtom.com → Keys → Traffic Flow). Живой слой не обновлён.")
                return 2
            if e.code == 429:
                print("TomTom: превышен лимит запросов (HTTP 429), остановка.")
                break
            errors += 1
            continue
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            errors += 1
            if errors <= 3:
                print(f"TomTom: ошибка запроса для остановки {s['stop_id']}: {type(e).__name__}")
            continue
        cur, free = f.get("currentSpeed"), f.get("freeFlowSpeed")
        points.append({"stop_id": s["stop_id"], "name": s["name"], "route": s["route"], "lat": s["lat"], "lon": s["lon"],
                       "current_speed": cur, "free_flow_speed": free,
                       "ratio": round(cur / free, 3) if cur and free else None,
                       "confidence": f.get("confidence"), "road_closure": bool(f.get("roadClosure"))})
        if n % 50 == 49:
            print(f"… {n + 1}/{len(todo)}")
        time.sleep(args.pause)
    if not points:
        print(f"TomTom: нет ни одного ответа ({errors} ошибок) — файл не записан.")
        return 3
    out = {"available": True, "source": "TomTom Traffic Flow Segment Data v4",
           "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "note": "снимок скорости на ближайшем к остановке участке дороги; ratio = текущая / свободная скорость",
           "points": points}
    (DATA / "traffic_live.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"TomTom: {len(points)} точек записано в data/traffic_live.json ({errors} ошибок)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
