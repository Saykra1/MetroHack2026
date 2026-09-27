"""In-memory data store: dense numpy cubes [route, day, hour] for O(1) slicing.

Loaded once per worker at startup (~60k history rows + ~15k forecast rows -> a few MB).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config

SOURCES = ("history", "forecast", "combined")
SOURCE_RU = {"history": "факт", "forecast": "прогноз", "combined": "факт + прогноз"}


@dataclass
class Store:
    routes: list[str]                     # routes with passenger counts (index = cube axis 0)
    route_idx: dict[str, int]
    day0: date
    n_days: int
    cubes: dict[str, np.ndarray]          # source -> float32 [R, D, 24], NaN = no data
    coverage: dict[str, tuple[date, date]]
    route_names: dict[str, str]
    stops: list[dict]                     # stop records (per route & direction)
    stops_by_route: dict[str, list[dict]]
    stop_routes: dict[str, list[tuple[str, float]]]  # stop_id -> [(route, share)]
    explain: dict | None = None           # (route, date) -> list[dict] of 24 rows
    explain_cols: list[str] = field(default_factory=list)
    forecast_path: str = ""
    history_routes: set = field(default_factory=set)
    comp: dict = field(default_factory=dict)      # explain components as cubes: base/special/weather/rules [R,D,24]
    weather_pr: np.ndarray | None = None          # daily precipitation (mm, 06-21 h) by day index
    weather_t: np.ndarray | None = None           # daily mean temperature (C, 06-21 h)
    weather_ref_pr: float = 0.0                   # reference precipitation (Oct 18-31 mean), as in src/adjust.py
    fleet: dict = field(default_factory=dict)
    launch: dict = field(default_factory=dict)    # route -> first forecast date with passengers (new routes)
    traffic_score: np.ndarray | None = None       # ЦОДД daily road-load score 0–10 (no post = 4) by day index
    traffic_norm: np.ndarray | None = None        # 3-week norm (mean of the 21 preceding days)
    traffic_url: dict = field(default_factory=dict)  # date -> permalink of the ЦОДД post
    ml: object = None                             # app.ml.MLData: intervals, anomalies, hybrid, report (optional)

    # ---------- helpers ----------
    def day_index(self, d: date) -> int:
        return (d - self.day0).days

    def day_at(self, i: int) -> date:
        return self.day0 + timedelta(days=i)


def _load_counts(path, value_col: str) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", dtype={"route": str})
    df.columns = [c.strip() for c in df.columns]
    df["route"] = df["route"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.rename(columns={value_col: "value"})[["route", "date", "hour", "value"]]


def load() -> Store:
    hist = _load_counts(config.HISTORY_PATH, "boardings")
    fc = _load_counts(config.FORECAST_PATH, "prediction")
    # A route has data if it has actual history OR a non-zero forecast (e.g. route 5, launched 2025-12-16).
    # All-zero forecast rows for routes without history are meaningless and are dropped.
    hist_routes = set(hist.route)
    fc_sum = fc.groupby("route").value.sum()
    fc_live = set(fc_sum[fc_sum > 0].index)
    fc = fc[fc.route.isin(hist_routes | fc_live)]
    routes = sorted(hist_routes | fc_live, key=lambda r: (len(r), r))
    launch = {r: fc[(fc.route == r) & (fc.value > 0)].date.min() for r in fc_live - hist_routes}
    ridx = {r: i for i, r in enumerate(routes)}
    day0 = min(hist.date.min(), fc.date.min())
    day1 = max(hist.date.max(), fc.date.max())
    n_days = (day1 - day0).days + 1

    def cube(df: pd.DataFrame) -> np.ndarray:
        a = np.full((len(routes), n_days, 24), np.nan, dtype=np.float32)
        ri = df.route.map(ridx).to_numpy()
        di = np.array([(d - day0).days for d in df.date])
        a[ri, di, df.hour.to_numpy()] = df.value.to_numpy(dtype=np.float32)
        return a

    h, f = cube(hist), cube(fc)
    comb = np.where(np.isnan(h), f, h)
    cubes = {"history": h, "forecast": f, "combined": comb}
    coverage = {
        "history": (hist.date.min(), hist.date.max()),
        "forecast": (fc.date.min(), fc.date.max()),
        "combined": (day0, day1),
    }

    names = {}
    if config.ROUTE_NAMES_PATH.exists():
        names = json.loads(config.ROUTE_NAMES_PATH.read_text(encoding="utf-8"))

    stops_all = json.loads(config.STOPS_PATH.read_text(encoding="utf-8")) if config.STOPS_PATH.exists() else []
    tracked = set(config.TRACKED_ROUTES) | set(routes)
    stops = [s for s in stops_all if s["route"] in tracked]
    by_route: dict[str, list[dict]] = {}
    for s in stops:
        by_route.setdefault(s["route"], []).append(s)
    stop_routes: dict[str, list[tuple[str, float]]] = {}
    for r, lst in by_route.items():
        tot = sum(s["weight"] for s in lst) or 1.0
        for s in lst:
            s["share"] = s["weight"] / tot
            stop_routes.setdefault(s["stop_id"], []).append((r, s["share"]))

    st = Store(routes, ridx, day0, n_days, cubes, coverage, names, stops, by_route, stop_routes,
               forecast_path=str(config.FORECAST_PATH), history_routes=hist_routes, launch=launch)
    _load_explain(st)
    _load_weather(st)
    _load_traffic(st)
    fleet_p = config.DATA_DIR / "fleet.json"
    if fleet_p.is_file():
        st.fleet = json.loads(fleet_p.read_text(encoding="utf-8"))
    from . import ml
    st.ml = ml.load(st)
    return st


def _load_weather(st: Store) -> None:
    p = config.DATA_DIR / "weather_daily.csv"
    if not p.is_file():
        return
    w = pd.read_csv(p, sep=";")
    w["date"] = pd.to_datetime(w["date"]).dt.date
    pr = np.full(st.n_days, np.nan)
    t = np.full(st.n_days, np.nan)
    for rec in w.itertuples():
        i = st.day_index(rec.date)
        if 0 <= i < st.n_days:
            pr[i], t[i] = rec.precip_mm, rec.temp_c
    st.weather_pr, st.weather_t = pr, t
    a, b = st.day_index(date(2025, 10, 18)), st.day_index(date(2025, 10, 31))
    st.weather_ref_pr = float(np.nanmean(pr[a:b + 1])) if b >= 0 else 0.0


def _load_traffic(st: Store) -> None:
    p = config.DATA_DIR / "traffic_daily.csv"
    if not p.is_file():
        return
    try:
        t = pd.read_csv(p, sep=";")
        sc = np.full(st.n_days, 4.0)
        nm = np.full(st.n_days, 4.0)
        for rec in t.itertuples():
            i = st.day_index(date.fromisoformat(rec.date))
            if 0 <= i < st.n_days:
                sc[i], nm[i] = rec.score, rec.norm
                if isinstance(rec.source_url, str) and rec.source_url:
                    st.traffic_url[rec.date] = rec.source_url
        st.traffic_score, st.traffic_norm = sc, nm
    except Exception:  # optional
        st.traffic_score = st.traffic_norm = None


def _load_explain(st: Store) -> None:
    p = config.EXPLAIN_PATH
    if not p.is_file():
        return
    try:
        df = pd.read_csv(p, sep=";", dtype={"route": str})
        need = {"route", "date", "hour", "base"}
        if not need.issubset(df.columns):
            return
        mult_cols = [c for c in df.columns if c.endswith("_mult")]
        df["route"] = df["route"].astype(str)
        out: dict = {}
        for (r, d), g in df.groupby(["route", "date"]):
            rows = []
            for rec in g.sort_values("hour").itertuples(index=False):
                rec = rec._asdict()
                row = {"hour": int(rec["hour"]), "base": float(rec["base"])}
                pred = row["base"]
                for c in mult_cols:
                    row[c] = float(rec[c])
                    pred *= row[c]
                row["prediction_recomputed"] = round(pred, 2)
                if "prediction" in rec:
                    row["prediction"] = float(rec["prediction"])
                note = rec.get("note")
                if isinstance(note, str) and note.strip():
                    row["note"] = note.strip()
                rows.append(row)
            out[(r, str(d))] = rows
        st.explain, st.explain_cols = out, mult_cols
        df = df[df.route.isin(st.route_idx)]
        ri = df.route.map(st.route_idx).to_numpy()
        di = np.array([st.day_index(d) for d in pd.to_datetime(df["date"]).dt.date])
        hi = df.hour.to_numpy()
        for col, key in (("base", "base"), ("special_mult", "special"), ("weather_mult", "weather"), ("rules_mult", "rules")):
            if col in df.columns:
                a = np.full((len(st.routes), st.n_days, 24), np.nan, dtype=np.float32)
                a[ri, di, hi] = df[col].to_numpy(dtype=np.float32)
                st.comp[key] = a
    except Exception:  # explain file is optional: never break startup
        st.explain = None


STORE: Store | None = None


def get() -> Store:
    global STORE
    if STORE is None:
        STORE = load()
    return STORE
