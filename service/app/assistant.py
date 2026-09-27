"""«Помощник диспетчера»: rule-based answers to structured questions, built only from the service's own data.

No LLM and no external calls. `app.nlq.parse_query` turns the text into a structured query (route, dates, hours,
granularity, corrections, intent). The dispatcher can confirm or edit it in the UI, and `answer_query` computes the
answer from the same query functions the API uses (fleet, series, kpi, anomalies, model).
"""
from __future__ import annotations

from datetime import date, timedelta

from . import adjust
from . import queries as Q
from .adjust import Adj
from .errors import ApiError
from .nlq import parse_query

MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря"]
WD_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

EXAMPLES = [
    "Где завтра переполнение?",
    "Сколько вагонов нужно на 17 маршруте в 8 утра?",
    "Пассажиры на семерке послезавтра в вечерний час пик",
    "Когда час пик на 11 маршруте в пятницу?",
    "Что будет на 17-ке 12 декабря, если дождь 10 мм?",
    "Какие аномалии были на маршруте 12 в апреле?",
    "Как устроена модель?",
]
FIELDS = ("route", "date_from", "date_to", "hour_from", "hour_to", "granularity", "corrections", "intent")


def _fmt(x) -> str:
    return "—" if x is None else f"{x:,.0f}".replace(",", " ")


def _human(d: date) -> str:
    return f"{d.day} {MONTHS_GEN[d.month - 1]} ({WD_SHORT[d.weekday()]})"


def _hr(h0: int, h1: int) -> str:
    return f"{h0:02d}:00–{(h1 + 1) % 24:02d}:00"


def _route(st, raw: str | None) -> str | None:
    if raw in (None, "", "all"):
        return None
    if raw not in st.route_idx:
        raise ApiError(404, "route_not_found",
                       f"Маршрут «{raw}» не найден. Доступные маршруты: {', '.join(st.routes)}")
    return raw


def _in_range(st, d: date) -> None:
    lo, hi = st.coverage["combined"]
    if not lo <= d <= hi:
        raise ApiError(400, "out_of_range", f"Данные есть с {lo:%d.%m.%Y} по {hi:%d.%m.%Y}; спросите про дату из этого периода")


def _fleet(st, route, d, adj, plan_by):
    return Q.fleet_query(st, route, str(d), adj, None, 0.8, 0.6, 1.5, None, 10.0, 20.0, None, 30.0, plan_by)


def _adj(st, q: dict, base: Adj) -> Adj:
    """Corrections recognised in the question override the dashboard's; otherwise the dashboard's are used."""
    c = q.get("corrections") or {}
    if not c:
        return base
    return adjust.parse(st, c.get("k_level"), 1.0, adjust.DEF_PRECIP, adjust.DEF_COLD, adjust.DEF_FLOOR,
                        c.get("w_scenario"), c.get("k_event"), base.model, c.get("k_traffic"))


def _ranges(q: dict) -> list[tuple[int, int]]:
    if q.get("hour_ranges"):
        return [(int(a), int(b)) for a, b in q["hour_ranges"]]
    if q.get("hour_from") is not None:
        return [(int(q["hour_from"]), int(q.get("hour_to", q["hour_from"])))]
    return []


def answer(st, text: str, ref: date, adj: Adj, plan_by: str = "p50") -> dict:
    return answer_query(st, parse_query(text, ref, st.coverage["combined"][0].year), adj, plan_by)


def answer_query(st, q: dict, adj: Adj, plan_by: str = "p50") -> dict:
    """q: structured query (from parse_query, possibly edited by the dispatcher)."""
    intent = q.get("intent") or "load"
    items: list[str] = []
    action: dict = {}
    try:
        route = _route(st, q.get("route"))
        a_adj = _adj(st, q, adj)
        d0 = date.fromisoformat(q["date_from"]) if q.get("date_from") else st.coverage["forecast"][0]
        d1 = date.fromisoformat(q["date_to"]) if q.get("date_to") else d0
        rng = _ranges(q)
        who = f"Маршрут {route}" if route else "Все маршруты"
        if intent == "help":
            text = ("Я отвечаю на вопросы по данным сервиса: переполнение, потребность в вагонах, пассажиропоток по "
                    "часам, час пик, аномалии в истории, устройство модели. Укажите маршрут, дату и час, например:")
            items = EXAMPLES
        elif intent == "model":
            m = Q.model_query(st)
            text = m["description"][0] + (" " + m["description"][1] if m["hybrid_available"] else "")
            if m["fold_table"] is not None:
                tb = m["tables"][m["fold_table"]]
                items += [" · ".join(f"{h}: {v}" for h, v in zip(tb["header"], r)) for r in tb["rows"][:6]]
            action = {"scroll": "modelCard"}
        elif intent == "anomalies":
            if not q.get("date_from") or q.get("date_defaulted"):
                a, b = st.coverage["history"]
            else:
                a, b = d0, d1
            r = Q.anomalies_query(st, route or "all", str(a), str(b))
            if not r["available"]:
                text = r["message"]
            elif not r["events"]:
                text = f"Аномалий {'на маршруте ' + route if route else 'в сети'} за {a:%d.%m}–{b:%d.%m.%Y} не найдено."
            else:
                ev = sorted(r["events"], key=lambda e: -abs(e["score"]))
                kinds = ", ".join(f"{r['kinds'].get(k, k)} — {n}" for k, n in r["by_kind"].items())
                text = (f"ИИ-детектор нашёл {r['count']} аномальных дней {'на маршруте ' + route if route else 'в сети'} "
                        f"за {a:%d.%m}–{b:%d.%m.%Y} ({kinds}). Самые сильные:")
                items = [f"{date.fromisoformat(e['date']):%d.%m} · маршрут {e['route']} · {e['kind_ru']}: {e['label']}"
                         + (f" ({e['deviation_pct']:+.0f} % к типичному дню)".replace(".", ",") if e["deviation_pct"] is not None else "")
                         for e in ev[:6]]
            action = {"scroll": "anomCard", "route": route}
        else:
            _in_range(st, d0)
            _in_range(st, d1)
            action = {"route": route or "all", "date": str(d0), "hour": rng[0][0] if rng else None}
            if intent == "overflow":
                r = _fleet(st, route or "all", d0, a_adj, plan_by)
                risks = [x for x in r["recommendations"] if x["type"] == "risk"
                         and (not rng or any(x["from"] is not None and x["from"] <= b and x["to"] >= a for a, b in rng))]
                ov = r["overflow"]
                where = f"на маршруте {route}" if route else "в сети"
                span = (" в " + " и ".join(_hr(a, b) for a, b in rng)) if rng else ""
                if risks:
                    rs = sorted({x["route"] for x in risks}, key=lambda s: (len(s), s))
                    text = f"{_human(d0)}{span}: риск переполнения {where} — маршруты {', '.join(rs)}."
                else:
                    text = f"{_human(d0)}{span}: переполнения {where} при текущем выпуске не ожидается."
                if ov["available"] and ov["max"] is not None:
                    text += (f" Максимальная вероятность переполнения за сутки — {round(ov['max'] * 100)} % "
                             f"(маршрут {ov['route']}, {ov['hour']:02d}:00).")
                items = [x["text"] for x in risks[:6]]
                action["scroll"] = "fleetCard"
            elif intent == "vehicles":
                r = _fleet(st, route or "all", d0, a_adj, plan_by)
                fr = r["routes"][0] if route else None
                rows = fr["hours"] if fr else r["total_hours"]
                parts = []
                for a, b in (rng or [(0, 23)]):
                    x = max(rows[a:b + 1], key=lambda x: x["required"])
                    s = (f"{_hr(a, b) if a != b else _hr(a, a)}: нужно {x['required']} ваг. на линии"
                         + (f" (макс. в {x['hour']:02d}:00)" if a != b else "")
                         + (f", сейчас ≈ {x['plan']}" if x.get("plan") else "")
                         + f", прогноз {_fmt(x['boardings'])} пасс./ч")
                    if x.get("boardings_p10") is not None:
                        s += f" (80 %: {_fmt(x['boardings_p10'])}–{_fmt(x['boardings_p90'])})"
                    if x.get("headway_min"):
                        s += f", интервал ≈ {x['headway_min']:.0f} мин"
                    if x.get("p_overflow") is not None:
                        s += f", вероятность переполнения {round(x['p_overflow'] * 100)} %"
                    parts.append(s)
                text = f"{who}, {_human(d0)}: " + "; ".join(parts) + "."
                if plan_by == "p90" and r["plan_by"] == "p90":
                    text += " Расчёт по P90 (с запасом на верхнюю границу прогноза)."
                if fr:
                    items = [f"{fr['vehicle_model']}, вместимость {fr['capacity']} пасс., оборот {fr['round_trip_min']:.0f} мин"]
                items += [rec["text"] for rec in r["recommendations"] if rec["type"] == "risk"][:3]
                action["scroll"] = "fleetCard"
            elif intent == "peak":
                src = "history" if d0 <= st.coverage["history"][1] else "forecast"
                k = Q.kpi_query(st, route or "all", str(d0), str(d0), 0, 23, src, a_adj)
                s = Q.series_query(st, src, route or "all", str(d0), str(d0), 0, 23, "hour", a_adj)["points"]
                am = max(s[5:12], key=lambda p: p["value"] or 0)
                pm = max(s[14:22], key=lambda p: p["value"] or 0)
                who2 = f"маршрута {route}" if route else "сети"
                text = (f"Час пик {who2} {_human(d0)} ({'факт' if src == 'history' else 'прогноз'}): утренний — "
                        f"{am['hour']:02d}:00, {_fmt(am['value'])} пасс./ч; вечерний — {pm['hour']:02d}:00, "
                        f"{_fmt(pm['value'])} пасс./ч. Максимум суток — {k['peak_hour']:02d}:00; за сутки {_fmt(k['total'])}.")
                action["hour"] = k["peak_hour"]
            else:  # load
                src = "history" if d1 <= st.coverage["history"][1] else "forecast" if d0 > st.coverage["history"][1] else "combined"
                kind = {"history": "факт", "forecast": "прогноз", "combined": "факт + прогноз"}[src]
                if d0 != d1:
                    s = Q.series_query(st, src, route or "all", str(d0), str(d1), 0, 23, "day", a_adj)
                    sm = s["summary"]
                    lo = sum(x.get("p10") or 0 for x in s["points"]) if s.get("interval") else None
                    text = (f"{who}, {d0:%d.%m}–{d1:%d.%m.%Y}: {kind} {_fmt(sm['total'])} пасс., в среднем "
                            f"{_fmt(sm['avg_per_day'])} в сутки; самый загруженный час — {sm['max_at'][8:10]}.{sm['max_at'][5:7]} "
                            f"{sm['max_at'][11:]} ({_fmt(sm['max_hourly'])} пасс./ч).")
                    action.update({"horizon": "month"})
                else:
                    s = Q.series_query(st, src, route or "all", str(d0), str(d0), 0, 23, "hour", a_adj)
                    pts = s["points"]
                    if rng:
                        parts = []
                        for a, b in rng:
                            sel = pts[a:b + 1]
                            tot = sum(p["value"] or 0 for p in sel)
                            s_ = f"{_hr(a, b)}: {kind} {_fmt(tot)} пасс." + (" за час" if a == b else "")
                            if sel and sel[0].get("p10") is not None:
                                s_ += f" (80 % интервал {_fmt(sum(p['p10'] or 0 for p in sel))}–{_fmt(sum(p['p90'] or 0 for p in sel))})"
                            parts.append(s_)
                        text = f"{who}, {_human(d0)}, " + "; ".join(parts) + "."
                    else:
                        sm = s["summary"]
                        text = (f"{who}, {_human(d0)}: {kind} {_fmt(sm['total'])} пасс. за сутки, пик "
                                f"{sm['peak_hour']:02d}:00 — {_fmt(sm['max_hourly'])} пасс./ч.")
                        lo = sum(x["p10"] for x in pts if x.get("p10") is not None)
                        hi = sum(x["p90"] for x in pts if x.get("p90") is not None)
                        if hi:
                            text += f" 80 % интервал на сутки: {_fmt(lo)}–{_fmt(hi)}."
                    if s.get("adjusted") and s.get("delta"):
                        text += f" С учётом условий из вопроса: {s['delta']['pct']:+.1f} % к прогнозу модели.".replace(".", ",", 1)
                    if src == "history":
                        an = Q.anomalies_query(st, route or "all", str(d0), str(d0))
                        items = [f"Аномалия ({e['kind_ru']}, маршрут {e['route']}): {e['label']}" for e in an["events"]]
            if a_adj.active and a_adj is not adj:
                items = [f"Учтено: {x}" for x in a_adj.describe()] + items
    except ApiError as e:
        text, items = e.message, []
    return {"question": q.get("text"), "intent": intent,
            "query": {k: q.get(k) for k in FIELDS} | {"hour_ranges": q.get("hour_ranges") or []},
            "chips": q.get("chips") or [], "fixes": q.get("fixes") or [],
            "parsed": {"route": q.get("route"), "date": q.get("date_from"), "hour": q.get("hour_from")},
            "answer": text, "items": items, "action": action,
            "engine": "правила и шаблоны по данным сервиса (без внешних LLM)"}
