"""API tests: happy paths + validation errors with Russian messages."""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


def test_health(c):
    r = c.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_routes(c):
    r = c.get("/api/v1/routes").json()
    ids = [x["route"] for x in r["routes"]]
    assert {"1", "7", "11", "12", "17", "25", "26", "28", "50"} <= set(ids)
    r5 = next(x for x in r["routes"] if x["route"] == "5")
    # route 5 is new: forecast from its launch date, no history, stops with coordinates
    assert r5["has_geometry"] is True and r5["has_history"] is False
    if r5["has_data"]:
        assert r5["launch_date"] >= "2025-11-01"
    r17 = next(x for x in r["routes"] if x["route"] == "17")
    assert r17["has_geometry"] is False and "геопривязка" in r17["note"]


@pytest.mark.parametrize("gran,n", [("hour", 24), ("day", 7), ("month", 1)])
def test_forecast_granularity(c, gran, n):
    r = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-11-03", "date_to": "2025-11-09" if gran != "hour" else "2025-11-03", "granularity": gran})
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == n
    assert body["summary"]["total"] > 0


def test_forecast_hour_filter_and_all(c):
    r = c.get("/api/v1/forecast", params={"route": "all", "date_from": "2025-11-11", "date_to": "2025-11-11", "hour_from": 7, "hour_to": 9})
    body = r.json()
    assert [p["hour"] for p in body["points"]] == [7, 8, 9]
    one = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-11-11", "date_to": "2025-11-11", "hour_from": 7, "hour_to": 9}).json()
    assert body["summary"]["total"] > one["summary"]["total"]


def test_history_and_kpi(c):
    h = c.get("/api/v1/history", params={"route": "1", "granularity": "month"}).json()
    assert len(h["points"]) == 10
    k = c.get("/api/v1/kpi", params={"route": "7", "date_from": "2025-11-01", "date_to": "2025-11-30"}).json()
    assert 0 <= k["peak_hour"] <= 23 and k["change_vs_prev_month"]["prev_month"].startswith("октябрь")


def test_stop_map_scenario_explain(c):
    s = c.get("/api/v1/stops", params={"route": "7"}).json()
    assert len(s["stops"]) > 10
    sid = s["stops"][0]["stop_id"]
    st = c.get("/api/v1/forecast/stop", params={"stop_id": sid, "date_from": "2025-11-11", "date_to": "2025-11-11"}).json()
    assert st["estimate"] is True and len(st["points"]) == 24
    m = c.get("/api/v1/map", params={"route": "7", "date": "2025-11-11"}).json()
    assert len(m["stops"][0]["values"]) == 24
    y = c.get("/api/v1/scenario/year", params={"route": "7", "growth": 5}).json()
    assert y["scenario"] is True and len(y["months"]) == 12
    e = c.get("/api/v1/explain", params={"route": "7", "date": "2025-11-11"})
    assert e.status_code in (200, 404)


def test_export(c):
    r = c.get("/api/v1/export", params={"format": "csv", "route": "7", "granularity": "day"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "Маршрут;Дата" in r.content.decode("utf-8-sig").splitlines()[0]
    x = c.get("/api/v1/export", params={"format": "xlsx", "route": "all", "granularity": "month"})
    assert x.status_code == 200 and x.content[:2] == b"PK"


@pytest.mark.parametrize("params,status,code,needle", [
    ({"route": "99"}, 404, "route_not_found", "не найден"),
    ({"hour_from": "abc"}, 422, "validation_error", "целым числом"),
    ({"hour_to": 25}, 422, "validation_error", "не больше 23"),
    ({"granularity": "week"}, 422, "validation_error", "Недопустимое значение"),
    ({"date_from": "2025-13-01"}, 400, "invalid_date", "ГГГГ-ММ-ДД"),
    ({"date_from": "2025-05-01", "date_to": "2025-05-02"}, 400, "out_of_range", "доступны только"),
    ({"date_from": "2025-11-10", "date_to": "2025-11-01"}, 400, "invalid_period", "раньше"),
    ({"hour_from": 10, "hour_to": 5}, 400, "invalid_hours", "меньше"),
])
def test_forecast_errors(c, params, status, code, needle):
    r = c.get("/api/v1/forecast", params=params)
    assert r.status_code == status
    err = r.json()["error"]
    assert err["code"] == code and needle in err["message"]


def test_new_route_without_history(c):
    r = c.get("/api/v1/history", params={"route": "5"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_history_for_route"
    y5 = c.get("/api/v1/scenario/year", params={"route": "5"}).json()  # new route: network seasonality
    assert y5["notes"] and y5["total"] > 0
    f = c.get("/api/v1/forecast", params={"route": "5", "date_from": "2025-12-20", "date_to": "2025-12-20"}).json()
    assert f["summary"]["total"] > 0


def test_explain_factors(c):
    e = c.get("/api/v1/explain", params={"route": "7", "date": "2025-12-01"})
    if e.status_code == 200 and e.json()["available"]:
        body = e.json()
        h = body["hours"][8]
        assert abs(h["prediction_recomputed"] - h.get("prediction", h["prediction_recomputed"])) < 1.0
        assert body["daily"]["prediction"] > 0


def test_misc_errors(c):
    assert c.get("/api/v1/forecast/stop", params={"stop_id": "nope"}).status_code == 404
    r = c.get("/api/v1/forecast/stop")
    assert r.status_code == 422 and "stop_id" in r.json()["error"]["message"]
    assert c.get("/api/v1/export", params={"format": "pdf"}).status_code == 422
    r = c.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["error"]["message"] == "Ресурс не найден"


def test_pipeline_report(c):
    r = c.get("/api/v1/pipeline/report")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.json()["ingest"]["raw_rows"] > 0


# ---------------- round 2: corrections, fleet, year ----------------
Q = {"route": "7", "date_from": "2025-12-01", "date_to": "2025-12-07", "granularity": "day"}


def test_corrections_default_is_model(c):
    base = c.get("/api/v1/forecast", params=Q).json()
    same = c.get("/api/v1/forecast", params={**Q, "w_precip": -0.011, "w_cold": -0.034, "k_special": 1}).json()
    assert same["adjusted"] is False and same["summary"]["total"] == base["summary"]["total"]


def test_corrections_level_event_weather(c):
    base = c.get("/api/v1/forecast", params=Q).json()["summary"]["total"]
    up = c.get("/api/v1/forecast", params={**Q, "k_level": "1.1"}).json()
    assert up["adjusted"] and abs(up["delta"]["pct"] - 10) < 0.01 and up["delta"]["total_before"] == base
    assert len(up["baseline"]["values"]) == len(up["points"])
    closed = c.get("/api/v1/forecast", params={**Q, "k_event": "7:2025-12-01:2025-12-07:0"}).json()
    assert closed["summary"]["total"] == 0
    other = c.get("/api/v1/forecast", params={**Q, "k_level": "11:1.5"}).json()
    assert other["delta"]["abs"] == 0  # another route's multiplier does not touch route 7
    rain = c.get("/api/v1/forecast", params={**Q, "w_scenario": "2025-12-03:10:-15"}).json()
    assert rain["delta"]["pct"] < 0
    hist = c.get("/api/v1/history", params={"route": "7", "date_from": "2025-10-01", "date_to": "2025-10-07",
                                            "k_level": "2"}).json()
    assert hist["adjusted"] is False  # actuals are never corrected
    k = c.get("/api/v1/kpi", params={**Q, "k_level": "0.9"}).json()
    assert k["delta"]["pct"] == -10.0


@pytest.mark.parametrize("params,needle", [
    ({"k_level": "abc"}, "Некорректное число"),
    ({"k_level": "99:1.1"}, "не найден"),
    ({"k_event": "7:2025-12-01"}, "формат"),
    ({"k_event": "7:2025-12-07:2025-12-01:0"}, "раньше"),
    ({"w_scenario": "2025-12-01"}, "формат"),
])
def test_corrections_errors(c, params, needle):
    r = c.get("/api/v1/forecast", params={**Q, **params})
    assert r.status_code == 400 and needle in r.json()["error"]["message"]


def test_fleet(c):
    r = c.get("/api/v1/fleet", params={"route": "7", "date": "2025-12-10"}).json()
    f = r["routes"][0]
    assert len(f["hours"]) == 24 and f["peak_required"] > 0 and "formula" in r["assumptions"]
    assert all(h["status"] in ("none", "ok", "risk", "surplus") for h in f["hours"])
    more = c.get("/api/v1/fleet", params={"route": "7", "date": "2025-12-10", "k_level": "1.3"}).json()
    assert more["routes"][0]["peak_required"] > f["peak_required"]
    assert any(x["type"] == "risk" and "+" in x["text"] for x in more["recommendations"])
    assert c.get("/api/v1/fleet", params={"route": "7", "load_target": 5}).status_code == 422


def test_year_and_weather(c):
    y = c.get("/api/v1/scenario/year", params={"route": "all", "band": 10}).json()
    m = y["months"][0]
    assert y["label"] == "сценарный прогноз" and len(y["months"]) == 12 and y["scenario_year"] == 2026
    assert m["low"] < m["forecast_total"] < m["high"]
    w = c.get("/api/v1/weather", params={"date_from": "2025-12-03", "date_to": "2025-12-03",
                                         "w_scenario": "2025-12-03:10:-15"}).json()
    assert w["days"][0]["weather_mult"] < w["days"][0]["weather_mult_model"]


def test_export_with_corrections_and_scenario(c):
    r = c.get("/api/v1/export", params={**Q, "format": "csv", "k_level": "1.1"})
    head = r.content.decode("utf-8-sig").splitlines()[0]
    assert "с коррекцией" in head and "Прогноз модели" in head
    s = c.get("/api/v1/export", params={"format": "csv", "source": "scenario", "route": "7"})
    assert s.status_code == 200 and "Сценарный прогноз" in s.content.decode("utf-8-sig")


def test_index_versioned_assets(c):
    r = c.get("/")
    assert r.status_code == 200 and "/static/app.js?v=" in r.text and "/static/style.css?v=" in r.text
    assert r.headers["cache-control"] == "no-cache"
