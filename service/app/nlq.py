"""Natural-language → structured query for «Помощник диспетчера» (rule-based, no LLM).

    parse_query("сколько вагонов на семерке завтра в вечерний час пик", ref=date(2025, 12, 10))
    -> {"route": "7", "date_from": "2025-12-11", "date_to": "2025-12-11", "hour_from": 16, "hour_to": 19,
        "hour_ranges": [[16, 19]], "granularity": "hour", "corrections": {}, "intent": "vehicles", "chips": [...]}

Steps: normalise (lower case, ё→е, dashes, typo repair against a vocabulary with difflib) → dates (ISO, 10.12,
«10 декабря», «с 10 по 15 декабря», «17-го», «семнадцатого», сегодня/завтра/послезавтра/вчера, weekdays,
«в декабре», неделя, выходные, год) → route (№ 17, «17 маршрут», «на 7-ке», «семерка», «семнадцатый трамвай») →
hours («в 8 утра», «в 7 вечера», 18:00, «с 7 до 10», час пик 07–10 / 16–20, утренний/вечерний пик, ночью, утром,
днём, вечером) → corrections (+10 %, дождь/снег N мм, мороз −N °C, перекрытие ×0, частичное ×0,5, фестиваль ×1,2,
пробки N баллов) → intent.

Hours are inclusive hour indices: «07:00–10:00» = hour_from 7, hour_to 9.
"""
from __future__ import annotations

import difflib
import re
from datetime import date, timedelta

MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября",
              "ноября", "декабря"]
MONTH_STEMS = ["январ", "феврал", "март", "апрел", "ма[йея]", "июн", "июл", "август", "сентябр", "октябр", "ноябр",
               "декабр"]
WD_PAT = [r"понедельник\w*", r"вторник\w*", r"сред[уаы]", r"четверг\w*", r"пятниц[уаы]", r"суббот[уаы]",
          r"воскресень[ея]"]
WD_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
ORD = {1: "перв", 2: "втор", 3: "трет", 4: "четверт", 5: "пят", 6: "шест", 7: "седьм", 8: "восьм", 9: "девят",
       10: "десят", 11: "одиннадцат", 12: "двенадцат", 13: "тринадцат", 14: "четырнадцат", 15: "пятнадцат",
       16: "шестнадцат", 17: "семнадцат", 18: "восемнадцат", 19: "девятнадцат", 20: "двадцат", 30: "тридцат"}
TENS = {"двадцать": 20, "тридцать": 30}
NICK = {"единичк": "1", "пятерк": "5", "семерк": "7", "одиннадцатк": "11", "двенашк": "12", "двенадцатк": "12",
        "семнашк": "17", "семнадцатк": "17", "полтинник": "50", "пятидесятк": "50"}
PEAK_AM, PEAK_PM = (7, 9), (16, 19)       # 07:00–10:00 and 16:00–20:00
PARTS = {"ночью": (0, 5), "ночь": (0, 5), "утром": (6, 11), "днем": (12, 16), "днём": (12, 16), "вечером": (17, 22)}

VOCAB = sorted({
    "завтра", "послезавтра", "сегодня", "вчера", "маршрут", "маршрута", "маршруте", "маршруту", "маршрутов",
    "трамвай", "трамвая", "трамваев", "трамваю", "вагонов", "вагона", "вагоны", "пассажиров", "пассажиры",
    "переполнение", "переполнения", "переполнен", "загрузка", "загрузку", "нагрузка", "понедельник", "вторник",
    "среду", "среда", "четверг", "пятницу", "пятница", "субботу", "суббота", "воскресенье", "утренний", "вечерний",
    "утром", "вечером", "ночью", "днем", "аномалии", "аномалия", "модель", "прогноз", "сколько", "нужно", "будет",
    "декабря", "ноября", "октября", "сентября", "декабре", "ноябре", "октябре", "перекрытие", "фестиваль", "дождь",
    "снегопад", "мороз", "пробки", "баллов", "семерке", "семерка", "выходные", "неделе", "следующей", "следующий",
    "вечера", "утра", "ночи", "часов", "числа", "градусов", "если", "будет", "какие", "какой", "когда", "перекрыт",
    "ремонт", "концерт", "матч", "частично", "маршрутах", "маршруты", "всех", "везде", "сейчас", "больше", "меньше",
    "праздник", "новый", "город", "центр", "станция", "метро", "людей", "человек", "поток", "спрос", "декабрь",
} | set(MONTHS_GEN))


def _hr(h0: int, h1: int) -> str:
    return f"{h0:02d}:00–{(h1 + 1) % 24:02d}:00"


def normalise(text: str) -> tuple[str, list[str]]:
    """Lower case, ё→е, unify dashes/spaces, fix typos of known words. Returns (text, list of fixes)."""
    t = (text or "").lower().replace("ё", "е")
    t = re.sub(r"[–—−]", "-", t)
    t = re.sub(r"[«»\"'!?,;()]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    fixes = []

    def fix(m):
        w = m.group(0)
        if len(w) < 5 or w in VOCAB:
            return w
        cand = difflib.get_close_matches(w, VOCAB, n=1, cutoff=0.82)
        if cand and cand[0] != w:
            fixes.append(f"{w}→{cand[0]}")
            return cand[0]
        return w

    t = re.sub(r"[а-я]+", fix, t)
    return f" {t} ", fixes


def _ord_value(s: str) -> int | None:
    """«семнадцатого» → 17, «двадцать первого» → 21."""
    parts = s.split()
    base = 0
    if parts and parts[0] in TENS:
        base, parts = TENS[parts[0]], parts[1:]
    if not parts:
        return base or None
    w = parts[0]
    for n, stem in sorted(ORD.items(), key=lambda x: -len(x[1])):
        if w.startswith(stem):
            return base + n if (base == 0 or n < 10) else None
    return None


ORD_ALT = "|".join(sorted(ORD.values(), key=len, reverse=True))
ORD_RE = rf"(?:(?:двадцать|тридцать)\s+)?(?:{ORD_ALT})\w*"


def parse_query(text: str, ref: date, year: int | None = None) -> dict:
    t, fixes = normalise(text)
    year = year or ref.year
    q: dict = {"text": text, "normalised": t.strip(), "fixes": fixes, "route": None, "date_from": None,
               "date_to": None, "hour_from": None, "hour_to": None, "hour_ranges": [], "granularity": None,
               "horizon": None, "corrections": {}, "intent": None}
    chips: list[dict] = []

    def cut(m):
        nonlocal t
        t = t[:m.start()] + " " + t[m.end():]

    def set_dates(a: date, b: date, how: str):
        q["date_from"], q["date_to"] = a.isoformat(), b.isoformat()
        chips.append({"key": "date", "label": "Дата" if a == b else "Период",
                      "value": a.isoformat() if a == b else f"{a.isoformat()}..{b.isoformat()}",
                      "text": (f"{a:%d.%m.%Y}" if a == b else f"{a:%d.%m} – {b:%d.%m.%Y}") + (f" ({how})" if how else "")})

    def mk(y, m, d):
        try:
            return date(y, m, d)
        except ValueError:
            return None

    mon = "|".join(MONTHS_GEN)
    # ---------------- dates ----------------
    m = re.search(rf"\bс\s+(\d{{1,2}})(?:\s+({mon}))?\s+по\s+(\d{{1,2}})\s+({mon})", t)
    if m:
        m2 = MONTHS_GEN.index(m[4]) + 1
        m1 = MONTHS_GEN.index(m[2]) + 1 if m[2] else m2
        a, b = mk(year, m1, int(m[1])), mk(year, m2, int(m[3]))
        if a and b and a <= b:
            set_dates(a, b, "")
            cut(m)
    if not q["date_from"] and (m := re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", t)):
        if d := mk(int(m[1]), int(m[2]), int(m[3])):
            set_dates(d, d, ""); cut(m)
    if not q["date_from"] and (m := re.search(r"\b(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\b", t)):
        y = int(m[3]) if m[3] else year
        if d := mk(y + 2000 if y < 100 else y, int(m[2]), int(m[1])):
            set_dates(d, d, ""); cut(m)
    if not q["date_from"] and (m := re.search(rf"\b(\d{{1,2}})\s+({mon})(?:\s+(\d{{4}}))?", t)):
        if d := mk(int(m[3]) if m[3] else year, MONTHS_GEN.index(m[2]) + 1, int(m[1])):
            set_dates(d, d, ""); cut(m)
    if not q["date_from"] and (m := re.search(rf"\b({ORD_RE})\s+({mon})", t)):
        n = _ord_value(m[1])
        if n and (d := mk(year, MONTHS_GEN.index(m[2]) + 1, n)):
            set_dates(d, d, ""); cut(m)
    if not q["date_from"]:
        for w, k in (("послезавтра", 2), ("завтра", 1), ("сегодня", 0), ("вчера", -1)):
            if m := re.search(rf"\b{w}\b", t):
                d = ref + timedelta(days=k)
                set_dates(d, d, w); cut(m)
                break
    if not q["date_from"] and (m := re.search(r"\b(\d{1,2})\s*-?\s*(?:го|е)\b(?!\s*-?\s*(?:маршрут|трамва|ка|ке))|\b(\d{1,2})\s+числа\b", t)):
        n = int(m[1] or m[2])
        if d := mk(ref.year, ref.month, n):
            set_dates(d, d, f"{n}-е число"); cut(m)
    if not q["date_from"] and (m := re.search(rf"\b({ORD_RE})(?:ого|ое)?\s*(?:числа)?(?=\s)(?!\s*(?:маршрут|трамва))", t)):
        n = _ord_value(m[1])
        if n and m[1].endswith(("ого", "ое", "его")) and (d := mk(ref.year, ref.month, n)):
            set_dates(d, d, f"{n}-е число"); cut(m)
    if not q["date_from"]:
        for i, pat in enumerate(WD_PAT):
            if m := re.search(rf"\b(?:в|во)?\s*(следующ\w+\s+)?{pat}", t):
                delta = (i - ref.weekday()) % 7
                d = ref + timedelta(days=delta or (7 if m[1] else 0))  # «следующий X» = next X strictly after today
                set_dates(d, d, WD_RU[i]); cut(m)
                break
    if not q["date_from"] and (m := re.search(r"\bна\s+(?:этой\s+)?неделе\b", t)):
        set_dates(ref, ref + timedelta(days=6), "7 дней"); cut(m)
    if not q["date_from"] and (m := re.search(r"\bна\s+следующей\s+неделе\b", t)):
        a = ref + timedelta(days=7 - ref.weekday())
        set_dates(a, a + timedelta(days=6), "следующая неделя"); cut(m)
    if not q["date_from"] and (m := re.search(r"\bна\s+выходн\w+\b", t)):
        a = ref + timedelta(days=(5 - ref.weekday()) % 7)
        set_dates(a, a + timedelta(days=1), "выходные"); cut(m)
    if not q["date_from"] and (m := re.search(r"\b(?:на|в|за)\s+(20\d\d)\s*(?:год\w*)?\b|\bна\s+год\b", t)):
        y = int(m[1]) if m[1] else year + 1
        q["horizon"] = "year"
        set_dates(date(y, 1, 1), date(y, 12, 31), "год"); cut(m)
    if not q["date_from"]:
        for i, pat in enumerate(MONTH_STEMS):
            if m := re.search(rf"\b(?:в|за|на)\s+{pat}\w*", t):
                a = date(year, i + 1, 1)
                b = date(year + (i == 11), (i + 1) % 12 + 1, 1) - timedelta(days=1)
                q["horizon"] = "month"
                set_dates(a, b, "месяц"); cut(m)
                break

    # ---------------- route ----------------
    route = None
    pats = [
        r"(?:маршрут\w*|трамва\w*|№|#)\s*(?:№\s*)?(\d{1,3})\b",
        r"\b(\d{1,3})\s*-?\s*(?:[а-я]{1,3})?\s+(?:маршрут|трамва)\w*",
        r"\b(\d{1,3})\s*-?\s*(?:ке|ка|ку|ки|кой|ой)\b",
    ]
    for pat in pats:
        if m := re.search(pat, t):
            route = m[1]; cut(m)
            break
    if route is None and (m := re.search(rf"\b({ORD_RE})\s+(?:маршрут|трамва)\w*", t)):
        n = _ord_value(m[1])
        if n:
            route = str(n); cut(m)
    if route is None:
        for stem, r in NICK.items():
            if m := re.search(rf"\b(?:на\s+)?{stem}\w*", t):
                route = r; cut(m)
                break
    if route is not None:
        q["route"] = route
        chips.append({"key": "route", "label": "Маршрут", "value": route, "text": f"№ {route}"})
    elif re.search(r"\b(?:все|всех|сети|сеть|везде|где)\b", t):
        q["route"] = "all"
        chips.append({"key": "route", "label": "Маршрут", "value": "all", "text": "все маршруты"})

    # ---------------- hours ----------------
    ranges: list[tuple[int, int]] = []
    how = ""
    if re.search(r"\bчас\w*\s*пик|\bпиков\w*|\bпик\b", t):
        am, pm = re.search(r"утрен", t), re.search(r"вечерн", t)
        ranges = [PEAK_AM] if am and not pm else [PEAK_PM] if pm and not am else [PEAK_AM, PEAK_PM]
        how = "утренний час пик" if ranges == [PEAK_AM] else "вечерний час пик" if ranges == [PEAK_PM] else "час пик"
        t = re.sub(r"\b(?:утренн\w+|вечерн\w+)?\s*(?:час\w*\s*)?пик\w*", " ", t)
    if not ranges and (m := re.search(r"\bс\s+(\d{1,2})(?::00)?\s*(?:ч\w*)?\s*до\s+(\d{1,2})(?::00)?\s*(утра|вечера|дня|ночи|ч\w*)?", t)):
        h0, h1 = int(m[1]), int(m[2])
        if m[3] in ("вечера", "дня") and h1 < 12:
            h1 += 12
            if h0 < 12 and h0 + 12 < h1:
                h0 += 12
        if 0 <= h0 < h1 <= 24:
            ranges, how = [(h0, h1 - 1)], ""
            cut(m)
    if not ranges:
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", t) or \
            re.search(r"\b(?:в|к|на|около)\s*(\d{1,2})\s*(?:ч\w*)?\s*(утра|вечера|дня|ночи)?(?!\s*(?:мм|%|балл|град|\d))", t) or \
            re.search(r"\b(\d{1,2})\s*(утра|вечера|дня|ночи|часов|час|ч)\b", t)
        if m:
            h = int(m[1])
            suf = m[2] if m.lastindex and m.lastindex >= 2 and m[2] and not m[2].isdigit() else ""
            if suf in ("вечера", "дня") and h < 12:
                h += 12
            if suf == "ночи" and h == 12:
                h = 0
            if 0 <= h <= 23:
                ranges = [(h, h)]
                cut(m)
    if not ranges:
        for w, r in PARTS.items():
            if m := re.search(rf"\b{w}\b", t):
                ranges, how = [r], w
                cut(m)
                break
    if ranges:
        q["hour_ranges"] = [list(r) for r in ranges]
        q["hour_from"], q["hour_to"] = min(r[0] for r in ranges), max(r[1] for r in ranges)
        chips.append({"key": "hours", "label": "Часы", "value": ";".join(f"{a}-{b}" for a, b in ranges),
                      "text": " и ".join(_hr(a, b) for a, b in ranges) + (f" ({how})" if how else "")})

    if not q["date_from"]:  # no date in the text: the date selected on the dashboard («сегодня»)
        set_dates(ref, ref, "дата на дашборде")
        q["date_defaulted"] = True
    # ---------------- corrections ----------------
    corr: dict[str, str] = {}
    scope = q["route"] if q["route"] not in (None, "all") else "all"
    d0, d1 = q["date_from"], q["date_to"] or q["date_from"]
    if m := re.search(r"(?:на\s+)?([+-]?\d{1,2}(?:[.,]\d)?)\s*%\s*(больше|выше|меньше|ниже)?", t):
        v = float(m[1].replace(",", "."))
        if m[2] in ("меньше", "ниже"):
            v = -abs(v)
        k = round(1 + v / 100, 4)
        corr["k_level"] = f"{scope}:{k}" if scope != "all" else f"{k}"
        chips.append({"key": "k_level", "label": "Уровень", "value": corr["k_level"], "text": f"×{k:g}".replace(".", ",")})
        cut(m)
    if d0:
        mm = re.search(r"(\d{1,3})\s*мм", t)
        tc = re.search(r"(?:мороз\w*|холод\w*|температур\w*)?\s*(-\s?\d{1,2})\s*(?:°|град\w*|c\b|с\b)", t) or \
            re.search(r"мороз\w*\s*(?:до\s*)?(\d{1,2})", t)
        wet = re.search(r"дожд|ливн|ливен|снег|осадк|метел", t)
        cold = re.search(r"мороз|холод", t)
        if mm or wet or tc or cold:
            add = int(mm[1]) if mm else (15 if wet and re.search(r"снег|метел", t) else 10 if wet else 0)
            temp = None
            if tc:
                temp = -abs(int(tc[1].replace(" ", "").replace("-", "")))
            elif cold:
                temp = -15
            corr["w_scenario"] = ";".join(f"{x}:{add}" + (f":{temp}" if temp is not None else "") for x in _days(d0, d1))
            chips.append({"key": "w_scenario", "label": "Погода", "value": corr["w_scenario"],
                          "text": f"+{add} мм" + (f", {temp} °C" if temp is not None else "")})
        ev = (0 if re.search(r"перекры|закры|ремонт|не ход", t) else
              0.5 if re.search(r"частичн", t) else
              1.2 if re.search(r"фестивал|концерт|матч|мероприят|салют|парад", t) else None)
        if ev is not None:
            hrs = f":{q['hour_from']}-{q['hour_to']}" if q["hour_from"] is not None else ""
            corr["k_event"] = f"{scope}:{d0}:{d1}:{ev}{hrs}"
            chips.append({"key": "k_event", "label": "Событие", "value": corr["k_event"],
                          "text": {0: "перекрытие ×0", 0.5: "частичное ×0,5", 1.2: "событие ×1,2"}[ev]})
        if m := re.search(r"пробк\w*\s*(?:на\s*)?(\d{1,2})\s*(?:балл\w*)?", t):
            sc = min(10, int(m[1]))
            corr["k_traffic"] = ";".join(f"{x}:{sc}" for x in _days(d0, d1))
            chips.append({"key": "k_traffic", "label": "Пробки", "value": corr["k_traffic"], "text": f"{sc} баллов"})
    q["corrections"] = corr

    # ---------------- intent + granularity ----------------
    intents = [
        ("help", r"помощ|что ты умеешь|что умеешь|примеры|^\s*$"),
        ("anomalies", r"аномал|сбо[йия]|выброс|провал|всплеск"),
        ("model", r"модел|точност|метрик|как (устроен|считает|считается|работает)|lightgbm|гибрид"),
        ("vehicles", r"вагон|трамва[ея]в|подвижн|выпуск|сколько (нужно|надо) (машин|единиц)"),
        ("overflow", r"переполн|давк|перегру|риск|не хват|битком"),
        ("peak", r"когда\b.*\bпик|\bкогда час"),
        ("load", r"пассажир|загрузк|нагрузк|пото[кч]|сколько (людей|человек)|прогноз|спрос"),
    ]
    raw = " " + (text or "").lower().replace("ё", "е") + " "
    q["intent"] = next((n for n, pat in intents if re.search(pat, t) or (n == "peak" and re.search(pat, raw))), None)
    if q["intent"] is None:
        q["intent"] = "load" if (q["route"] or q["date_from"] or ranges) else "help"
    if q["date_from"]:
        n_days = (date.fromisoformat(q["date_to"]) - date.fromisoformat(q["date_from"])).days + 1
        q["granularity"] = "hour" if n_days == 1 else "day" if n_days <= 62 else "month"
        q["horizon"] = q["horizon"] or ("day" if n_days == 1 else "month")
    q["chips"] = chips
    return q


def _days(d0: str, d1: str) -> list[str]:
    a, b = date.fromisoformat(d0), date.fromisoformat(d1)
    n = min((b - a).days, 30)
    return [(a + timedelta(days=i)).isoformat() for i in range(n + 1)]
