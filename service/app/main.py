"""FastAPI app: REST API /api/v1 + static dashboard."""
from __future__ import annotations

import csv
import io
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Literal

import orjson
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import adjust, assistant, config, errors, metrics, queries, store
from .errors import ApiError

TAGS = [
    {"name": "Справочники", "description": "Маршруты и остановки"},
    {"name": "Прогноз", "description": "Прогноз пассажиропотока (ноябрь–декабрь 2025)"},
    {"name": "Факт", "description": "Фактический пассажиропоток (январь–октябрь 2025)"},
    {"name": "Аналитика", "description": "KPI, сценарий на год, объяснение прогноза"},
    {"name": "ИИ / ML", "description": "Интервалы прогноза, ИИ-детектор аномалий, гибридная модель, помощник диспетчера"},
    {"name": "Экспорт", "description": "Выгрузка CSV / XLSX"},
    {"name": "Сервис", "description": "Здоровье и метрики"},
]

@asynccontextmanager
async def lifespan(_app):
    store.get()  # load data into memory before serving
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Прогноз загрузки трамвайных маршрутов Москвы",
    description="API прогноза пассажиропотока по маршрутам и остановкам. Все ошибки возвращаются в JSON "
                "вида `{\"error\": {\"code\", \"message\", \"details\"}}` с понятным сообщением на русском.",
    version="1.0.0",
    default_response_class=ORJSONResponse,
    openapi_tags=TAGS,
)
errors.install(app)
app.add_middleware(GZipMiddleware, minimum_size=2048)
app.add_middleware(metrics.MetricsMiddleware)

Gran = Literal["hour", "day", "month"]
Src = Literal["history", "forecast", "combined"]
HF = Query(0, ge=0, le=23, description="Час начала (0–23)")
HT = Query(23, ge=0, le=23, description="Час окончания (0–23), включительно")
DF = Query(None, description="Дата начала ГГГГ-ММ-ДД", examples=["2025-11-03"])
DT = Query(None, description="Дата окончания ГГГГ-ММ-ДД (включительно)", examples=["2025-11-09"])
RT = Query("all", description="Номер маршрута, список через запятую или all", examples=["7"])


def _json(obj) -> Response:
    return Response(orjson.dumps(obj), media_type="application/json")


AdjDesc = {
    "k_level": "Множитель уровня/сезона: «1.02» (все маршруты) или «7:1.05,11:0.97» (по маршрутам)",
    "k_special": "Сила эффекта особых дней (праздники/переносы): 1 — как в модели, 0 — не учитывать",
    "w_precip": "Эффект осадков на 1 мм за 06–21 ч (модель: −0.011 = −1,1 %/мм)",
    "w_cold": "Эффект морозного дня, средняя t < −10 °C (модель: −0.034 = −3,4 %)",
    "w_floor": "Нижняя граница погодного множителя (модель: 0.9)",
    "w_scenario": "Сценарий погоды «дата:+мм[:температура]», несколько через «;», например 2025-12-10:10:-15",
    "k_event": "События «маршрут|all:с:по:множитель[:час-час]», несколько через «;», например 7:2025-12-01:2025-12-07:0",
    "k_traffic": "Пробки ЦОДД (баллы 0–10): «ГГГГ-ММ-ДД:балл», несколько через «;», или actual — фактические посты ЦОДД за ноябрь–декабрь",
    "w_traffic": "Эффект пробок на пассажиров трамвая на 1 балл выше нормы 3 недель (подтверждено: +0.007 = +0,7 %/балл)",
    "model": "Модель прогноза: v08 (структурная) или hybrid (структурная × поправка LightGBM, если загружен hybrid_nov_dec.csv)",
}


@lru_cache(maxsize=1024)
def _parse_adj(*args) -> adjust.Adj:
    return adjust.parse(store.get(), *args)


def get_adj(k_level: str | None = Query(None, description=AdjDesc["k_level"], examples=["1.02"]),
            k_special: float = Query(1.0, ge=0, le=3, description=AdjDesc["k_special"]),
            w_precip: float = Query(adjust.DEF_PRECIP, ge=-0.2, le=0.2, description=AdjDesc["w_precip"]),
            w_cold: float = Query(adjust.DEF_COLD, ge=-0.5, le=0.5, description=AdjDesc["w_cold"]),
            w_floor: float = Query(adjust.DEF_FLOOR, ge=0.3, le=1.0, description=AdjDesc["w_floor"]),
            w_scenario: str | None = Query(None, description=AdjDesc["w_scenario"]),
            k_event: str | None = Query(None, description=AdjDesc["k_event"]),
            model: Literal["v08", "hybrid"] = Query("v08", description=AdjDesc["model"]),
            k_traffic: str | None = Query(None, description=AdjDesc["k_traffic"]),
            w_traffic: float = Query(adjust.DEF_TRAFFIC, ge=0, le=0.05, description=AdjDesc["w_traffic"])) -> adjust.Adj:
    return _parse_adj(k_level, k_special, w_precip, w_cold, w_floor, w_scenario, k_event, model, k_traffic, w_traffic)


ADJ = Annotated[adjust.Adj, Depends(get_adj)]


@lru_cache(maxsize=config.CACHE_SIZE)
def _cached(kind: str, *args) -> bytes:
    """Cache serialized responses: data is immutable after startup, so this is always safe
    (corrections are part of the key: Adj is a frozen dataclass)."""
    st = store.get()
    fn = {
        "series": queries.series_query, "stop": queries.stop_query, "routes": queries.routes_query,
        "stops": queries.stops_query, "map": queries.map_query, "kpi": queries.kpi_query,
        "year": queries.year_scenario, "explain": queries.explain_query, "fleet": queries.fleet_query,
        "weather": queries.weather_query, "traffic": queries.traffic_query, "anomalies": queries.anomalies_query, "model": queries.model_query,
        "assistant": assistant.answer,
    }[kind]
    return orjson.dumps(fn(st, *args))


def _cached_response(kind: str, *args) -> Response:
    return Response(_cached(kind, *args), media_type="application/json")


# ---------------- reference ----------------
@app.get("/api/v1/routes", tags=["Справочники"], summary="Список маршрутов (10 целевых)")
def routes():
    return _cached_response("routes")


@app.get("/api/v1/stops", tags=["Справочники"], summary="Остановки маршрута с координатами")
def stops(route: str = Query("all", description="Номер маршрута или all")):
    return _cached_response("stops", route)


# ---------------- forecast / history ----------------
@app.get("/api/v1/forecast", tags=["Прогноз"], summary="Прогноз по маршруту (час / день / месяц), с коррекцией")
def forecast(adj: ADJ, route: str = RT, date_from: str | None = DF, date_to: str | None = DT,
             hour_from: int = HF, hour_to: int = HT, granularity: Gran = "hour"):
    return _cached_response("series", "forecast", route, date_from, date_to, hour_from, hour_to, granularity, adj)


@app.get("/api/v1/history", tags=["Факт"], summary="Фактический пассажиропоток (январь–октябрь 2025)")
def history(route: str = RT, date_from: str | None = DF, date_to: str | None = DT,
            hour_from: int = HF, hour_to: int = HT, granularity: Gran = "day"):
    return _cached_response("series", "history", route, date_from, date_to, hour_from, hour_to, granularity,
                            adjust.NO_ADJ)


@app.get("/api/v1/series", tags=["Прогноз"], summary="Единый ряд: факт, прогноз или факт+прогноз")
def series(adj: ADJ, source: Src = "combined", route: str = RT, date_from: str | None = DF, date_to: str | None = DT,
           hour_from: int = HF, hour_to: int = HT, granularity: Gran = "day"):
    return _cached_response("series", source, route, date_from, date_to, hour_from, hour_to, granularity, adj)


@app.get("/api/v1/forecast/stop", tags=["Прогноз"], summary="Оценка прогноза по остановке")
def forecast_stop(adj: ADJ, stop_id: str = Query(..., description="ID остановки из /stops"), source: Src = "forecast",
                  date_from: str | None = DF, date_to: str | None = DT,
                  hour_from: int = HF, hour_to: int = HT, granularity: Gran = "hour"):
    return _cached_response("stop", stop_id, source, date_from, date_to, hour_from, hour_to, granularity, adj)


@app.get("/api/v1/map", tags=["Прогноз"], summary="Слой карты: оценка по остановкам на 24 часа выбранной даты")
def map_layer(adj: ADJ, route: str = Query("all"), date: str | None = Query(None, description="ГГГГ-ММ-ДД"),
              source: Src = "forecast"):
    return _cached_response("map", route, date, source, adj)


# ---------------- analytics ----------------
@app.get("/api/v1/kpi", tags=["Аналитика"], summary="KPI: пиковый час, максимум, изменение к прошлому месяцу")
def kpi(adj: ADJ, route: str = RT, date_from: str | None = DF, date_to: str | None = DT,
        hour_from: int = HF, hour_to: int = HT, source: Src = "forecast"):
    return _cached_response("kpi", route, date_from, date_to, hour_from, hour_to, source, adj)


@app.get("/api/v1/scenario/year", tags=["Аналитика"], summary="Сценарный прогноз на год по месяцам (с коридором)")
def scenario_year(adj: ADJ, route: str = RT,
                  growth: float = Query(0.0, ge=-50, le=50, description="Рост к уровню 2025, %"),
                  band: float = Query(10.0, ge=0, le=50, description="Коридор неопределённости ±, %")):
    return _cached_response("year", route, round(growth, 2), round(band, 2), adj)


@app.get("/api/v1/weather", tags=["Аналитика"], summary="Погода по дням и погодный множитель (модель / с коррекцией)")
def weather(adj: ADJ, date_from: str | None = DF, date_to: str | None = DT):
    return _cached_response("weather", date_from, date_to, adj)


@app.get("/api/v1/traffic", tags=["Аналитика"], summary="Пробки ЦОДД по дням: балл 0–10, норма 3 недель, множитель")
def traffic(adj: ADJ, date_from: str | None = DF, date_to: str | None = DT):
    return _cached_response("traffic", date_from, date_to, adj)


@lru_cache(maxsize=1)
def _traffic_live() -> bytes | None:
    p = config.DATA_DIR / "traffic_live.json"
    return p.read_bytes() if p.is_file() else None


@app.get("/api/v1/traffic/live", tags=["Аналитика"],
         summary="Живой слой пробок TomTom у остановок (если scripts/fetch_traffic.py отработал с рабочим ключом)")
def traffic_live():
    data = _traffic_live()
    if data is None:
        return _json({"available": False, "message": "Живой слой TomTom не настроен: нет рабочего ключа TOMTOM_API_KEY "
                                                     "или scripts/fetch_traffic.py ещё не запускался", "points": []})
    return Response(data, media_type="application/json")


@app.get("/api/v1/fleet", tags=["Аналитика"], summary="Выпуск подвижного состава: потребность в вагонах по часам")
def fleet(adj: ADJ, route: str = RT, date: str | None = Query(None, description="ГГГГ-ММ-ДД"),
          capacity: int | None = Query(None, ge=50, le=400, description="Вместимость вагона, пасс. (по умолчанию из наряда)"),
          load_target: float = Query(0.8, ge=0.3, le=1.2, description="Целевая загрузка (доля вместимости)"),
          peak_share: float = Query(0.6, ge=0.5, le=1.0, description="Доля пикового направления"),
          turnover: float = Query(1.5, ge=1.0, le=5.0, description="Коэффициент сменяемости пассажиров"),
          speed: float | None = Query(None, ge=5, le=40, description="Эксплуатационная скорость, км/ч"),
          layover: float = Query(10.0, ge=0, le=60, description="Отстой на конечных за оборот, мин"),
          max_headway: float = Query(20.0, ge=3, le=60, description="Максимальный интервал движения, мин"),
          plan: int | None = Query(None, ge=0, le=200, description="Плановый выпуск (вагонов в час), если известен"),
          min_boardings: float = Query(30.0, ge=0, le=500, description="Порог входов в час, ниже которого регулярное движение не требуется"),
          plan_by: Literal["p50", "p90"] = Query("p50", description="Планировать по медиане прогноза (p50) или по P90 (с запасом)")):
    return _cached_response("fleet", route, date, adj, capacity, round(load_target, 3), round(peak_share, 3),
                            round(turnover, 3), speed, round(layover, 1), round(max_headway, 1), plan,
                            round(min_boardings, 1), plan_by)


@app.get("/api/v1/explain", tags=["Аналитика"], summary="Декомпозиция прогноза (base × множители)")
def explain(route: str = Query(..., description="Номер маршрута"), date: str = Query(..., description="ГГГГ-ММ-ДД")):
    return _cached_response("explain", route, date)


# ---------------- AI / ML ----------------
@app.get("/api/v1/anomalies", tags=["ИИ / ML"], summary="ИИ-детектор аномалий: аномальные дни истории с причиной")
def anomalies(route: str = RT, date_from: str | None = DF, date_to: str | None = DT,
              kind: Literal["drop", "spike", "shape"] | None = Query(None, description="drop — провал, spike — всплеск, shape — аномальный профиль")):
    return _cached_response("anomalies", route, date_from, date_to, kind)


@app.get("/api/v1/model", tags=["ИИ / ML"], summary="Модель: гибрид, метрики по фолдам, внешние источники, факторы")
def model_info():
    return _cached_response("model")


@app.get("/api/v1/assistant", tags=["ИИ / ML"], summary="Помощник диспетчера: ответ на вопрос по данным (правила, без LLM)")
def assistant_q(adj: ADJ, q: str = Query("", max_length=300, description="Вопрос, например «сколько вагонов нужно на 17 маршруте в 8 утра?»"),
                ref_date: str | None = Query(None, description="«Сегодня» для слов завтра/сегодня, ГГГГ-ММ-ДД (по умолчанию — начало прогноза)"),
                plan_by: Literal["p50", "p90"] = "p50"):
    st = store.get()
    ref = queries.parse_date(ref_date, "ref_date") or st.coverage["forecast"][0]
    return _cached_response("assistant", q.strip(), ref, adj, plan_by)


class AssistantQuery(BaseModel):
    """Structured query. Every field is optional: the dispatcher edits the recognised parameters and re-asks."""
    route: str | None = Field(None, max_length=10, description="номер маршрута или all")
    date_from: str | None = Field(None, description="ГГГГ-ММ-ДД")
    date_to: str | None = Field(None, description="ГГГГ-ММ-ДД")
    hour_from: int | None = Field(None, ge=0, le=23)
    hour_to: int | None = Field(None, ge=0, le=23)
    hour_ranges: list[list[int]] | None = Field(None, max_length=4, description="[[7, 9], [16, 19]]: 07–10 и 16–20")
    granularity: Literal["hour", "day", "month"] | None = None
    intent: Literal["help", "overflow", "vehicles", "load", "peak", "anomalies", "model"] | None = None
    corrections: dict[str, str] | None = Field(None, description="k_level, k_event, w_scenario, k_traffic (формат как в API)")


class AssistantRequest(BaseModel):
    text: str = Field("", max_length=300, description="Вопрос диспетчера свободным текстом")
    ref_date: str | None = Field(None, description="«Сегодня» для слов завтра/сегодня (по умолчанию — начало прогноза)")
    plan_by: Literal["p50", "p90"] = "p50"
    query: AssistantQuery | None = Field(None, description="Подтверждённые / исправленные параметры (вместо разбора текста)")


def _assistant_q(st, q: dict) -> dict:
    """Validate an edited structured query (dates, hours) with the same Russian errors as the rest of the API."""
    for k in ("date_from", "date_to"):
        if q.get(k):
            q[k] = str(queries.parse_date(q[k], k))
    if q.get("date_from") and not q.get("date_to"):
        q["date_to"] = q["date_from"]
    if q.get("date_from") and q["date_to"] < q["date_from"]:
        raise ApiError(400, "invalid_period", f"Дата окончания ({q['date_to']}) раньше даты начала ({q['date_from']})")
    rng = q.get("hour_ranges") or ([[q["hour_from"], q.get("hour_to", q["hour_from"])]] if q.get("hour_from") is not None else [])
    for r in rng:
        if len(r) != 2 or not (0 <= r[0] <= r[1] <= 23):
            raise ApiError(400, "invalid_hours", "Часы: от 0 до 23, начало не позже конца")
    q["hour_ranges"] = rng
    if rng:
        q["hour_from"], q["hour_to"] = min(r[0] for r in rng), max(r[1] for r in rng)
    if q.get("corrections"):
        c = q["corrections"]
        adjust.parse(st, c.get("k_level"), 1.0, adjust.DEF_PRECIP, adjust.DEF_COLD, adjust.DEF_FLOOR,
                     c.get("w_scenario"), c.get("k_event"), "v08", c.get("k_traffic"))  # validation only
    return q


@app.post("/api/v1/assistant/query", tags=["ИИ / ML"],
          summary="Помощник: свободный текст → структурированный запрос (маршрут, даты, часы, коррекции) + ответ")
def assistant_query(adj: ADJ, body: AssistantRequest):
    st = store.get()
    ref = queries.parse_date(body.ref_date, "ref_date") or st.coverage["forecast"][0]
    from .nlq import parse_query

    parsed = parse_query(body.text, ref, st.coverage["combined"][0].year)
    if body.query is not None:
        edited = body.query.model_dump(exclude_none=True)
        if "hour_from" in edited and "hour_ranges" not in edited:
            parsed["hour_ranges"] = []
        parsed.update(edited)
        parsed["chips"] = []
        parsed.pop("date_defaulted", None)
        parsed = _assistant_q(st, parsed)
    return _json(assistant.answer_query(st, parsed, adj, body.plan_by))


@lru_cache(maxsize=1)
def _pipeline_report() -> bytes | None:
    p = config.PIPELINE_REPORT_PATH
    return p.read_bytes() if p.is_file() else None


@app.get("/api/v1/pipeline/report", tags=["Сервис"], summary="Отчёт о качестве данных (конвейер загрузки валидаций)")
def pipeline_report():
    data = _pipeline_report()
    if data is None:
        raise ApiError(404, "report_not_found", "Отчёт о качестве данных не загружен")
    return Response(data, media_type="application/json")


# ---------------- export ----------------
@app.get("/api/v1/export", tags=["Экспорт"], summary="Выгрузка в CSV или XLSX",
         responses={200: {"content": {"text/csv": {}, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}})
def export(adj: ADJ, format: Literal["csv", "xlsx"] = "csv",
           source: Literal["history", "forecast", "combined", "scenario"] = "forecast", route: str = RT,
           date_from: str | None = DF, date_to: str | None = DT, hour_from: int = HF, hour_to: int = HT,
           granularity: Gran = "hour"):
    st = store.get()
    if source == "scenario":
        y = queries.year_scenario(st, route, 0.0, 10.0, adj)
        header = ["Маршрут", "Месяц", "Сценарный прогноз, пасс.", "Нижняя граница", "Верхняя граница",
                  "Средние сутки", "Сезонный индекс"]
        rows = [[route, f"{m['year']}-{m['month']:02d}", m["forecast_total"], m["low"], m["high"],
                 m["forecast_avg_per_day"], m["seasonal_index"]] for m in y["months"]]
    else:
        header, rows = queries.export_rows(st, source, route, date_from, date_to, hour_from, hour_to, granularity, adj)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    fname = f"tram_{source}_{route.replace(',', '-')}_{granularity}_{stamp}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
        data = ("﻿" + buf.getvalue()).encode("utf-8")  # BOM so Excel opens Cyrillic correctly
        return Response(data, media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'})
    import xlsxwriter

    bio = io.BytesIO()
    wb = xlsxwriter.Workbook(bio, {"in_memory": True})
    ws = wb.add_worksheet("Данные")
    bold = wb.add_format({"bold": True, "bg_color": "#E8EEF7", "border": 1})
    ws.write_row(0, 0, header, bold)
    for i, r in enumerate(rows, start=1):
        ws.write_row(i, 0, ["" if v is None else v for v in r])
    ws.set_column(0, len(header) - 1, 18)
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, len(rows), len(header) - 1)
    meta = wb.add_worksheet("Параметры")
    for i, (k, v) in enumerate([("Источник", source), ("Маршрут", route), ("Период", f"{date_from or ''} — {date_to or ''}"),
                                ("Часы", f"{hour_from}–{hour_to}"), ("Гранулярность", granularity),
                                ("Файл прогноза", st.forecast_path.split('/')[-1].split('\\')[-1]),
                                ("Модель", "гибрид ML (структурная × LightGBM)" if adj.model == "hybrid" else "v08 (структурная)"),
                                ("Коррекция", "; ".join(adj.describe()) if adj.active else "нет (прогноз модели)"),
                                ("Сформировано", stamp)]):
        meta.write_row(i, 0, [k, v])
    meta.set_column(0, 1, 28)
    wb.close()
    return Response(bio.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{fname}.xlsx"'})


# ---------------- service ----------------
@app.get("/api/v1/health", tags=["Сервис"], summary="Проверка готовности")
def health():
    st = store.get()
    return _json({"status": "ok", "routes_with_data": len(st.routes), "stops": len(st.stops),
                  "forecast_file": st.forecast_path.replace("\\", "/").split("/")[-1],
                  "data_bundle": _meta(),
                  "explain_loaded": st.explain is not None,
                  "ml": {"intervals": bool(st.ml and st.ml.intervals), "hybrid": bool(st.ml and st.ml.hybrid),
                         "anomalies": len(st.ml.anomalies) if st.ml else 0,
                         "report": bool(st.ml and st.ml.report_md), "errors": st.ml.errors if st.ml else []},
                  "coverage": {k: [str(v[0]), str(v[1])] for k, v in st.coverage.items()}})


@lru_cache(maxsize=1)
def _meta() -> dict:
    p = config.DATA_DIR / "meta.json"
    return orjson.loads(p.read_bytes()) if p.is_file() else {}


@app.get("/api/v1/metrics", tags=["Сервис"], summary="Счётчики запросов (на worker)")
def get_metrics():
    info = _cached.cache_info()
    return _json(metrics.snapshot() | {"cache": {"hits": info.hits, "misses": info.misses, "size": info.currsize}})


@app.get("/health", include_in_schema=False)
def health_root():
    return {"status": "ok"}


# ---------------- frontend ----------------
@lru_cache(maxsize=4)
def _index_html_for(_mtimes: tuple) -> bytes:
    """index.html with versioned asset URLs, so a browser never runs a stale cached app.js against a newer page."""
    import hashlib

    h = hashlib.sha1()
    for name in ("app.js", "style.css"):
        h.update((config.STATIC_DIR / name).read_bytes())
    v = h.hexdigest()[:10]
    html = (config.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    html = html.replace('/static/app.js"', f'/static/app.js?v={v}"').replace('/static/style.css"', f'/static/style.css?v={v}"')
    return html.encode("utf-8")


def _index_html() -> bytes:
    # keyed on the files' mtimes: an edited page is never served with a mismatched cached script version
    return _index_html_for(tuple((config.STATIC_DIR / n).stat().st_mtime_ns for n in ("index.html", "app.js", "style.css")))


@app.get("/", include_in_schema=False)
def index():
    return Response(_index_html(), media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
