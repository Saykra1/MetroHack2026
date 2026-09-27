"""Query logic: validation + aggregation over the in-memory cubes. Pure functions returning dicts."""
from __future__ import annotations

import calendar
import math
import warnings
from datetime import date

import numpy as np

from . import adjust
from .adjust import NO_ADJ, Adj
from .errors import ApiError
from .store import SOURCE_RU, Store

MONTHS_RU = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август",
             "сентябрь", "октябрь", "ноябрь", "декабрь"]
UNIT = "пассажиров (входы/валидации)"


# ---------------- validation ----------------
def parse_date(value: str | None, name: str) -> date | None:
    if value is None or value == "":
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(400, "invalid_date", f"Неверный формат даты «{name}»: «{value}». Ожидается ГГГГ-ММ-ДД, например 2025-11-15")


def resolve_routes(st: Store, route: str | None, *, allow_all: bool = True, source: str | None = None) -> list[str]:
    r = (route or "all").strip()
    if r.lower() in ("all", "все", "*"):
        if not allow_all:
            raise ApiError(400, "route_required", "Укажите конкретный маршрут в параметре «route»")
        return list(st.routes) if source != "history" else [x for x in st.routes if x in st.history_routes]
    parts = [p.strip() for p in r.split(",") if p.strip()]
    for p in parts:
        if source == "history" and p in st.route_idx and p not in st.history_routes:
            since = st.launch.get(p)
            raise ApiError(404, "no_history_for_route",
                           f"Для маршрута {p} нет фактических данных" + (f": маршрут запускается {since:%d.%m.%Y}" if since else ""))
        if p not in st.route_idx:
            if p in st.stops_by_route:
                raise ApiError(404, "no_data_for_route",
                               f"Для маршрута {p} нет данных о пассажиропотоке (доступна только геометрия остановок)")
            raise ApiError(404, "route_not_found",
                           f"Маршрут «{p}» не найден. Доступные маршруты: {', '.join(st.routes)}")
    return parts


def resolve_period(st: Store, source: str, d_from: str | None, d_to: str | None,
                   h_from: int, h_to: int) -> tuple[date, date, int, int]:
    lo, hi = st.coverage[source]
    a = parse_date(d_from, "date_from") or lo
    b = parse_date(d_to, "date_to") or (a if d_from and not d_to else hi)
    if b < a:
        raise ApiError(400, "invalid_period", f"Дата окончания ({b}) раньше даты начала ({a})")
    if a < lo or b > hi:
        raise ApiError(400, "out_of_range",
                       f"Данные «{SOURCE_RU[source]}» доступны только с {lo} по {hi}; запрошено {a} — {b}",
                       {"available_from": str(lo), "available_to": str(hi)})
    if h_to < h_from:
        raise ApiError(400, "invalid_hours", f"«hour_to» ({h_to}) меньше «hour_from» ({h_from})")
    return a, b, h_from, h_to


# ---------------- aggregation ----------------
def _nansum(a: np.ndarray, axis) -> np.ndarray:
    allnan = np.all(np.isnan(a), axis=axis)
    s = np.nansum(a, axis=axis)
    return np.where(allnan, np.nan, s)


def _cube_slice(st: Store, source: str, routes: list[str], a: date, b: date, h0: int, h1: int,
                weights: list[float] | None = None, adj: Adj = NO_ADJ) -> np.ndarray:
    """Return [days, hours] aggregated over routes (optionally weighted: stop shares; optionally corrected)."""
    ri = [st.route_idx[r] for r in routes]
    i0, i1 = st.day_index(a), st.day_index(b)
    sub = _cube(st, source, adj)[ri, i0:i1 + 1, h0:h1 + 1]
    if adj.active and source != "history":
        sub = sub * adjust.factor(st, adj, routes, i0, i1, h0, h1)
    if weights is not None:
        sub = sub * np.asarray(weights, dtype=np.float32)[:, None, None]
    return _nansum(sub, 0) if len(ri) > 1 else sub[0]


def _cube(st: Store, source: str, adj: Adj) -> np.ndarray:
    """Cube of the selected forecast model (v08 or hybrid); actuals are the same for every model."""
    if adj.model != "v08" and source != "history":
        return st.cubes[f"{source}_{adj.model}"]
    return st.cubes[source]


def _band(st: Store, source: str, routes: list[str], a: date, b: date, h0: int, h1: int,
          weights: list[float] | None = None, adj: Adj = NO_ADJ) -> tuple[np.ndarray, np.ndarray] | None:
    """80 % interval (p10, p90) [days, hours] around the shown point forecast: value × p10/p50 and value × p90/p50
    per cell; summed over routes/hours/days assuming fully correlated errors (quantiles add up). NaN on actual days."""
    ml = st.ml
    if source == "history" or ml is None or not ml.intervals:
        return None
    ri = [st.route_idx[r] for r in routes]
    i0, i1 = st.day_index(a), st.day_index(b)
    sub = _cube(st, source, adj)[ri, i0:i1 + 1, h0:h1 + 1]
    if adj.active:
        sub = sub * adjust.factor(st, adj, routes, i0, i1, h0, h1)
    if weights is not None:
        sub = sub * np.asarray(weights, dtype=np.float32)[:, None, None]
    lo = sub * ml.rel_lo[ri, i0:i1 + 1, h0:h1 + 1]
    hi = sub * ml.rel_hi[ri, i0:i1 + 1, h0:h1 + 1]
    if len(ri) > 1:
        return _nansum(lo, 0), _nansum(hi, 0)
    return lo[0], hi[0]


INTERVAL_INFO = {"level": 0.8, "label": "80 % интервал (P10–P90)",
                 "method": "Квантили P10/P90 ML-модели в относительном виде (P10/P50, P90/P50) применены к показанному "
                           "прогнозу; часы одних суток и маршруты суммируются как полностью коррелированные, "
                           "сутки внутри месяца — как независимые (нормальное приближение)"}


def _month_band(st: Store, m: np.ndarray, band, a: date, h0: int) -> tuple[list[dict], list[dict]]:
    """Monthly totals: daily deviations from the point forecast are combined as independent (root of sum of squares)."""
    v, lo, hi = (_nansum(x, 1) for x in (m, band[0], band[1]))
    days = [st.day_at(st.day_index(a) + i) for i in range(len(v))]
    acc: dict[str, list] = {}
    for d, vv, ll, hh in zip(days, v, lo, hi):
        rec = acc.setdefault(f"{d.year}-{d.month:02d}", [0.0, 0.0, 0.0, False])
        if not np.isnan(ll):
            rec[0] += float(vv); rec[1] += float(vv - ll) ** 2; rec[2] += float(hh - vv) ** 2; rec[3] = True
    out_lo = [{"value": round(max(0.0, x[0] - x[1] ** 0.5), 1) if x[3] else None} for x in acc.values()]
    out_hi = [{"value": round(x[0] + x[2] ** 0.5, 1) if x[3] else None} for x in acc.values()]
    return out_lo, out_hi


def _attach_band(st: Store, out: dict, band, a: date, h0: int, granularity: str, m: np.ndarray | None = None) -> dict:
    if band is None:
        return out
    if granularity == "month" and m is not None:
        lo, hi = _month_band(st, m, band, a, h0)
    else:
        lo = build_series(st, band[0], a, h0, granularity)
        hi = build_series(st, band[1], a, h0, granularity)
    any_band = False
    for p, l, h in zip(out["points"], lo, hi):
        p["p10"], p["p90"] = l["value"], h["value"]
        any_band = any_band or l["value"] is not None
    if any_band:
        out["interval"] = INTERVAL_INFO
    return out


def _num(x) -> float | None:
    return None if x is None or np.isnan(x) else round(float(x), 1)


def build_series(st: Store, m: np.ndarray, a: date, h0: int, granularity: str) -> list[dict]:
    n_days, n_h = m.shape
    days = [st.day_at(st.day_index(a) + i) for i in range(n_days)]
    if granularity == "hour":
        pts = []
        for i, d in enumerate(days):
            ds = d.isoformat()
            row = m[i]
            for j in range(n_h):
                h = h0 + j
                pts.append({"ts": f"{ds}T{h:02d}:00", "date": ds, "hour": h, "value": _num(row[j])})
        return pts
    daily = _nansum(m, 1)
    if granularity == "day":
        return [{"ts": d.isoformat(), "date": d.isoformat(), "value": _num(v)} for d, v in zip(days, daily)]
    # month
    out: dict[str, dict] = {}
    for d, v in zip(days, daily):
        key = f"{d.year}-{d.month:02d}"
        rec = out.setdefault(key, {"ts": key, "month": key, "label": f"{MONTHS_RU[d.month - 1]} {d.year}",
                                   "value": 0.0, "days": 0})
        if not np.isnan(v):
            rec["value"] += float(v)
            rec["days"] += 1
    for rec in out.values():
        rec["avg_per_day"] = round(rec["value"] / rec["days"], 1) if rec["days"] else None
        rec["value"] = round(rec["value"], 1) if rec["days"] else None
    return list(out.values())


def summarize(st: Store, m: np.ndarray, a: date, h0: int) -> dict:
    if np.all(np.isnan(m)):
        return {"total": None, "avg_per_day": None, "max_hourly": None, "max_at": None, "peak_hour": None}
    total = float(np.nansum(m))
    daily = _nansum(m, 1)
    n_days = int(np.sum(~np.isnan(daily)))
    flat = np.where(np.isnan(m), -1, m)
    i, j = np.unravel_index(int(np.argmax(flat)), m.shape)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)
        prof = np.nanmean(m, axis=0)
    ph = int(np.nanargmax(prof))
    return {
        "total": round(total, 1),
        "avg_per_day": round(total / n_days, 1) if n_days else None,
        "max_hourly": round(float(m[i, j]), 1),
        "max_at": f"{st.day_at(st.day_index(a) + int(i)).isoformat()}T{h0 + int(j):02d}:00",
        "peak_hour": h0 + ph,
        "peak_hour_avg": round(float(prof[ph]), 1),
        "hourly_profile": [{"hour": h0 + k, "avg": _num(v)} for k, v in enumerate(prof)],
    }


def _with_baseline(st: Store, out: dict, adj: Adj, source: str, m: np.ndarray, m0: np.ndarray | None,
                   a: date, h0: int, granularity: str | None) -> dict:
    """Attach «было -> стало» when corrections are active."""
    out["adjusted"] = bool(adj.active and source != "history")
    if not out["adjusted"] or m0 is None:
        return out
    before, after = float(np.nansum(m0)), float(np.nansum(m))
    out["adjustments"] = adj.describe()
    out["delta"] = {"total_before": round(before, 1), "total_after": round(after, 1),
                    "abs": round(after - before, 1), "pct": round((after / before - 1) * 100, 2) if before else None}
    base = {"summary": summarize(st, m0, a, h0)}
    base["summary"].pop("hourly_profile", None)
    if granularity:
        base["values"] = [p["value"] for p in build_series(st, m0, a, h0, granularity)]
    out["baseline"] = base
    return out


def series_query(st: Store, source: str, route: str | None, date_from, date_to, hour_from, hour_to,
                 granularity: str, adj: Adj = NO_ADJ) -> dict:
    routes = resolve_routes(st, route, source=source)
    a, b, h0, h1 = resolve_period(st, source, date_from, date_to, hour_from, hour_to)
    m = _cube_slice(st, source, routes, a, b, h0, h1, adj=adj)
    m0 = _cube_slice(st, source, routes, a, b, h0, h1, adj=adj.base) if adj.active else None
    out = {
        "route": route or "all", "routes": routes, "source": source, "model": adj.model, "source_ru": SOURCE_RU[source],
        "granularity": granularity, "date_from": str(a), "date_to": str(b),
        "hour_from": h0, "hour_to": h1, "unit": UNIT,
        "summary": summarize(st, m, a, h0),
        "points": build_series(st, m, a, h0, granularity),
    }
    _attach_band(st, out, _band(st, source, routes, a, b, h0, h1, adj=adj), a, h0, granularity, m)
    return _with_baseline(st, out, adj, source, m, m0, a, h0, granularity)


def stop_query(st: Store, stop_id: str, source: str, date_from, date_to, hour_from, hour_to, granularity,
               adj: Adj = NO_ADJ) -> dict:
    serving = st.stop_routes.get(stop_id)
    if not serving:
        raise ApiError(404, "stop_not_found", f"Остановка «{stop_id}» не найдена в справочнике")
    serving_data = [(r, s) for r, s in serving if r in st.route_idx]
    if not serving_data:
        raise ApiError(404, "no_data_for_stop",
                       f"Для маршрутов остановки {stop_id} ({', '.join(r for r, _ in serving)}) нет данных о пассажиропотоке")
    a, b, h0, h1 = resolve_period(st, source, date_from, date_to, hour_from, hour_to)
    routes = [r for r, _ in serving_data]
    w = [s for _, s in serving_data]
    m = _cube_slice(st, source, routes, a, b, h0, h1, weights=w, adj=adj)
    m0 = _cube_slice(st, source, routes, a, b, h0, h1, weights=w, adj=adj.base) if adj.active else None
    info = next(s for s in st.stops if s["stop_id"] == stop_id)
    out = {
        "stop_id": stop_id, "name": info["name"], "lat": info["lat"], "lon": info["lon"],
        "routes": [{"route": r, "share": round(s, 4)} for r, s in serving_data],
        "estimate": True,
        "method": "Оценка: прогноз маршрута × доля остановки (вес 1; пересадочный узел ×2; конечная ×0.1)",
        "source": source, "granularity": granularity, "date_from": str(a), "date_to": str(b),
        "hour_from": h0, "hour_to": h1, "unit": UNIT,
        "summary": summarize(st, m, a, h0),
        "points": build_series(st, m, a, h0, granularity),
    }
    _attach_band(st, out, _band(st, source, routes, a, b, h0, h1, weights=w, adj=adj), a, h0, granularity, m)
    return _with_baseline(st, out, adj, source, m, m0, a, h0, granularity)


def routes_query(st: Store) -> dict:
    from . import config
    ids = sorted(set(config.TRACKED_ROUTES) | set(st.routes), key=lambda r: (len(r), r))
    items = []
    for r in ids:
        has = r in st.route_idx
        tot = None
        if has:
            a, b = st.coverage["forecast"]
            tot = _num(np.nansum(st.cubes["forecast"][st.route_idx[r], st.day_index(a):st.day_index(b) + 1]))
        items.append({
            "route": r, "name": st.route_names.get(r), "has_data": has,
            "has_history": r in st.history_routes,
            "launch_date": str(st.launch[r]) if r in st.launch else None,
            "has_geometry": r in st.stops_by_route,
            "n_stops": len({s["stop_id"] for s in st.stops_by_route.get(r, [])}),
            "forecast_total": tot,
            "note": None if r in st.stops_by_route else "геопривязка остановок недоступна для маршрута",
        })
    return {
        "routes": items,
        "coverage": {k: {"from": str(v[0]), "to": str(v[1])} for k, v in st.coverage.items()},
        "explain_available": st.explain is not None,
    }


def stops_query(st: Store, route: str | None) -> dict:
    if route and route.lower() != "all":
        if route not in st.stops_by_route:
            if route in st.route_idx:
                return {"route": route, "stops": [], "lines": {},
                        "note": f"геопривязка остановок недоступна для маршрута {route}"}
            raise ApiError(404, "route_not_found", f"Маршрут «{route}» не найден")
        rs = [route]
    else:
        rs = list(st.stops_by_route)
    stops, lines = [], {}
    for r in rs:
        for s in st.stops_by_route[r]:
            stops.append({k: s[k] for k in ("stop_id", "name", "lat", "lon", "route", "direction", "seq", "hub")}
                         | {"share": round(s["share"], 4)})
            lines.setdefault(r, {}).setdefault(str(s["direction"]), []).append([s["lat"], s["lon"]])
    return {"route": route or "all", "stops": stops, "lines": lines}


def map_query(st: Store, route: str | None, day: str | None, source: str, adj: Adj = NO_ADJ) -> dict:
    lo, hi = st.coverage[source]
    d = parse_date(day, "date") or lo
    if d < lo or d > hi:
        raise ApiError(400, "out_of_range", f"Данные «{SOURCE_RU[source]}» доступны только с {lo} по {hi}")
    base = stops_query(st, route)
    di = st.day_index(d)
    route_hours, route_hours0 = {}, {}
    for r in {s["route"] for s in base["stops"]}:
        if r in st.route_idx:
            route_hours0[r] = _cube(st, source, adj)[st.route_idx[r], di]
            route_hours[r] = _cube_slice(st, source, [r], d, d, 0, 23, adj=adj)[0] if adj.active else route_hours0[r]
    vmax = 0.0
    for s in base["stops"]:
        rh = route_hours.get(s["route"])
        if rh is None:
            s["values"] = None
            continue
        vals = [_num(v * s["share"]) for v in rh]
        s["values"] = vals
        vmax = max(vmax, max((v for v in vals if v is not None), default=0))
    base.update({
        "date": str(d), "source": source, "estimate": True, "max_value": vmax,
        "route_hourly": {r: [_num(v) for v in h] for r, h in route_hours.items()},
        "no_data_routes": sorted({s["route"] for s in base["stops"]} - set(route_hours)),
        "adjusted": bool(adj.active and source != "history"),
    })
    if base["adjusted"]:
        base["baseline_route_hourly"] = {r: [_num(v) for v in h] for r, h in route_hours0.items()}
    return base


def kpi_query(st: Store, route: str | None, date_from, date_to, hour_from, hour_to, source: str,
              adj: Adj = NO_ADJ) -> dict:
    routes = resolve_routes(st, route, source=source)
    a, b, h0, h1 = resolve_period(st, source, date_from, date_to, hour_from, hour_to)
    m = _cube_slice(st, source, routes, a, b, h0, h1, adj=adj)
    m0 = _cube_slice(st, source, routes, a, b, h0, h1, adj=adj.base) if adj.active else None
    s = summarize(st, m, a, h0)
    # Change vs previous month: avg daily load of the period vs avg daily of previous calendar month (fact+forecast).
    py, pm = (a.year, a.month - 1) if a.month > 1 else (a.year - 1, 12)
    p_from, p_to = date(py, pm, 1), date(py, pm, calendar.monthrange(py, pm)[1])
    change = None
    lo, hi = st.coverage["combined"]
    if p_from >= lo:
        pm_m = _cube_slice(st, "combined", routes, p_from, min(p_to, hi), h0, h1, adj=adj.base)
        daily = _nansum(pm_m, 1)
        basis = "avg_day"
        if a == b:  # single day: compare with the same weekday of the previous month
            wd = a.weekday()
            mask = np.array([p_from.fromordinal(p_from.toordinal() + i).weekday() == wd for i in range(len(daily))])
            daily = daily[mask]
            basis = "same_weekday"
        if len(daily) and not np.all(np.isnan(daily)) and s["avg_per_day"]:
            prev = float(np.nanmean(daily))
            change = {"prev_month": f"{MONTHS_RU[pm - 1]} {py}", "prev_avg_per_day": round(prev, 1), "basis": basis,
                      "pct": round((s["avg_per_day"] / prev - 1) * 100, 1) if prev else None}
    s.pop("hourly_profile", None)
    out = {"route": route or "all", "source": source, "date_from": str(a), "date_to": str(b),
           "hour_from": h0, "hour_to": h1, **s, "change_vs_prev_month": change}
    return _with_baseline(st, out, adj, source, m, m0, a, h0, None)


def _monthly_avg_day(st: Store, routes: list[str], adj: Adj) -> list[float | None]:
    """Average day per calendar month of the base year (Jan–Oct actual, Nov–Dec forecast incl. corrections)."""
    lo, hi = st.coverage["combined"]
    m = _cube_slice(st, "combined", routes, lo, hi, 0, 23, adj=adj)
    daily = _nansum(m, 1)
    months = np.array([st.day_at(st.day_index(lo) + i).month for i in range(len(daily))])
    out = []
    for mo in range(1, 13):
        v = daily[months == mo]
        v = v[~np.isnan(v)]
        v = v[v > 0]
        out.append(float(v.mean()) if len(v) else None)
    return out


def year_scenario(st: Store, route: str | None, growth: float, band: float = 10.0, adj: Adj = NO_ADJ) -> dict:
    """Scenario forecast Jan–Dec of the next year, per route, summed for route=all.

    route with history:  avg_day(m) = level × index(m) × (1 + growth);  index(m) = avg_day_2025(m) / level,
                         level = mean of the 12 monthly average days of 2025 (Jan–Oct fact, Nov–Dec forecast).
    new route (no history, e.g. route 5): network seasonal index (all routes with history) × the route's level
                         derived from its forecast after launch:  level = avg_day(Dec) / index_network(Dec).
    """
    routes = resolve_routes(st, route)
    year = st.coverage["combined"][0].year
    sy = year + 1
    k = 1 + growth / 100.0
    hist_routes = [r for r in st.routes if r in st.history_routes]
    net = _monthly_avg_day(st, hist_routes, adj)
    net_vals = [v for v in net if v]
    net_level = float(np.mean(net_vals)) if net_vals else 0.0
    net_idx = [(v / net_level) if (v and net_level) else None for v in net]

    per_route, notes = {}, []
    for r in routes:
        mavg = _monthly_avg_day(st, [r], adj)
        if r in st.history_routes:
            vals = [v for v in mavg if v]
            level = float(np.mean(vals)) if vals else 0.0
            idx = [(v / level) if (v and level) else None for v in mavg]
        else:
            last = next((i for i in range(11, -1, -1) if mavg[i] and net_idx[i]), None)
            if last is None:
                continue
            level = mavg[last] / net_idx[last]
            idx = net_idx
            notes.append(f"Маршрут {r} новый: сезонность взята по сети, уровень — по прогнозу после запуска "
                         f"({MONTHS_RU[last]} {year}: {mavg[last]:,.0f} пасс./сутки)".replace(",", " "))
        per_route[r] = (level, idx, mavg)

    months = []
    tot = tot_lo = tot_hi = 0.0
    for mo in range(1, 13):
        days = calendar.monthrange(sy, mo)[1]
        avg = sum(lv * ix[mo - 1] * k for lv, ix, _ in per_route.values() if ix[mo - 1])
        base_2025 = sum(mv[mo - 1] for _, _, mv in per_route.values() if mv[mo - 1])
        total = avg * days
        lo_, hi_ = total * (1 - band / 100), total * (1 + band / 100)
        tot, tot_lo, tot_hi = tot + total, tot_lo + lo_, tot_hi + hi_
        idx_all = (avg / (sum(lv for lv, _, _ in per_route.values()) * k)) if per_route else None
        months.append({
            "month": mo, "label": MONTHS_RU[mo - 1], "year": sy,
            "seasonal_index": round(idx_all, 3) if idx_all else None,
            "base_2025_avg_per_day": round(base_2025, 1) if base_2025 else None,
            "base_2025_source": "факт" if date(year, mo, 1) <= st.coverage["history"][1] else "прогноз",
            "forecast_avg_per_day": round(avg, 1), "forecast_total": round(total), "low": round(lo_), "high": round(hi_),
        })
    return {
        "route": route or "all", "scenario_year": sy, "scenario": True, "label": "сценарный прогноз",
        "growth_pct": growth, "band_pct": band, "adjusted": adj.active,
        "method": (f"Сценарный прогноз на {sy}: сезонный индекс месяца = средние сутки месяца {year} "
                   f"(янв–окт — факт, ноя–дек — прогноз модели) / средний уровень {year}; "
                   f"прогноз = уровень × индекс × (1 + рост {growth:g} %) × дней в месяце; "
                   f"коридор ±{band:g} % ≈ 1 − метрика качества модели на лидерборде (0,90)"),
        "notes": notes,
        "total": round(tot), "total_low": round(tot_lo), "total_high": round(tot_hi), "months": months,
    }


def weather_query(st: Store, date_from, date_to, adj: Adj = NO_ADJ) -> dict:
    if st.weather_pr is None:
        raise ApiError(404, "weather_not_found", "Данные о погоде не загружены")
    lo, hi = st.coverage["combined"]
    a = parse_date(date_from, "date_from") or st.coverage["forecast"][0]
    b = parse_date(date_to, "date_to") or (a if date_from else hi)
    if b < a or a < lo or b > hi:
        raise ApiError(400, "out_of_range", f"Погода доступна с {lo} по {hi}")
    di = np.arange(st.day_index(a), st.day_index(b) + 1)
    w0 = adjust.weather_mult(st, NO_ADJ, di)
    w1 = adjust.weather_mult(st, adj, di)
    out = []
    for n, i in enumerate(di):
        d = st.day_at(int(i))
        scn = next(((x, t) for dd, x, t in adj.w_scn if dd == d), None)
        out.append({"date": str(d), "precip_mm": _num(st.weather_pr[i]), "temp_c": _num(st.weather_t[i]),
                    "scenario": {"add_mm": scn[0], "temp_c": scn[1]} if scn else None,
                    "weather_mult_model": round(float(w0[n]), 4), "weather_mult": round(float(w1[n]), 4)})
    return {"reference_precip_mm": round(st.weather_ref_pr, 2),
            "formula": "множитель = clip(exp(w_precip × (осадки − референс) + w_cold × [t < −10 °C]), w_floor, 1.05); "
                       "осадки и температура — за 06:00–21:00",
            "days": out}


# ---------------- rolling stock ----------------
CLASS_CAPACITY = {"ОБК": 190, "БК": 140}


def _fleet_route(st: Store, r: str, d: date, source: str, adj: Adj, p: dict) -> dict:
    info = st.fleet.get("routes", {}).get(r, {})
    lengths = [v["length_km"] for k, v in st.fleet.get("routes", {}).items() if v.get("length_km") and k in st.route_idx]
    default_len = float(np.median(lengths)) if lengths else 15.0
    length = info.get("length_km") or default_len
    cls = info.get("vehicle_class")
    cap = p["capacity"] or CLASS_CAPACITY.get(cls, 190)
    speed = p["speed"] or st.fleet.get("schedule_speed_kmh", 17.0)
    rt_min = 2 * length / speed * 60 + p["layover"]
    trips_per_veh_h = 60.0 / rt_min
    per_veh_h = cap * p["load_target"] * trips_per_veh_h
    min_veh = math.ceil(rt_min / p["max_headway"])

    def need(boardings):
        if boardings is None or np.isnan(boardings) or boardings < p["min_boardings"]:
            return 0  # no regular service needed (night / depot hours)
        onboard = boardings * p["peak_share"] / p["turnover"]
        return max(min_veh, math.ceil(onboard / per_veh_h))

    di = st.day_index(d)
    hours = _cube_slice(st, source, [r], d, d, 0, 23, adj=adj)[0]
    ml = st.ml
    has_iv = bool(source != "history" and ml is not None and ml.intervals)
    rlo = rhi = np.ones(24, dtype=np.float32)
    if has_iv:
        rlo = np.nan_to_num(ml.rel_lo[st.route_idx[r], di], nan=1.0)
        rhi = np.nan_to_num(ml.rel_hi[st.route_idx[r], di], nan=1.0)
    demand = hours * rhi if (has_iv and p["plan_by"] == "p90") else hours
    # reference supply ("плановый выпуск") = demand of the same weekday over the 4 preceding actual weeks
    ref = None
    if r in st.history_routes:
        h_end = min(di - 1, st.day_index(st.coverage["history"][1]))
        cand = [i for i in range(h_end, max(h_end - 60, -1), -1) if st.day_at(i).weekday() == d.weekday()][:4]
        if cand:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=RuntimeWarning)
                ref = np.nanmean(st.cubes["history"][st.route_idx[r], cand], axis=0)
    rows = []
    for h in range(24):
        b = hours[h]
        req = need(demand[h])
        plan = p["plan"] if p["plan"] is not None else (need(ref[h]) if ref is not None else None)
        if p["plan"] is not None and req == 0:
            plan = 0
        onboard = (b * p["peak_share"] / p["turnover"]) if b is not None and not np.isnan(b) else None
        load = (onboard / (plan * per_veh_h)) if (plan and onboard is not None) else None
        delta = (req - plan) if plan is not None else None
        # risk only where the reference has regular service (plan > 0): night edge hours are not flagged
        status = "none" if req == 0 and not plan else "ok" if not plan \
            else "risk" if (delta or 0) > 0 else "surplus" if delta is not None and delta < 0 else "ok"
        # P(load > capacity): boardings that fill the supply (current plan, or the requirement for new routes)
        # to 100 % of vehicle capacity; two-piece lognormal around the shown forecast (see app/ml.py)
        p_over = None
        if has_iv and b is not None and not np.isnan(b) and (plan or req):
            supply = plan or req
            cap_boardings = supply * cap * trips_per_veh_h * p["turnover"] / p["peak_share"]
            p_over = round(ml_p_exceed(float(b), float(rlo[h]), float(rhi[h]), cap_boardings), 3)
        rows.append({"hour": h, "boardings": _num(b), "peak_dir_onboard": _num(onboard), "required": req,
                     "boardings_p10": _num(b * rlo[h]) if has_iv else None,
                     "boardings_p90": _num(b * rhi[h]) if has_iv else None, "p_overflow": p_over,
                     "plan": plan, "delta": delta, "load_at_plan_pct": round(load * 100) if load is not None else None,
                     "headway_min": round(rt_min / req, 1) if req else None, "status": status})
    return {"route": r, "length_km": round(length, 2), "length_source": "геометрия остановок" if info.get("length_km")
            else f"нет геопривязки — медиана маршрутов ({default_len:.1f} км)",
            "vehicle_model": info.get("vehicle_model") or "71-931М (принято)", "vehicle_class": cls or "ОБК (принято)",
            "capacity": cap, "round_trip_min": round(rt_min, 1), "trips_per_vehicle_per_hour": round(trips_per_veh_h, 3),
            "passengers_per_vehicle_per_hour": round(per_veh_h, 1), "min_vehicles_service": min_veh,
            "plan_source": "задан вручную" if p["plan"] is not None else
            ("потребность по факту 4 предыдущих недель (тот же день недели)" if ref is not None else "нет истории (новый маршрут)"),
            "hours": rows, "peak_required": max(x["required"] for x in rows),
            "max_p_overflow": max((x["p_overflow"] for x in rows if x["p_overflow"] is not None), default=None),
            "max_p_overflow_hour": max((x for x in rows if x["p_overflow"] is not None),
                                       key=lambda x: x["p_overflow"], default={"hour": None})["hour"]}


def ml_p_exceed(median: float, rel_lo: float, rel_hi: float, threshold: float) -> float:
    from .ml import p_exceed
    return p_exceed(median, rel_lo, rel_hi, threshold)


def _fi(x) -> str:
    return f"{x:,.0f}".replace(",", " ") if x is not None else "—"


def _intervals(rows: list[dict], key) -> list[tuple[int, int, list[dict]]]:
    out, cur = [], None
    for x in rows:
        k = key(x)
        if k is None:
            cur = None
            continue
        if cur and cur[2] == k and cur[1] == x["hour"] - 1:
            cur[1] = x["hour"]
            cur[3].append(x)
        else:
            cur = [x["hour"], x["hour"], k, [x]]
            out.append(cur)
    return [(a, b, xs) for a, b, _, xs in out]


def _veh(n: int) -> str:
    n = abs(n)
    return "вагон" if n % 10 == 1 and n % 100 != 11 else "вагона" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "вагонов"


def fleet_query(st: Store, route: str | None, day: str | None, adj: Adj, capacity: int | None, load_target: float,
                peak_share: float, turnover: float, speed: float | None, layover: float, max_headway: float,
                plan: int | None, min_boardings: float = 30.0, plan_by: str = "p50") -> dict:
    routes = resolve_routes(st, route)
    lo, hi = st.coverage["combined"]
    d = parse_date(day, "date") or st.coverage["forecast"][0]
    if d < lo or d > hi:
        raise ApiError(400, "out_of_range", f"Дата должна быть с {lo} по {hi}")
    source = "history" if d <= st.coverage["history"][1] else "forecast"
    p = dict(capacity=capacity, load_target=load_target, peak_share=peak_share, turnover=turnover, speed=speed,
             layover=layover, max_headway=max_headway, plan=plan, min_boardings=min_boardings, plan_by=plan_by)
    per = [_fleet_route(st, r, d, source, adj, p) for r in routes
           if not (source == "history" and r not in st.history_routes)]
    recs = []
    for fr in per:
        rows = fr["hours"]
        for a, b, xs in _intervals(rows, lambda x: ("risk", x["delta"]) if x["status"] == "risk" and x["delta"] else
                                  ("surplus", x["delta"]) if x["status"] == "surplus" else None):
            dlt = xs[0]["delta"]
            peak = max(xs, key=lambda x: x["boardings"] or 0)
            span = f"{a:02d}:00–{b + 1:02d}:00"
            if dlt > 0:
                load = f", загрузка при текущем выпуске {peak['load_at_plan_pct']} %" if peak["load_at_plan_pct"] else ""
                pov = max((x["p_overflow"] for x in xs if x["p_overflow"] is not None), default=None)
                pov_s = f"; вероятность переполнения {round(pov * 100)} %" if pov is not None else ""
                by = " по P90" if plan_by == "p90" and pov is not None else ""
                txt = (f"Маршрут {fr['route']}, {span}: +{dlt} {_veh(dlt)} (всего {peak['required']}{by}; "
                       f"прогноз {_fi(peak['boardings'])} пасс./ч{load}{pov_s})")
                recs.append({"route": fr["route"], "from": a, "to": b, "delta": dlt, "type": "risk", "text": txt,
                             "severity": dlt * len(xs)})
            else:
                txt = f"Маршрут {fr['route']}, {span}: можно снять {-dlt} {_veh(dlt)} (резерв вместимости)"
                recs.append({"route": fr["route"], "from": a, "to": b, "delta": dlt, "type": "surplus", "text": txt,
                             "severity": dlt * len(xs)})
        if fr["plan_source"].startswith("нет истории"):
            recs.append({"route": fr["route"], "from": None, "to": None, "delta": fr["peak_required"], "type": "info",
                         "text": f"Маршрут {fr['route']} (новый): в пик нужно {fr['peak_required']} {_veh(fr['peak_required'])}, "
                                 f"интервал ≈ {min(x['headway_min'] or 99 for x in fr['hours']):.0f} мин", "severity": 0})
    recs.sort(key=lambda x: (0 if x["type"] == "risk" else 1 if x["type"] == "info" else 2, -abs(x["severity"])))
    total = [{"hour": h, "required": sum(fr["hours"][h]["required"] for fr in per),
              "plan": sum(fr["hours"][h]["plan"] or 0 for fr in per),
              "boardings": _num(sum(fr["hours"][h]["boardings"] or 0 for fr in per)),
              "p_overflow": max((fr["hours"][h]["p_overflow"] for fr in per if fr["hours"][h]["p_overflow"] is not None),
                                default=None)} for h in range(24)]
    worst = max((fr for fr in per if fr["max_p_overflow"] is not None), key=lambda fr: fr["max_p_overflow"], default=None)
    iv = bool(source != "history" and st.ml is not None and st.ml.intervals)
    return {
        "route": route or "all", "date": str(d), "source": source, "adjusted": adj.active and source != "history",
        "model": adj.model, "plan_by": plan_by if iv else "p50",
        "overflow": {
            "available": iv,
            "max": worst["max_p_overflow"] if worst else None,
            "route": worst["route"] if worst else None, "hour": worst["max_p_overflow_hour"] if worst else None,
            "method": "P(входы за час > вместимость текущего выпуска при 100 % заполнения): логнормальное распределение "
                      "по ячейке, подобранное по P10/P50/P90 ML-модели (σ слева и справа от медианы отдельно)"
                      if iv else "нет интервалов прогноза (intervals.csv) или выбран период факта",
        },
        "assumptions": {
            "capacity": capacity or "по классу из наряда: ОБК (71-931М) — 190, БК — 140 пасс. (≈5 чел./м²)",
            "load_target": load_target, "peak_share": peak_share, "turnover": turnover,
            "speed_kmh": speed or st.fleet.get("schedule_speed_kmh", 17.0),
            "speed_source": "задана вручную" if speed else f"по расписанию из справочника ({st.fleet.get('schedule_sample', '—')})",
            "layover_min": layover, "max_headway_min": max_headway, "min_boardings_per_hour": min_boardings,
            "formula": "вагонов = max(⌈входы × доля пикового направления / сменяемость ÷ (вместимость × целевая загрузка "
                       "× рейсов на вагон в час)⌉, ⌈оборот / макс. интервал⌉); оборот = 2 × длина / скорость + отстой",
        },
        "recommendations": recs[:30], "routes": per, "total_hours": total,
    }


def explain_query(st: Store, route: str, day: str) -> dict:
    routes = resolve_routes(st, route, allow_all=False)
    d = parse_date(day, "date")
    if d is None:
        raise ApiError(400, "date_required", "Укажите дату в параметре «date» (ГГГГ-ММ-ДД)")
    if st.explain is None:
        return {"available": False, "route": routes[0], "date": str(d),
                "message": "Декомпозиция прогноза пока недоступна: файл с множителями не загружен"}
    rows = st.explain.get((routes[0], str(d)))
    if not rows:
        raise ApiError(404, "explain_not_found", f"Нет декомпозиции для маршрута {routes[0]} на {d}")
    ml = st.ml
    if ml is not None and ml.hybrid and routes[0] in st.route_idx:
        ri, di = st.route_idx[routes[0]], st.day_index(d)
        if 0 <= di < st.n_days:
            ratio, hyb = ml.hybrid_ratio[ri, di], st.cubes["forecast_hybrid"][ri, di]
            rows = [x | {"ml_ratio": None if np.isnan(ratio[x["hour"]]) else round(float(ratio[x["hour"]]), 4),
                         "prediction_hybrid": _num(hyb[x["hour"]])} for x in rows]
    daily = {"base": round(sum(x["base"] for x in rows), 1),
             "prediction": round(sum(x.get("prediction", x["prediction_recomputed"]) for x in rows), 1)}
    return {"available": True, "route": routes[0], "date": str(d), "factors": st.explain_cols, "daily": daily,
            "formula": "прогноз = base × " + " × ".join(st.explain_cols), "hours": rows}


def export_rows(st: Store, source: str, route: str | None, date_from, date_to, hour_from, hour_to,
                granularity: str, adj: Adj = NO_ADJ) -> tuple[list[str], list[list]]:
    routes = resolve_routes(st, route, source=source)
    a, b, h0, h1 = resolve_period(st, source, date_from, date_to, hour_from, hour_to)
    col = "Пассажиры (факт)" if source == "history" else "Пассажиры (прогноз)" if source == "forecast" else "Пассажиры"
    if granularity == "hour":
        header = ["Маршрут", "Дата", "Час", col]
    elif granularity == "day":
        header = ["Маршрут", "Дата", col]
    else:
        header = ["Маршрут", "Месяц", col, "Дней с данными", "Среднее в сутки"]
    corrected = adj.active and source != "history"
    if corrected:
        k = 3 if granularity == "hour" else 2
        header = header[:k] + [col + " с коррекцией", "Прогноз модели"] + header[k + 1:]
    with_iv = source != "history" and st.ml is not None and st.ml.intervals
    if with_iv:
        header = header + ["P10 (80 % интервал)", "P90 (80 % интервал)"]
    rows = []
    for r in routes:
        m = _cube_slice(st, source, [r], a, b, h0, h1, adj=adj)
        pts = build_series(st, m, a, h0, granularity)
        base = None
        if corrected:
            base = [p["value"] for p in build_series(st, _cube_slice(st, source, [r], a, b, h0, h1, adj=adj.base), a, h0, granularity)]
        iv = None
        if with_iv:
            bnd = _band(st, source, [r], a, b, h0, h1, adj=adj)
            iv = (_month_band(st, m, bnd, a, h0) if granularity == "month" else
                  (build_series(st, bnd[0], a, h0, granularity), build_series(st, bnd[1], a, h0, granularity)))
        for i, p in enumerate(pts):
            extra = [base[i]] if corrected else []
            tail = [iv[0][i]["value"], iv[1][i]["value"]] if iv else []
            if granularity == "hour":
                rows.append([r, p["date"], p["hour"], p["value"], *extra, *tail])
            elif granularity == "day":
                rows.append([r, p["date"], p["value"], *extra, *tail])
            else:
                rows.append([r, p["month"], p["value"], *extra, p["days"], p["avg_per_day"], *tail])
    return header, rows


# ---------------- AI / ML layer ----------------
TRAINING_NOTE = ("Кнопка информационная: модель уже учится на очищенной истории. Праздники, ремонты и сбои "
                 "исключаются ручной разметкой аналитиков и автоочисткой по ИИ-детектору с «защитой режима» "
                 "(продолжающийся режим, например ремонт маршрута 50 по выходным, не выбрасывается). На бэктесте такая "
                 "автоочистка воспроизводит ручную очистку, поэтому повторно исключать аномалии не нужно.")


def anomalies_query(st: Store, route: str | None, date_from, date_to, kind: str | None = None) -> dict:
    routes = resolve_routes(st, route)
    lo, hi = st.coverage["history"]
    a = parse_date(date_from, "date_from") or lo
    b = parse_date(date_to, "date_to") or (a if date_from and not date_to else hi)
    if b < a:
        raise ApiError(400, "invalid_period", f"Дата окончания ({b}) раньше даты начала ({a})")
    ml = st.ml
    base = {"route": route or "all", "date_from": str(a), "date_to": str(b), "training_note": TRAINING_NOTE,
            "kinds": {"drop": "провал", "spike": "всплеск", "shape": "аномальный профиль"}}
    if ml is None or not ml.anomalies:
        return base | {"available": False, "count": 0, "by_kind": {}, "events": [],
                       "message": "ИИ-детектор аномалий ещё не подключён: нет файла anomalies.csv"}
    rs, sa, sb = set(routes), str(a), str(b)
    ev = [e for e in ml.anomalies if e["route"] in rs and sa <= e["date"] <= sb and (not kind or e["kind"] == kind)]
    by_kind: dict[str, int] = {}
    for e in ev:
        by_kind[e["kind"]] = by_kind.get(e["kind"], 0) + 1
    return base | {"available": True, "count": len(ev), "by_kind": by_kind, "events": ev,
                   "total_in_history": len(ml.anomalies)}


FACTORS = [
    {"key": "base", "name": "Базовый профиль", "description": "уровень маршрута (последние недели) × суточная форма по типу дня"},
    {"key": "special_mult", "name": "Особый день", "description": "праздники, переносы рабочих дней, предпраздничные дни (производственный календарь)"},
    {"key": "weather_mult", "name": "Погода", "description": "осадки 06–21 ч (−1,1 %/мм от нормы) и мороз ниже −10 °C (−3,4 %)"},
    {"key": "rules_mult", "name": "Сетевые события", "description": "запуск маршрута 5 с 16.12, изменения маршрутов, бесплатный проезд в новогоднюю ночь"},
    {"key": "ml_ratio", "name": "ML-поправка (LightGBM)", "description": "отношение факт/структурный прогноз, предсказанное градиентным бустингом по календарю, погоде, событиям и загруженности дорог"},
]
SOURCES = [
    {"name": "Погода: Open-Meteo (архив ERA5)", "what": "почасовые осадки, температура, снег по Москве",
     "url": "https://open-meteo.com/en/docs/historical-weather-api", "used_in": "weather_mult, признаки ML"},
    {"name": "Производственный календарь 2025", "what": "выходные, праздники, переносы, сокращённые дни",
     "url": "https://www.consultant.ru/law/ref/calendar/proizvodstvennye/2025/", "used_in": "special_mult, признаки ML"},
    {"name": "События и перекрытия (Дептранс)", "what": "перекрытия, изменения маршрутов, запуск маршрута 5",
     "url": "https://transport.mos.ru/mostrans/closures", "used_in": "rules_mult, признаки ML"},
    {"name": "Загруженность дорог (ЦОДД, «Дептранс. Оперативно»)", "what": "балл пробок 0–10 и средняя скорость по постам ЦОДД",
     "url": "https://t.me/DtOperativno", "used_in": "признаки ML (+2 % пассажиров трамвая в дни ≥ 7 баллов)"},
]


TABLE_TITLES = [  # (keyword in heading/header, Russian title)
    ("decision", "Решения по ML-компонентам"),
    ("hybrid", "Гибрид: точность по фолдам (метрика соревнования, выше — лучше)"),
    ("interval", "Интервалы P10–P90: методы (среднее по 5 фолдам)"),
    ("known cause", "ИИ-детектор: полнота по известным причинам"),
    ("variant", "Автоочистка истории против ручной (Δ ×10⁻³)"),
    ("fold", "Точность по фолдам"),
]
CELL_RU = {"Component": "Компонент", "Method": "Метод", "Fold result": "Результат на фолдах", "Decision": "Решение",
           "Hybrid": "Гибрид", "Intervals": "Интервалы", "Anomalies": "Аномалии", "keep v08": "оставить v08",
           "monitoring tool": "инструмент мониторинга", "Known cause": "Известная причина", "Recall": "Полнота",
           "Variant": "Вариант", "mean": "среднее", "coverage": "покрытие", "width": "ширина"}


def _title(t: dict) -> str:
    txt = f"{t.get('heading') or ''} {' '.join(t['header'])}".lower()
    return next((ru for k, ru in TABLE_TITLES if k in txt), t.get("heading") or "Таблица")


def model_query(st: Store) -> dict:
    from . import ml as mlmod
    ml = st.ml or mlmod.MLData()
    tables = mlmod.parse_md_tables(ml.report_md) if ml.report_md else []
    for t in tables:
        t["title"] = _title(t)
        t["header"] = [CELL_RU.get(h, h) for h in t["header"]]
        t["rows"] = [[CELL_RU.get(v, v) for v in r] for r in t["rows"]]
    fold_idx = mlmod.pick_fold_table(tables)
    if ml.folds_table and (fold_idx is None or not any("fold" in " ".join(t["header"]).lower() for t in tables)):
        tables = [ml.folds_table | {"title": ml.folds_table["heading"]}] + tables
        fold_idx = 0
    hyb_pct = None
    if ml.hybrid:
        a, b = st.coverage["forecast"]
        i0, i1 = st.day_index(a), st.day_index(b)
        v08 = float(np.nansum(st.cubes["forecast"][:, i0:i1 + 1]))
        hyb = float(np.nansum(st.cubes["forecast_hybrid"][:, i0:i1 + 1]))
        hyb_pct = round((hyb / v08 - 1) * 100, 2) if v08 else None
    zero_w = bool(ml.hybrid and (ml.hybrid_weight_zero or (hyb_pct is not None and abs(hyb_pct) < 0.01)))
    hybrid_txt = ("Гибрид: к структурному прогнозу применяется поправка LightGBM, прогноз = base × (1 − w + w·r̂), "
                  "где r̂ — предсказанное бустингом отношение факт/структурный прогноз по календарю, погоде, событиям и "
                  "загруженности дорог (55 исторических точек прогноза). ")
    gap = (f" (от отправленного v08 отличается на {hyb_pct:+.2f} % за ноябрь–декабрь)".replace(".", ",").replace("-", "−")
           if hyb_pct is not None and abs(hyb_pct) >= 0.01 else "")
    hybrid_txt += (f"На скользящем бэктесте бустинг не улучшил точность, поэтому в финале вес w = 0: гибридный ряд равен "
                   f"структурной базе без ML-поправки{gap}, а поправка ml_ratio показана как объясняющий фактор."
                   if zero_w or not ml.hybrid else
                   f"Гибрид отличается от v08 на {hyb_pct:+.2f} % за ноябрь–декабрь.".replace(".", ",", 1))
    out = {
        "hybrid_available": ml.hybrid, "intervals_available": ml.intervals,
        "anomalies_available": bool(ml.anomalies), "report_available": ml.report_md is not None,
        "hybrid_weight_zero": zero_w,
        "description": [
            "Структурная модель (v08): прогноз = базовый профиль × особый день × погода × сетевые события. "
            "Базовый профиль — уровень маршрута за последние недели × суточная форма по типу дня. "
            "Модель прозрачна: каждый множитель виден в блоке «Из чего складывается прогноз».",
            hybrid_txt,
            "Интервалы P10–P90: конформные квантили по часу, типу дня и горизонту прогноза, откалиброванные на "
            "скользящем бэктесте (покрытие — в таблице ниже). По ним для каждого часа считается вероятность "
            "переполнения: раздельное логнормальное распределение через P10/P50/P90.",
            "ИИ-детектор аномалий без учителя (IsolationForest и робастные z-оценки уровня, доли маршрута и суточного "
            "профиля) размечает дни истории: провал, всплеск, аномальный профиль. Автоочистка с «защитой режима» "
            "воспроизводит ручную очистку аналитиков; детектор работает как инструмент мониторинга.",
        ],
        "summary": mlmod.report_text(ml.report_md),
        "tables": tables, "fold_table": fold_idx,
        "sources": SOURCES,
        "factors": [(f | {"description": f["description"] + " (в финале вес 0 — справочно)"}) if f["key"] == "ml_ratio" and zero_w else f
                    for f in FACTORS if f["key"] in (["base"] + st.explain_cols) or (f["key"] == "ml_ratio" and ml.hybrid)],
        "files": {"intervals_rows": ml.intervals_rows, "hybrid_rows": ml.hybrid_rows, "anomalies": len(ml.anomalies)},
        "errors": ml.errors,
    }
    if ml.hybrid:
        out["hybrid_compare"] = {"v08_total": round(v08), "hybrid_total": round(hyb), "pct": hyb_pct}
    if ml.intervals:
        fc = st.cubes["forecast"]
        w = np.nan_to_num(fc)
        width = np.nan_to_num(ml.rel_hi - ml.rel_lo)
        out["interval_avg_width_pct"] = round(float((w * width).sum() / w.sum() * 100), 1) if w.sum() else None
    return out


# ---------------- road traffic (ЦОДД) ----------------
def traffic_query(st: Store, date_from, date_to, adj: Adj = NO_ADJ) -> dict:
    if st.traffic_score is None:
        raise ApiError(404, "traffic_not_found", "Данные ЦОДД о загруженности дорог не загружены")
    lo, hi = st.coverage["combined"]
    a = parse_date(date_from, "date_from") or st.coverage["forecast"][0]
    b = parse_date(date_to, "date_to") or (a if date_from else hi)
    if b < a or a < lo or b > hi:
        raise ApiError(400, "out_of_range", f"Данные о пробках доступны с {lo} по {hi}")
    scn = dict(adj.traffic)
    days = []
    for i in range(st.day_index(a), st.day_index(b) + 1):
        d = st.day_at(i)
        sc, nm = float(st.traffic_score[i]), float(st.traffic_norm[i])
        s2 = scn.get(d)
        fc = d >= st.coverage["forecast"][0]
        mult = (1 + adj.w_traffic * (s2 - nm)) if (s2 is not None and fc) else 1.0
        days.append({"date": str(d), "score": sc, "reported": str(d) in st.traffic_url or sc != 4.0, "norm": round(nm, 2),
                     "source_url": st.traffic_url.get(str(d)), "scenario_score": s2, "mult": round(mult, 4)})
    return {"source": "ЦОДД, посты «Дептранс. Оперативно» (t.me/DtOperativno): балл загруженности дорог 0–10",
            "effect_per_point": adj.w_traffic,
            "formula": "множитель = 1 + эффект × (балл − норма 3 недель); норма — среднее 21 предыдущего дня, "
                       "день без поста = 4 балла; v08 предполагает обычный день (балл = норма)",
            "confirmed": "+2,0 % пассажиров трамвая в дни с баллом ≥ 7 (p = 0,039); +0,7 %/балл к норме 3 недель (p = 0,025)",
            "days": days}
