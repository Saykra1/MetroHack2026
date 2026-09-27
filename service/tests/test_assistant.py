"""«Помощник диспетчера»: text normalisation → structured query, POST /assistant/query, ЦОДД traffic coefficient."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.nlq import parse_query

REF = date(2025, 12, 10)  # a Wednesday


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("text,exp", [
    ("Где завтра переполнение?", dict(route="all", date_from="2025-12-11", intent="overflow")),
    ("Сколько вагонов нужно на 17 маршруте в 8 утра?", dict(route="17", hour_ranges=[[8, 8]], intent="vehicles")),
    ("сколько вагонов на семерке завтра в вечерний час пик", dict(route="7", date_from="2025-12-11", hour_ranges=[[16, 19]])),
    ("пассажиры на 7-ке 17-го", dict(route="7", date_from="2025-12-17", intent="load")),
    ("загрузка семнадцатого декабря на 11 маршруте ночью", dict(route="11", date_from="2025-12-17", hour_ranges=[[0, 5]])),
    ("пассажиры на 12 маршруте в утренний час пик послезавтра", dict(route="12", date_from="2025-12-12", hour_ranges=[[7, 9]])),
    ("ЧАС ПИК на 1 маршруте в пятницу", dict(route="1", date_from="2025-12-12", hour_ranges=[[7, 9], [16, 19]])),
    ("сколко вагонв на 17 маршрте послезавтра утром", dict(route="17", date_from="2025-12-12", intent="vehicles", hour_ranges=[[6, 11]])),
    ("Пассажиры на маршруте 7 10 декабря в 18:00", dict(route="7", date_from="2025-12-10", hour_ranges=[[18, 18]])),
    ("сколько трамваев надо на №11 12.12 в 7 вечера", dict(route="11", date_from="2025-12-12", hour_ranges=[[19, 19]], intent="vehicles")),
    ("перекрытие на 7 маршруте с 10 по 12 декабря", dict(route="7", date_from="2025-12-10", date_to="2025-12-12", granularity="day")),
    ("на семнадцатом маршруте в декабре", dict(route="17", date_from="2025-12-01", date_to="2025-12-31")),
    ("прогноз на ёлку 31.12 с 16 до 20", dict(date_from="2025-12-31", hour_ranges=[[16, 19]])),
    ("третьего числа на 1 маршруте", dict(route="1", date_from="2025-12-03")),
    ("в следующий понедельник на 25 маршруте", dict(route="25", date_from="2025-12-15")),
    ("семнадцатый трамвай в субботу", dict(route="17", date_from="2025-12-13")),
])
def test_parse_phrasings(text, exp):
    q = parse_query(text, REF, 2025)
    for k, v in exp.items():
        assert q[k] == v, (text, k, q[k])


def test_parse_corrections_and_normalisation():
    q = parse_query("Что будет на 17-ке 12 декабря в час пик, если дождь 10 мм и мороз -15 градусов", REF, 2025)
    assert q["corrections"]["w_scenario"] == "2025-12-12:10:-15"
    q = parse_query("нагрузка на 12 маршруте на 10% больше завтра", REF, 2025)
    assert q["corrections"]["k_level"] == "12:1.1"
    q = parse_query("пробки 8 баллов завтра на 17-ке", REF, 2025)
    assert q["corrections"]["k_traffic"] == "2025-12-11:8"
    q = parse_query("фестиваль на всех маршрутах 20 декабря с 16 до 22", REF, 2025)
    assert q["corrections"]["k_event"] == "all:2025-12-20:2025-12-20:1.2:16-21"
    q = parse_query("ЗАВТРА на маршрутЕ 7 в 8 утра", REF, 2025)
    assert (q["route"], q["date_from"], q["hour_from"]) == ("7", "2025-12-11", 8)
    q = parse_query("в 8 утра на 7 маршруте", REF, 2025)  # no date -> the dashboard's date, flagged
    assert q["date_from"] == "2025-12-10" and q.get("date_defaulted")
    assert any(ch["key"] == "hours" for ch in q["chips"])


def test_post_query_structured(c):
    r = c.post("/api/v1/assistant/query", json={"text": "сколько вагонов на семерке завтра в вечерний час пик",
                                                "ref_date": "2025-12-10"})
    assert r.status_code == 200
    b = r.json()
    q = b["query"]
    assert (q["route"], q["date_from"], q["date_to"], q["hour_from"], q["hour_to"], q["granularity"]) == \
           ("7", "2025-12-11", "2025-12-11", 16, 19, "hour")
    assert b["intent"] == "vehicles" and "Маршрут 7" in b["answer"] and "16:00–20:00" in b["answer"]
    assert {ch["key"] for ch in b["chips"]} >= {"route", "date", "hours"}


def test_post_query_edited_and_errors(c):
    # the dispatcher corrects the recognised route and hours: the edited query wins over the text
    r = c.post("/api/v1/assistant/query", json={"text": "сколько вагонов на семерке завтра",
                                                "query": {"route": "17", "hour_from": 8, "hour_to": 8}}).json()
    assert r["query"]["route"] == "17" and r["query"]["hour_ranges"] == [[8, 8]] and "Маршрут 17" in r["answer"]
    both = c.post("/api/v1/assistant/query", json={"text": "пассажиры на 7 маршруте 11 декабря в час пик"}).json()
    assert "07:00–10:00" in both["answer"] and "16:00–20:00" in both["answer"]
    bad = c.post("/api/v1/assistant/query", json={"text": "x", "query": {"date_from": "2025-12-40"}})
    assert bad.status_code == 400 and "ГГГГ-ММ-ДД" in bad.json()["error"]["message"]
    bad = c.post("/api/v1/assistant/query", json={"text": "x", "query": {"hour_ranges": [[10, 5]]}})
    assert bad.status_code == 400
    assert c.post("/api/v1/assistant/query", json={"text": "x" * 301}).status_code == 422
    nf = c.post("/api/v1/assistant/query", json={"text": "пассажиры на 99 маршруте завтра"}).json()
    assert "не найден" in nf["answer"]


def test_post_query_with_corrections(c):
    r = c.post("/api/v1/assistant/query", json={"text": "пассажиры на 7 маршруте 12 декабря, если перекрытие",
                                                "ref_date": "2025-12-10"}).json()
    assert r["query"]["corrections"]["k_event"].startswith("7:2025-12-12:2025-12-12:0")
    assert "−100" in r["answer"] or "-100" in r["answer"]


def test_traffic_coefficient(c):
    q = {"route": "7", "date_from": "2025-12-11", "date_to": "2025-12-11", "granularity": "day"}
    base = c.get("/api/v1/forecast", params=q).json()["summary"]["total"]
    up = c.get("/api/v1/forecast", params={**q, "k_traffic": "2025-12-11:9"}).json()
    t = c.get("/api/v1/traffic", params={"date_from": "2025-12-11", "date_to": "2025-12-11"}).json()
    day = t["days"][0]
    exp = 1 + 0.007 * (9 - day["norm"])
    assert up["adjusted"] and up["summary"]["total"] == pytest.approx(base * exp, rel=2e-3)
    assert day["source_url"].startswith("https://t.me/DtOperativno/")
    w = c.get("/api/v1/forecast", params={**q, "k_traffic": "2025-12-11:9", "w_traffic": 0.014}).json()
    assert w["delta"]["pct"] == pytest.approx(up["delta"]["pct"] * 2, rel=0.02)
    act = c.get("/api/v1/forecast", params={**q, "k_traffic": "actual"}).json()
    assert act["adjusted"]
    for bad in ("2025-12-11", "2025-12-11:11", "xx:5"):
        r = c.get("/api/v1/forecast", params={**q, "k_traffic": bad})
        assert r.status_code == 400 and "k_traffic" in r.json()["error"]["message"]
    hist = c.get("/api/v1/history", params={"route": "7", "date_from": "2025-10-01", "date_to": "2025-10-01",
                                            "k_traffic": "2025-10-01:9"}).json()
    assert hist["adjusted"] is False


def test_fetch_traffic_script(tmp_path, monkeypatch, capsys):
    import importlib.util
    import io
    import json
    import urllib.error

    spec = importlib.util.spec_from_file_location("fetch_traffic", "scripts/fetch_traffic.py")
    ft = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ft)
    (tmp_path / "stops.json").write_text(json.dumps([{"stop_id": "1", "name": "A", "route": "7", "lat": 55.7, "lon": 37.6},
                                                     {"stop_id": "2", "name": "B", "route": "7", "lat": 55.8, "lon": 37.5}]),
                                         encoding="utf-8")
    monkeypatch.setattr(ft, "DATA", tmp_path)
    monkeypatch.setattr(ft, "SERVICE", tmp_path)  # no .env there
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["fetch_traffic.py", "--pause", "0"])
    assert ft.main() == 2  # no key
    monkeypatch.setenv("TOMTOM_API_KEY", "SECRET-TEST-KEY")

    def unauthorized(*a, **k):
        raise urllib.error.HTTPError("https://api.tomtom.com/x", 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(ft, "fetch", unauthorized)
    assert ft.main() == 2 and not (tmp_path / "traffic_live.json").exists()
    out = capsys.readouterr().out
    assert "401" in out and "SECRET-TEST-KEY" not in out  # the key is never printed
    monkeypatch.setattr(ft, "fetch", lambda p, k, z: {"currentSpeed": 18, "freeFlowSpeed": 36, "confidence": 0.9})
    assert ft.main() == 0
    live = json.loads((tmp_path / "traffic_live.json").read_text(encoding="utf-8"))
    assert live["available"] and live["points"][0]["ratio"] == 0.5 and "SECRET" not in json.dumps(live)


def test_traffic_live_endpoint_absent(c):
    r = c.get("/api/v1/traffic/live").json()
    assert r["available"] in (True, False) and isinstance(r["points"], list)
