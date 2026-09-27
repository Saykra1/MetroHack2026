"""Correction coefficients ("корректирующие коэффициенты") applied on top of the model forecast.

The model forecast is   prediction = base × special_mult × weather_mult × rules_mult   (final_candidate_explain.csv).
A dispatcher can override factors through query parameters; the service recomputes the forecast on the fly:

  k_level    level/season multiplier: "1.02" (all routes) or "7:1.05,11:0.97" (per route) or mixed "0.98,7:1.1"
  k_special  strength of special-day effects (holidays, moved days off): special' = 1 + k × (special − 1);
             1 = as in the model, 0 = ignore special days, 1.5 = 50 % stronger
  w_precip   precipitation effect per mm of rain/snow over 06–21 h (model: −0.011 = −1.1 %/mm)
  w_cold     cold-day effect when mean temperature < −10 °C (model: −0.034 = −3.4 %)
  w_floor    lower bound of the weather multiplier (model: 0.9); upper bound fixed at 1.05
  w_scenario what-if weather: "2025-12-10:10:-15" = +10 mm precipitation and −15 °C on 2025-12-10;
             several items separated by ";"; temperature may be omitted: "2025-12-10:5"
  k_event    events: "7:2025-12-01:2025-12-07:0" (route 7 closed), "all:2025-12-20:2025-12-21:1.2" (festival);
             several items separated by ";"; optional hour range: "7:2025-12-01:2025-12-01:0.5:7-10"

weather' = clip(exp(w_precip × (precip − ref) + w_cold × [temp < −10]), w_floor, 1.05),
ref = mean precipitation of 2025-10-18..31 (the model's level window).  The forecast is multiplied by
weather'/weather_mult, special'/special_mult, k_level and the event multipliers.  With default values every
ratio is 1 (up to rounding of the weather file), i.e. the corrected forecast equals the model forecast.
Corrections touch forecast days only; actuals (history) are never modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from .errors import ApiError

DEF_PRECIP, DEF_COLD, DEF_FLOOR, W_CAP = -0.011, -0.034, 0.9, 1.05
DEF_TRAFFIC = 0.007  # +0.7 % boardings per ЦОДД point above the 3-week norm (research/traffic_source.md, spec C, p=0.025)


@dataclass(frozen=True)
class Adj:
    level: tuple = ()          # ((route | "*", k), ...)
    special: float = 1.0
    w_precip: float = DEF_PRECIP
    w_cold: float = DEF_COLD
    w_floor: float = DEF_FLOOR
    w_scn: tuple = ()          # ((date, add_mm, temp | None), ...)
    events: tuple = ()         # ((route | "*", d0, d1, k, h0, h1), ...)
    model: str = "v08"         # forecast source: "v08" (structural) or "hybrid" (structural × LightGBM ratio)
    traffic: tuple = ()        # ((date, score 0–10), ...) ЦОДД road-load scenario
    w_traffic: float = DEF_TRAFFIC

    @property
    def weather_changed(self) -> bool:
        return (self.w_precip, self.w_cold, self.w_floor) != (DEF_PRECIP, DEF_COLD, DEF_FLOOR) or bool(self.w_scn)

    @property
    def active(self) -> bool:
        return bool(self.level) or self.special != 1.0 or self.weather_changed or bool(self.events) or bool(self.traffic)

    @property
    def base(self) -> "Adj":
        """The same forecast model without corrections (the «было» side of «было → стало»)."""
        return NO_ADJ if self.model == "v08" else Adj(model=self.model)

    def describe(self) -> list[str]:
        out = []
        for r, k in self.level:
            out.append(f"Уровень/сезон {'всех маршрутов' if r == '*' else 'маршрута ' + r}: ×{k:g}")
        if self.special != 1.0:
            out.append(f"Сила эффекта особых дней: ×{self.special:g}")
        if (self.w_precip, self.w_cold, self.w_floor) != (DEF_PRECIP, DEF_COLD, DEF_FLOOR):
            pct = lambda v: f"{v * 100:+.1f}".replace("-", "−").replace(".", ",")
            out.append(f"Погода: осадки {pct(self.w_precip)} %/мм, мороз {pct(self.w_cold)} %, нижняя граница {self.w_floor:g}")
        for d, add, t in self.w_scn:
            out.append(f"Сценарий погоды {d:%d.%m}: {add:+g} мм" + (f", {t:g} °C" if t is not None else ""))
        if self.traffic:
            sc = ", ".join(f"{d:%d.%m} — {s:g}" for d, s in self.traffic[:5]) + (" …" if len(self.traffic) > 5 else "")
            out.append(f"Пробки ЦОДД (баллы): {sc}; эффект {self.w_traffic * 100:+.1f} %/балл к норме 3 недель".replace(".", ","))
        for r, d0, d1, k, h0, h1 in self.events:
            hrs = "" if (h0, h1) == (0, 23) else f", {h0:02d}:00–{h1:02d}:59"
            out.append(f"Событие {'все маршруты' if r == '*' else 'маршрут ' + r}, {d0:%d.%m}–{d1:%d.%m}{hrs}: ×{k:g}")
        return out


NO_ADJ = Adj()


def _f(x: str, what: str) -> float:
    try:
        return float(x.replace(",", "."))
    except ValueError:
        raise ApiError(400, "invalid_adjustment", f"Некорректное число «{x}» в параметре «{what}»")


def _d(x: str, what: str) -> date:
    try:
        return date.fromisoformat(x.strip())
    except ValueError:
        raise ApiError(400, "invalid_adjustment", f"Некорректная дата «{x}» в параметре «{what}» (ожидается ГГГГ-ММ-ДД)")


def parse(st, k_level: str | None, k_special: float, w_precip: float, w_cold: float, w_floor: float,
          w_scenario: str | None, k_event: str | None, model: str = "v08", k_traffic: str | None = None,
          w_traffic: float = DEF_TRAFFIC) -> Adj:
    if model == "hybrid" and "forecast_hybrid" not in st.cubes:
        raise ApiError(400, "model_unavailable",
                       "Гибридная модель ML не загружена (нет файла hybrid_nov_dec.csv): используйте model=v08")
    level = []
    for item in filter(None, (x.strip() for x in (k_level or "").split(","))):
        if ":" in item:
            r, k = item.split(":", 1)
            r = r.strip()
            if r not in st.route_idx:
                raise ApiError(400, "invalid_adjustment", f"k_level: маршрут «{r}» не найден")
        else:
            r, k = "*", item
        kv = _f(k, "k_level")
        if not 0 <= kv <= 3:
            raise ApiError(400, "invalid_adjustment", "k_level: множитель должен быть от 0 до 3")
        if kv != 1.0:
            level.append((r, kv))
    scn = []
    for item in filter(None, (x.strip() for x in (w_scenario or "").split(";"))):
        parts = item.split(":")
        if len(parts) not in (2, 3):
            raise ApiError(400, "invalid_adjustment", "w_scenario: формат «ГГГГ-ММ-ДД:+мм[:температура]», например 2025-12-10:10:-15")
        d = _d(parts[0], "w_scenario")
        add = _f(parts[1], "w_scenario")
        t = _f(parts[2], "w_scenario") if len(parts) == 3 and parts[2].strip() != "" else None
        if not -50 <= add <= 100 or (t is not None and not -50 <= t <= 45):
            raise ApiError(400, "invalid_adjustment", "w_scenario: осадки от −50 до +100 мм, температура от −50 до +45 °C")
        scn.append((d, add, t))
    events = []
    for item in filter(None, (x.strip() for x in (k_event or "").split(";"))):
        parts = item.split(":")
        if len(parts) not in (4, 5):
            raise ApiError(400, "invalid_adjustment",
                           "k_event: формат «маршрут:с:по:множитель[:час-час]», например 7:2025-12-01:2025-12-07:0")
        r = parts[0].strip()
        r = "*" if r.lower() in ("all", "*", "все") else r
        if r != "*" and r not in st.route_idx:
            raise ApiError(400, "invalid_adjustment", f"k_event: маршрут «{r}» не найден")
        d0, d1 = _d(parts[1], "k_event"), _d(parts[2], "k_event")
        if d1 < d0:
            raise ApiError(400, "invalid_adjustment", "k_event: дата окончания раньше даты начала")
        k = _f(parts[3], "k_event")
        if not 0 <= k <= 5:
            raise ApiError(400, "invalid_adjustment", "k_event: множитель должен быть от 0 до 5")
        h0, h1 = 0, 23
        if len(parts) == 5 and parts[4].strip():
            try:
                h0, h1 = (int(x) for x in parts[4].split("-"))
            except ValueError:
                raise ApiError(400, "invalid_adjustment", "k_event: часы в формате «7-10»")
            if not (0 <= h0 <= h1 <= 23):
                raise ApiError(400, "invalid_adjustment", "k_event: часы от 0 до 23, начало не позже конца")
        events.append((r, d0, d1, k, h0, h1))
    traffic = []
    for item in filter(None, (x.strip() for x in (k_traffic or "").split(";"))):
        if item.lower() in ("actual", "факт", "цодд"):
            if st.traffic_score is None:
                raise ApiError(400, "invalid_adjustment", "k_traffic: данные ЦОДД о пробках не загружены")
            a, b = st.coverage["forecast"]
            traffic += [(st.day_at(i), float(st.traffic_score[i])) for i in range(st.day_index(a), st.day_index(b) + 1)
                        if st.traffic_score[i] != st.traffic_norm[i]]
            continue
        parts = item.split(":")
        if len(parts) != 2:
            raise ApiError(400, "invalid_adjustment", "k_traffic: формат «ГГГГ-ММ-ДД:балл» (0–10), несколько через «;», или actual")
        d, sc = _d(parts[0], "k_traffic"), _f(parts[1], "k_traffic")
        if not 0 <= sc <= 10:
            raise ApiError(400, "invalid_adjustment", "k_traffic: балл пробок от 0 до 10")
        traffic.append((d, sc))
    traffic = sorted(dict(traffic).items())
    return Adj(tuple(level), round(k_special, 4), round(w_precip, 5), round(w_cold, 5), round(w_floor, 4),
               tuple(scn), tuple(events), model, tuple(traffic), round(w_traffic, 5) if traffic else DEF_TRAFFIC)


def weather_mult(st, adj: Adj, di: np.ndarray) -> np.ndarray | None:
    """Model-style weather multiplier for day indices `di` under `adj` (None if no weather data)."""
    if st.weather_pr is None:
        return None
    pr = np.nan_to_num(st.weather_pr[di].copy())
    t = st.weather_t[di].copy()
    for d, add, temp in adj.w_scn:
        hit = di == st.day_index(d)
        pr[hit] = np.maximum(0, pr[hit] + add)
        if temp is not None:
            t[hit] = temp
    with np.errstate(invalid="ignore"):
        cold = (t < -10).astype(float)
    m = np.exp(adj.w_precip * (pr - st.weather_ref_pr) + adj.w_cold * cold)
    return np.clip(m, adj.w_floor, W_CAP)


def factor(st, adj: Adj, routes: list[str], i0: int, i1: int, h0: int, h1: int) -> np.ndarray:
    """Multiplier [k_routes, days, hours] for the slice; 1 on non-forecast days."""
    ri = [st.route_idx[r] for r in routes]
    n_d, n_h = i1 - i0 + 1, h1 - h0 + 1
    f = np.ones((len(ri), n_d, n_h), dtype=np.float32)
    fc_from = st.day_index(st.coverage["forecast"][0])
    days = np.arange(i0, i1 + 1)
    is_fc = days >= fc_from
    if not is_fc.any():
        return f
    fcm = is_fc[None, :, None]
    for r, k in adj.level:
        if r == "*":
            f = np.where(fcm, f * k, f)
        elif r in routes:
            j = routes.index(r)
            f[j] = np.where(is_fc[:, None], f[j] * k, f[j])
    if adj.special != 1.0 and "special" in st.comp:
        s = st.comp["special"][ri, i0:i1 + 1, h0:h1 + 1]
        s = np.where(np.isnan(s) | (s <= 0), 1.0, s)
        f *= (1 + adj.special * (s - 1)) / s
    if adj.weather_changed:
        w_new = weather_mult(st, adj, days)
        if w_new is not None:
            w_old = st.comp["weather"][ri, i0:i1 + 1, h0:h1 + 1] if "weather" in st.comp else np.ones_like(f)
            w_old = np.where(np.isnan(w_old) | (w_old <= 0), 1.0, w_old)
            ratio = w_new[None, :, None] / w_old
            f *= np.where(fcm, ratio, 1.0).astype(np.float32)
    if adj.traffic and st.traffic_norm is not None:
        for d, sc in adj.traffic:
            i = st.day_index(d)
            if i0 <= i <= i1 and i >= fc_from:
                f[:, i - i0, :] *= max(0.5, 1 + adj.w_traffic * (sc - float(st.traffic_norm[i])))
    for r, d0, d1, k, eh0, eh1 in adj.events:
        a, b = max(st.day_index(d0), i0, fc_from), min(st.day_index(d1), i1)
        c0, c1 = max(eh0, h0), min(eh1, h1)
        if a > b or c0 > c1:
            continue
        js = range(len(ri)) if r == "*" else ([routes.index(r)] if r in routes else [])
        for j in js:
            f[j, a - i0:b - i0 + 1, c0 - h0:c1 - h0 + 1] *= k
    return f
