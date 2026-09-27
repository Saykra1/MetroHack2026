"""Build the service data bundle (service/data/) from the hackathon workspace.

Run from anywhere:  python service/scripts/prepare_data.py [--forecast PATH] [--explain PATH]
(defaults: ../submissions/final_candidate.csv and ../submissions/final_candidate_explain.csv)

Outputs (all UTF-8):
  data/history.csv   route;date;hour;boardings   (Jan-Oct 2025, train+test labels)
  data/forecast.csv  route;date;hour;prediction  (Nov-Dec 2025)
  data/explain.csv   optional decomposition (copied if given/exists)
  data/stops.json    stops with coordinates per route/direction (routes with geometry only)
  data/routes.json   route names from the GTFS_ROUTES sheet
  data/intervals.csv, anomalies.csv, hybrid_nov_dec.csv, hybrid_folds.csv, model_report.md
                     optional ML layer copied from ../experiments/ml (--ml-dir); missing files are skipped
"""
from __future__ import annotations

import argparse
import glob
import json
import shutil
from pathlib import Path

import pandas as pd

SERVICE = Path(__file__).resolve().parents[1]
ROOT = SERVICE.parent
OUT = SERVICE / "data"

# Stops that are transfer hubs get a higher share of boardings (see README "stop estimate").
HUB_WORDS = ("метро", "мцд", "мцк", "вокзал", "станция", "платформа")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forecast", default=str(ROOT / "submissions" / "final_candidate.csv"))
    ap.add_argument("--explain", default=str(ROOT / "submissions" / "final_candidate_explain.csv"))
    ap.add_argument("--ml-dir", default=str(ROOT / "experiments" / "ml"))
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)

    hist = pd.concat(
        [pd.read_csv(ROOT / "labels" / f, sep=";") for f in ("labels_day_train.csv", "labels_day_test.csv")]
    ).drop_duplicates(["route", "date", "hour"]).sort_values(["route", "date", "hour"])
    hist.to_csv(OUT / "history.csv", sep=";", index=False)
    print("history", hist.shape, hist.date.min(), hist.date.max())

    shutil.copyfile(args.forecast, OUT / "forecast.csv")
    print("forecast <-", args.forecast)
    if args.explain and Path(args.explain).exists():
        shutil.copyfile(args.explain, OUT / "explain.csv")
        print("explain <-", args.explain)
    elif (OUT / "explain.csv").exists():
        (OUT / "explain.csv").unlink()  # stale decomposition must not describe another forecast
        print("explain: none")

    xlsx = [p for p in glob.glob(str(ROOT / "spravochniki" / "*.xlsx")) if "10_" in Path(p).name][0]
    sheets = pd.read_excel(xlsx, sheet_name=None)
    names = list(sheets)

    routes = sheets[names[0]].iloc[1:, [2, 3]]
    routes.columns = ["route", "name"]
    route_names = {str(int(r.route)): str(r.name) for r in routes.itertuples() if pd.notna(r.route)}
    (OUT / "routes.json").write_text(json.dumps(route_names, ensure_ascii=False, indent=1), encoding="utf-8")

    # Canonical route->stop binding from the data pipeline if present, else the GTFS sheet.
    canon = ROOT / "experiments" / "route_stops.csv"
    if canon.exists():
        st = pd.read_csv(canon, sep=";").rename(columns={"route": "route_short_name"})
        print("stops <-", canon)
    else:
        st = sheets[[n for n in names if "координат" in n][0]]
        st["weight"] = 1.0
    stops = []
    for (route, direction), g in st.groupby(["route_short_name", "direction_id"]):
        g = g.sort_values("stop_sequence")
        n = len(g)
        for i, r in enumerate(g.itertuples()):
            hub = any(w in str(r.stop_name).lower() for w in HUB_WORDS)
            # Weight = pipeline base weight x heuristic: transfer hubs x2; last stop of a direction x0.1
            # (passengers alight there, almost nobody boards). Shares are renormalised per route at load.
            w = float(r.weight) * (0.1 if i == n - 1 else (2.0 if hub else 1.0))
            stops.append(
                {
                    "route": str(int(route)),
                    "direction": int(direction),
                    "seq": int(r.stop_sequence),
                    "stop_id": str(int(r.stop_id)),
                    "name": str(r.stop_name),
                    "lat": round(float(r.stop_lat), 6),
                    "lon": round(float(r.stop_lon), 6),
                    "hub": hub,
                    "weight": w,
                }
            )
    ml_files = copy_ml(Path(args.ml_dir))
    build_pipeline_report()
    build_weather()
    build_traffic()
    build_fleet(sheets, stops)
    from datetime import datetime
    meta = {"forecast_source": Path(args.forecast).name,
            "explain_source": Path(args.explain).name if args.explain and Path(args.explain).exists() else None,
            "ml_files": ml_files,
            "built_at": datetime.now().isoformat(timespec="seconds")}
    (OUT / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "stops.json").write_text(json.dumps(stops, ensure_ascii=False), encoding="utf-8")
    print("stops", len(stops), "routes with geometry:", sorted({s["route"] for s in stops}, key=int))


ML_FILES = {"intervals.csv": "intervals.csv", "anomalies.csv": "anomalies.csv",
            "hybrid_nov_dec.csv": "hybrid_nov_dec.csv", "hybrid_folds.csv": "hybrid_folds.csv",
            "REPORT.md": "model_report.md"}


def copy_ml(src: Path) -> list[str]:
    """Copy the ML layer (prediction intervals, anomaly labels, hybrid forecast, report). Every file is optional;
    a stale copy is removed when the source is gone so the bundle never mixes outputs of different ML runs."""
    copied = []
    for name, dst in ML_FILES.items():
        f = src / name
        if f.is_file():
            shutil.copyfile(f, OUT / dst)
            copied.append(name)
        elif (OUT / dst).exists():
            (OUT / dst).unlink()
    print("ml <-", src, copied or "none")
    return copied


def build_weather() -> None:
    """Daily weather for the correction panel: precipitation sum and mean temperature over 06-21 h
    (same aggregation as src/adjust.py::weather, so default coefficients reproduce the model's weather_mult)."""
    src = ROOT / "research" / "weather_moscow_2025.csv"
    if not src.exists():
        print("weather: none")
        return
    w = pd.read_csv(src)
    w["ts"] = pd.to_datetime(w.datetime)
    w = w[(w.ts.dt.hour >= 6) & (w.ts.dt.hour <= 21)]
    d = w.groupby(w.ts.dt.date).agg(precip_mm=("precipitation", "sum"), temp_c=("temperature_2m", "mean"),
                                    snow_cm=("snowfall", "sum")).round(3)
    d.index.name = "date"
    d.to_csv(OUT / "weather_daily.csv", sep=";")
    print("weather days:", len(d))


def build_traffic() -> None:
    """Daily ЦОДД road-load score (0–10, «Дептранс. Оперативно»), its 3-week norm and a permalink as evidence.
    Days without a post are «normal» (score 4, see research/traffic_source.md); norm = mean of the 21 preceding days."""
    src = ROOT / "research" / "traffic_moscow_2025_daily.csv"
    if not src.exists():
        print("traffic: none")
        return
    d = pd.read_csv(src)
    d["score"] = d.max_score.fillna(4.0)
    d["norm"] = d.score.shift(1).rolling(21, min_periods=7).mean().fillna(4.0).round(3)
    posts = ROOT / "research" / "traffic_moscow_2025.csv"
    if posts.exists():
        p = pd.read_csv(posts).sort_values(["date", "score"], ascending=[True, False]).drop_duplicates("date")
        d = d.merge(p[["date", "source_url"]], on="date", how="left")
    else:
        d["source_url"] = None
    out = d[["date", "score", "norm", "reported", "n_posts", "source_url"]]
    out.to_csv(OUT / "traffic_daily.csv", sep=";", index=False)
    print("traffic days:", len(out), "reported:", int(out.reported.sum()))


def build_fleet(sheets: dict, stops: list[dict]) -> None:
    """Rolling-stock assumptions: vehicle class per route (Наряд sheet), operating speed (Расписание sample),
    route length from stop geometry (haversine along direction 0)."""
    import math

    def hav(a, b):
        la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
        h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
        return 2 * 6371 * math.asin(math.sqrt(h))

    out: dict = {"routes": {}}
    n = sheets.get("Наряд")
    if n is not None:
        n.columns = n.iloc[0]
        n = n.iloc[1:]
        for r, g in n.groupby("route_short_name"):
            out["routes"].setdefault(str(int(r)), {}).update(
                {"vehicle_model": str(g.model.mode().iloc[0]), "vehicle_class": str(g.vehicle_capacity.mode().iloc[0])})
    sch = sheets.get("Расписание")
    if sch is not None:
        sch.columns = sch.iloc[0]
        sch = sch.iloc[1:]
        t = pd.to_datetime(sch.arrival_time.astype(str), format="%H:%M", errors="coerce")
        dist = pd.to_numeric(sch.shape_dist_traveled, errors="coerce")
        mins = (t.max() - t.min()).total_seconds() / 60
        if mins > 0:
            out["schedule_speed_kmh"] = round(float(dist.max() - dist.min()) / (mins / 60), 1)
            out["schedule_sample"] = f"маршрут {sch.route_short_name.iloc[0]}: {dist.max() - dist.min():.2f} км за {mins:.0f} мин"
    by = {}
    for s in stops:
        if s["direction"] == 0:
            by.setdefault(s["route"], []).append(s)
    for r, lst in by.items():
        lst.sort(key=lambda s: s["seq"])
        km = sum(hav((a["lat"], a["lon"]), (b["lat"], b["lon"])) for a, b in zip(lst, lst[1:]))
        out["routes"].setdefault(r, {})["length_km"] = round(km * 1.15, 2)  # x1.15: track is longer than straight segments
    (OUT / "fleet.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("fleet:", {k: v for k, v in out.items() if k != "routes"}, len(out["routes"]), "routes")


def build_pipeline_report() -> None:
    """Merge experiments/pipeline_report.json + ingest_report.md into data/pipeline_report.json."""
    import re

    rep: dict = {}
    pj = ROOT / "experiments" / "pipeline_report.json"
    if pj.exists():
        rep.update(json.loads(pj.read_text(encoding="utf-8")))
    md = ROOT / "experiments" / "ingest_report.md"
    if md.exists():
        t = md.read_text(encoding="utf-8")
        num = lambda pat: (lambda m: int(m.group(1).replace(",", "")) if m else None)(re.search(pat, t))
        rep["ingest"] = {
            "raw_rows": num(r"raw rows:\s*([\d,]+)"),
            "clean_rows": num(r"clean successful validations:\s*([\d,]+)"),
            "label_cells": num(r"labels cells:\s*([\d,]+)"),
            "label_cells_exact_match": num(r"exact match:\s*([\d,]+)"),
            "runtime_s": num(r"runtime:\s*([\d,]+)\s*s"),
        }
        m = re.search(r"\(([\d.]+)%\)", t)
        rep["ingest"]["label_match_pct"] = float(m.group(1)) if m else None
    if rep:
        (OUT / "pipeline_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print("pipeline report:", rep.get("ingest"))


if __name__ == "__main__":
    main()
