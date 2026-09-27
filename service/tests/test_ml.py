"""AI/ML layer tests on small synthetic fixtures (the real ML files may or may not be in data/)."""
from datetime import date

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import assistant, config, main, ml, store
from app.main import app

REPORT = """# ML report

Гибрид: структурная модель × поправка LightGBM. Интервалы — квантильная регрессия.

## Метрики по фолдам

| fold | период | v08 | hybrid |
|---|---|---|---|
| 1 | 2025-08 | 0.881 | 0.893 |
| 2 | 2025-09 | 0.874 | 0.889 |

## Другое

| a | b |
|---|---|
| x | y |
"""


def _reset(st):
    main._cached.cache_clear()
    main._parse_adj.cache_clear()


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def synth(tmp_path_factory, c):
    """Write synthetic intervals / hybrid / anomalies / report and attach them to the running store."""
    st = store.get()
    d = tmp_path_factory.mktemp("ml")
    fc = st.cubes["forecast"]
    a, b = st.coverage["forecast"]
    rows = []
    for r in ("7", "17"):
        ri = st.route_idx[r]
        for i in range(st.day_index(a), st.day_index(b) + 1):
            day = st.day_at(i).isoformat()
            for h in range(24):
                v = float(fc[ri, i, h])
                rows.append((r, day, h, v * 0.8, v, v * 1.3))
    pd.DataFrame(rows, columns=["route", "date", "hour", "p10", "p50", "p90"]).to_csv(d / "intervals.csv", sep=";", index=False)
    hyb = [(r, dd, h, p50, 1.05, p50 * 1.05) for r, dd, h, _, p50, _ in rows if r == "7"]
    pd.DataFrame(hyb, columns=["route", "date", "hour", "base", "ml_ratio", "prediction"]).to_csv(d / "hybrid.csv", sep=";", index=False)
    pd.DataFrame([("7", "2025-05-09", 3.1, "drop", "День Победы: перекрытия"),
                  ("7", "2025-03-15", 2.2, "spike", "событие у метро"),
                  ("11", "2025-06-01", 1.5, "shape", "")],
                 columns=["route", "date", "score", "kind", "label"]).to_csv(d / "anomalies.csv", sep=";", index=False)
    (d / "report.md").write_text(REPORT, encoding="utf-8")
    saved = (config.INTERVALS_PATH, config.HYBRID_PATH, config.ANOMALIES_PATH, config.MODEL_REPORT_PATH)
    config.INTERVALS_PATH, config.HYBRID_PATH = d / "intervals.csv", d / "hybrid.csv"
    config.ANOMALIES_PATH, config.MODEL_REPORT_PATH = d / "anomalies.csv", d / "report.md"
    ml.detach(st)
    st.ml = ml.load(st)
    _reset(st)
    yield st
    config.INTERVALS_PATH, config.HYBRID_PATH, config.ANOMALIES_PATH, config.MODEL_REPORT_PATH = saved
    ml.detach(st)
    st.ml = ml.load(st)
    _reset(st)


def test_p_exceed_lognormal():
    # median 100, p90 = 130: P(X > 130) = 10 %, P(X > 100) = 50 %, P(X > 80) = 90 %
    assert abs(ml.p_exceed(100, 0.8, 1.3, 130) - 0.10) < 1e-6
    assert abs(ml.p_exceed(100, 0.8, 1.3, 100) - 0.50) < 1e-6
    assert abs(ml.p_exceed(100, 0.8, 1.3, 80) - 0.90) < 1e-6
    assert ml.p_exceed(0, 0.8, 1.3, 10) == 0.0
    assert abs(ml.p_exceed(100, 0.0, 1.3, 100 / 1.3) - 0.90) < 1e-6  # p10 = 0 -> symmetric fallback
    assert ml.p_exceed(100, 1.0, 1.0, 120) == 0.0 and ml.p_exceed(100, 1.0, 1.0, 90) == 1.0


def test_md_tables():
    t = ml.parse_md_tables(REPORT)
    assert len(t) == 2 and t[0]["header"] == ["fold", "период", "v08", "hybrid"] and len(t[0]["rows"]) == 2
    assert ml.pick_fold_table(t) == 0 and t[0]["heading"] == "Метрики по фолдам"


def test_intervals_in_series(c, synth):
    r = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-12-10", "date_to": "2025-12-10"}).json()
    p = r["points"][8]
    assert r["interval"]["level"] == 0.8
    assert p["p10"] == pytest.approx(p["value"] * 0.8, rel=1e-3) and p["p90"] == pytest.approx(p["value"] * 1.3, rel=1e-3)
    day = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-12-01", "date_to": "2025-12-07",
                                            "granularity": "day", "k_level": "1.1"}).json()
    assert day["points"][0]["p90"] == pytest.approx(day["points"][0]["value"] * 1.3, rel=1e-3)  # band follows corrections
    mon = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-12-01", "date_to": "2025-12-31",
                                            "granularity": "month"}).json()["points"][0]
    assert mon["p10"] < mon["value"] < mon["p90"] < mon["value"] * 1.3  # days independent -> narrower than hourly
    # route without intervals: zero-width band; actual days: no band
    r11 = c.get("/api/v1/forecast", params={"route": "11", "date_from": "2025-12-10", "date_to": "2025-12-10"}).json()
    assert r11["points"][8]["p10"] == r11["points"][8]["value"]
    ex = c.get("/api/v1/export", params={"format": "csv", "route": "7", "date_from": "2025-12-10", "date_to": "2025-12-10"})
    lines = ex.content.decode("utf-8-sig").splitlines()
    assert "P90 (80 % интервал)" in lines[0] and len(lines[9].split(";")) == 6
    comb = c.get("/api/v1/series", params={"route": "7", "source": "combined", "date_from": "2025-10-30",
                                           "date_to": "2025-11-02", "granularity": "day"}).json()
    assert comb["points"][0]["p10"] is None and comb["points"][-1]["p10"] is not None


def test_fleet_overflow_and_p90(c, synth):
    q = {"route": "17", "date": "2025-12-10"}
    r = c.get("/api/v1/fleet", params=q).json()
    assert r["overflow"]["available"] and 0 <= r["overflow"]["max"] <= 1
    hrs = r["routes"][0]["hours"]
    assert all(h["p_overflow"] is None or 0 <= h["p_overflow"] <= 1 for h in hrs)
    assert hrs[8]["boardings_p90"] == pytest.approx(hrs[8]["boardings"] * 1.3, rel=1e-2)
    p90 = c.get("/api/v1/fleet", params={**q, "plan_by": "p90"}).json()
    assert p90["plan_by"] == "p90"
    assert p90["routes"][0]["peak_required"] >= r["routes"][0]["peak_required"]
    assert sum(h["required"] for h in p90["routes"][0]["hours"]) > sum(h["required"] for h in hrs)
    # more demand -> higher overflow probability
    up = c.get("/api/v1/fleet", params={**q, "k_level": "1.3"}).json()
    assert up["overflow"]["max"] >= r["overflow"]["max"]
    hist = c.get("/api/v1/fleet", params={"route": "17", "date": "2025-10-10"}).json()
    assert hist["overflow"]["available"] is False


def test_hybrid_toggle(c, synth):
    q = {"route": "7", "date_from": "2025-12-01", "date_to": "2025-12-07", "granularity": "day"}
    v08 = c.get("/api/v1/forecast", params=q).json()
    hyb = c.get("/api/v1/forecast", params={**q, "model": "hybrid"}).json()
    assert hyb["model"] == "hybrid" and hyb["adjusted"] is False
    assert hyb["summary"]["total"] == pytest.approx(v08["summary"]["total"] * 1.05, rel=1e-3)
    both = c.get("/api/v1/forecast", params={**q, "model": "hybrid", "k_level": "1.1"}).json()
    assert both["delta"]["total_before"] == pytest.approx(hyb["summary"]["total"], rel=1e-4)  # baseline = same model
    r11 = c.get("/api/v1/forecast", params={**q, "route": "11", "model": "hybrid"}).json()  # not in file -> v08
    assert r11["summary"]["total"] == c.get("/api/v1/forecast", params={**q, "route": "11"}).json()["summary"]["total"]
    e = c.get("/api/v1/explain", params={"route": "7", "date": "2025-12-03"}).json()
    if e.get("available"):
        assert e["hours"][8]["ml_ratio"] == pytest.approx(1.05)
    assert c.get("/api/v1/forecast", params={**q, "model": "gbm"}).status_code == 422


def test_anomalies(c, synth):
    r = c.get("/api/v1/anomalies", params={"route": "7"}).json()
    assert r["available"] and r["count"] == 2 and r["by_kind"] == {"spike": 1, "drop": 1}
    e = next(x for x in r["events"] if x["kind"] == "drop")
    assert e["kind_ru"] == "провал" and "Победы" in e["label"] and e["actual_total"] is not None
    one = c.get("/api/v1/anomalies", params={"route": "all", "date_from": "2025-06-01", "date_to": "2025-06-30"}).json()
    assert one["count"] == 1 and one["events"][0]["label"] == "причина не установлена"
    assert c.get("/api/v1/anomalies", params={"route": "all", "kind": "drop"}).json()["count"] == 1
    assert ml.ru_label("repairs: route 50 weekends (Sep-Nov 14)") == "ремонт: маршрут 50, выходные, сентябрь – 14 ноября"
    assert ml.ru_label("holiday weekend") == "праздничные выходные" and ml.ru_label("new text") == "new text"
    assert c.get("/api/v1/anomalies", params={"route": "99"}).status_code == 404
    bad = c.get("/api/v1/anomalies", params={"date_from": "2025-06-10", "date_to": "2025-06-01"})
    assert bad.status_code == 400 and "раньше" in bad.json()["error"]["message"]


def test_model_info(c, synth):
    m = c.get("/api/v1/model").json()
    assert m["hybrid_available"] and m["intervals_available"] and m["report_available"]
    assert m["fold_table"] == 0 and m["tables"][0]["rows"][1][3] == "0.889"
    assert any("ЦОДД" in s["name"] for s in m["sources"]) and all(s["url"].startswith("https://") for s in m["sources"])
    assert m["hybrid_compare"]["pct"] > 0
    h = c.get("/api/v1/health").json()
    assert h["ml"]["intervals"] and h["ml"]["hybrid"] and h["ml"]["anomalies"] == 3


def test_ml_absent_degrades(c, synth):
    st = store.get()
    saved = (st.ml, st.cubes.pop("forecast_hybrid"), st.cubes.pop("combined_hybrid"))
    st.ml = ml.MLData()
    _reset(st)
    try:
        f = c.get("/api/v1/forecast", params={"route": "7", "date_from": "2025-12-10", "date_to": "2025-12-10"}).json()
        assert "interval" not in f and "p10" not in f["points"][0]
        assert c.get("/api/v1/fleet", params={"route": "7", "date": "2025-12-10"}).json()["overflow"]["available"] is False
        a = c.get("/api/v1/anomalies").json()
        assert a["available"] is False and "anomalies.csv" in a["message"]
        r = c.get("/api/v1/forecast", params={"route": "7", "model": "hybrid"})
        assert r.status_code == 400 and r.json()["error"]["code"] == "model_unavailable"
        m = c.get("/api/v1/model").json()
        assert m["hybrid_available"] is False and m["tables"] == [] and m["sources"]
    finally:
        st.ml = saved[0]
        st.cubes["forecast_hybrid"], st.cubes["combined_hybrid"] = saved[1], saved[2]
        _reset(st)


def test_assistant_answers(c, synth):
    ask = lambda q, **kw: c.get("/api/v1/assistant", params={"q": q, "ref_date": "2025-12-10", **kw}).json()
    v = ask("Сколько вагонов нужно на 17 маршруте в 8 утра?")
    assert v["intent"] == "vehicles" and "Маршрут 17" in v["answer"] and "ваг." in v["answer"]
    assert "вероятность переполнения" in v["answer"] and v["action"]["hour"] == 8
    o = ask("где завтра переполнение?")
    assert o["intent"] == "overflow" and "11 декабря" in o["answer"]
    a = ask("аномалии на маршруте 7 в мае")
    assert "Победы" in " ".join(a["items"])
    x = ask("пассажиры на маршруте 99 завтра")
    assert "не найден" in x["answer"]
    y = ask("сколько пассажиров 1 марта 2026")
    assert "Данные есть" in y["answer"]
    h = ask("")
    assert h["intent"] == "help" and len(h["items"]) >= 4
    assert c.get("/api/v1/assistant", params={"q": "x" * 301}).status_code == 422
