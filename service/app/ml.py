"""Optional ML layer produced by the ML pipeline (experiments/ml → service/data):

  intervals.csv       route;date;hour;p10;p50;p90         prediction intervals (Nov–Dec 2025)
  anomalies.csv       route;date;score;kind;label          AI anomaly detector over the history (Jan–Oct 2025)
  hybrid_nov_dec.csv  route;date;hour;base;ml_ratio;prediction   hybrid forecast (structural × LightGBM ratio)
  model_report.md     REPORT.md of the ML run (fold metrics tables)

Every file is optional: when one is missing the related feature is reported as unavailable and the service keeps
working on the v08 forecast.  Loading never raises.

Intervals are stored *relative* to the ML median (p10/p50, p90/p50), so the band follows whatever point forecast is
shown (v08, hybrid, or a corrected forecast).  The overflow probability fits a two-piece lognormal per cell:
ln X ~ N(ln median, σ), σ_low = ln(p50/p10)/z, σ_high = ln(p90/p50)/z, z = Φ⁻¹(0.9) = 1.2816.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config

Z90 = 1.2815515655446004
KIND_RU = {"drop": "провал", "spike": "всплеск", "shape": "аномальный профиль"}
LABEL_RU = {
    "holiday (new year period)": "праздник (новогодний период)",
    "holiday / bridge / pre-holiday": "праздник / перенос / предпраздничный день",
    "holiday weekend": "праздничные выходные",
    "school break": "школьные каникулы",
    "unknown": "причина не установлена — новый сигнал для диспетчера",
}
PERIOD_RU = {"jul-aug": "июль–август", "jul": "июль", "aug": "август", "weekends (sep-nov 14)": "выходные, сентябрь – 14 ноября"}


def ru_label(label: str) -> str:
    """Russian text for the detector's labels (unknown formats are shown as is)."""
    key = label.strip().lower()
    if key in LABEL_RU:
        return LABEL_RU[key]
    m = re.match(r"repairs?:\s*route\s+(\w+)\s*(.*)$", key)
    if m:
        per = PERIOD_RU.get(m[2].strip(), m[2].strip())
        return f"ремонт: маршрут {m[1]}" + (f", {per}" if per else "")
    return label.strip()


@dataclass
class MLData:
    rel_lo: np.ndarray | None = None      # p10/p50 [R, D, 24]; 1 on forecast days without data, NaN on history days
    rel_hi: np.ndarray | None = None      # p90/p50
    intervals_rows: int = 0
    anomalies: list[dict] = field(default_factory=list)
    hybrid_ratio: np.ndarray | None = None  # ml_ratio [R, D, 24] (for explain)
    hybrid_rows: int = 0
    hybrid_weight_zero: bool = False      # prediction == base in the hybrid file (ML weight w = 0)
    report_md: str | None = None
    folds_table: dict | None = None       # hybrid_folds.csv as a table (fallback when REPORT.md has none)
    errors: list[str] = field(default_factory=list)

    @property
    def intervals(self) -> bool:
        return self.rel_lo is not None

    @property
    def hybrid(self) -> bool:
        return self.hybrid_ratio is not None


def _read(path, cols: set[str]) -> pd.DataFrame | None:
    df = pd.read_csv(path, sep=";", dtype={"route": str})
    df.columns = [c.strip() for c in df.columns]
    if not cols.issubset(df.columns):
        raise ValueError(f"{path.name}: нет колонок {sorted(cols - set(df.columns))}")
    df["route"] = df["route"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _index(st, df: pd.DataFrame, with_hour: bool = True):
    df = df[df.route.isin(st.route_idx)]
    di = np.array([st.day_index(d) for d in df.date], dtype=np.int64)
    ok = (di >= 0) & (di < st.n_days)
    if with_hour:
        ok &= df.hour.between(0, 23).to_numpy()
    df, di = df[ok], di[ok]
    return df, df.route.map(st.route_idx).to_numpy(), di


def _load_intervals(st, ml: MLData, path) -> None:
    df = _read(path, {"route", "date", "hour", "p10", "p50", "p90"})
    df, ri, di = _index(st, df)
    hi_ = df.hour.to_numpy()
    p10, p50, p90 = (df[c].to_numpy(dtype=np.float64) for c in ("p10", "p50", "p90"))
    shape = (len(st.routes), st.n_days, 24)
    fc0 = st.day_index(st.coverage["forecast"][0])
    lo = np.full(shape, np.nan, dtype=np.float32)
    hi = np.full(shape, np.nan, dtype=np.float32)
    lo[:, fc0:, :] = 1.0
    hi[:, fc0:, :] = 1.0
    good = (p50 > 0) & (p10 >= 0) & (p90 >= p50) & (p10 <= p50) & (di >= fc0)
    with np.errstate(divide="ignore", invalid="ignore"):
        lo[ri[good], di[good], hi_[good]] = (p10[good] / p50[good]).astype(np.float32)
        hi[ri[good], di[good], hi_[good]] = (p90[good] / p50[good]).astype(np.float32)
    ml.rel_lo, ml.rel_hi, ml.intervals_rows = lo, hi, int(good.sum())


def _load_hybrid(st, ml: MLData, path) -> None:
    df = _read(path, {"route", "date", "hour", "prediction"})
    df, ri, di = _index(st, df)
    fc = st.cubes["forecast"]
    hyb = fc.copy()  # cells missing in the hybrid file fall back to v08
    hyb[ri, di, df.hour.to_numpy()] = df.prediction.to_numpy(dtype=np.float32)
    hyb = np.where(np.isnan(fc), np.nan, hyb)  # keep the forecast horizon/routes of v08
    # new routes (no history): no passengers before launch, as in v08
    for r, d0 in st.launch.items():
        if r in st.route_idx:
            hyb[st.route_idx[r], :st.day_index(d0)] = np.where(np.isnan(fc[st.route_idx[r], :st.day_index(d0)]), np.nan, 0)
    ratio = np.full(fc.shape, np.nan, dtype=np.float32)
    if "ml_ratio" in df.columns:
        ratio[ri, di, df.hour.to_numpy()] = df.ml_ratio.to_numpy(dtype=np.float32)
    st.cubes["forecast_hybrid"] = hyb.astype(np.float32)
    st.cubes["combined_hybrid"] = np.where(np.isnan(st.cubes["history"]), hyb, st.cubes["history"]).astype(np.float32)
    ml.hybrid_ratio, ml.hybrid_rows = ratio, len(df)
    if "base" in df.columns and len(df):
        ml.hybrid_weight_zero = bool(np.allclose(df.prediction.to_numpy(float), df.base.to_numpy(float), atol=0.5))


def _load_anomalies(st, ml: MLData, path) -> None:
    df = _read(path, {"route", "date", "score", "kind"})
    if "label" not in df.columns:
        df["label"] = ""
    h = st.cubes["history"]
    out = []
    for rec in df.itertuples(index=False):
        r, d = rec.route, rec.date
        actual = typical = None
        if r in st.route_idx and 0 <= st.day_index(d) < st.n_days:
            i, ri = st.day_index(d), st.route_idx[r]
            day = h[ri, i]
            if not np.all(np.isnan(day)):
                actual = float(np.nansum(day))
                # typical = median of the same weekday over ±4 weeks (the anomalous day itself excluded)
                cand = [i + 7 * k for k in (-4, -3, -2, -1, 1, 2, 3, 4) if 0 <= i + 7 * k < st.n_days]
                tots = [float(np.nansum(h[ri, j])) for j in cand if not np.all(np.isnan(h[ri, j]))]
                typical = float(np.median(tots)) if tots else None
        kind = str(rec.kind).strip().lower()
        label = rec.label.strip() if isinstance(rec.label, str) else ""
        out.append({
            "route": r, "date": str(d), "weekday": d.weekday(), "score": round(float(rec.score), 3),
            "kind": kind, "kind_ru": KIND_RU.get(kind, kind),
            "label": ru_label(label) if label else "причина не установлена", "label_src": label or None,
            "actual_total": round(actual, 1) if actual is not None else None,
            "typical_total": round(typical, 1) if typical is not None else None,
            "deviation_pct": round((actual / typical - 1) * 100, 1) if actual is not None and typical else None,
        })
    out.sort(key=lambda x: (x["date"], x["route"]))
    ml.anomalies = out


def load(st) -> MLData:
    ml = MLData()
    for name, path, fn in (("intervals", config.INTERVALS_PATH, _load_intervals),
                           ("hybrid", config.HYBRID_PATH, _load_hybrid),
                           ("anomalies", config.ANOMALIES_PATH, _load_anomalies)):
        if not path.is_file():
            continue
        try:
            fn(st, ml, path)
        except Exception as e:  # optional layer: never break startup
            ml.errors.append(f"{name}: {e}")
    if config.HYBRID_FOLDS_PATH.is_file():
        try:
            ml.folds_table = _folds_table(config.HYBRID_FOLDS_PATH)
        except Exception as e:
            ml.errors.append(f"folds: {e}")
    if config.MODEL_REPORT_PATH.is_file():
        ml.report_md = config.MODEL_REPORT_PATH.read_text(encoding="utf-8", errors="replace")
    return ml


def _folds_table(path) -> dict:
    df = pd.read_csv(path, sep=";")
    fmt = lambda v: "—" if pd.isna(v) else f"{v:.4f}" if isinstance(v, float) else str(v)
    return {"heading": "Метрики по фолдам (hybrid_folds.csv)", "header": [str(c) for c in df.columns],
            "rows": [[fmt(v) for v in r] for r in df.itertuples(index=False)]}


def detach(st) -> None:
    """Drop the ML layer (used by tests)."""
    st.cubes.pop("forecast_hybrid", None)
    st.cubes.pop("combined_hybrid", None)
    st.ml = MLData()


# ---------------- math ----------------
def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def p_exceed(median: float, rel_lo: float, rel_hi: float, threshold: float) -> float:
    """P(X > threshold) for a two-piece lognormal with the given median and p10/p50, p90/p50 ratios."""
    if not (median > 0) or threshold is None:
        return 0.0
    if threshold <= 0:
        return 1.0
    x = math.log(threshold / median)
    ok = lambda v: v is not None and np.isfinite(v) and v > 0 and v != 1.0
    s_hi = abs(math.log(rel_hi)) / Z90 if ok(rel_hi) else None
    s_lo = abs(math.log(rel_lo)) / Z90 if ok(rel_lo) else None
    # p10 = 0 (or a degenerate side) -> use the other side's spread (symmetric lognormal)
    sigma = (s_hi if s_hi is not None else s_lo) if x >= 0 else (s_lo if s_lo is not None else s_hi)
    if sigma is None:
        return 1.0 if x < 0 else 0.0
    if sigma < 1e-9:
        return 1.0 if x < 0 else 0.0
    return 1.0 - _phi(x / sigma)


# ---------------- REPORT.md ----------------
def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def parse_md_tables(md: str) -> list[dict]:
    """Extract GitHub-style markdown tables with the nearest preceding heading."""
    lines = md.splitlines()
    out, heading, i = [], None, 0
    sep = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^\s*#{1,6}\s+(.*)$", ln)
        if m:
            heading = m.group(1).strip()
        if "|" in ln and i + 1 < len(lines) and sep.match(lines[i + 1]):
            header = _cells(ln)
            rows, j = [], i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                rows.append(_cells(lines[j]))
                j += 1
            out.append({"heading": heading, "header": header, "rows": rows})
            i = j
            continue
        i += 1
    return out


def pick_fold_table(tables: list[dict]) -> int | None:
    for k, t in enumerate(tables):
        txt = " ".join(t["header"] + [t["heading"] or ""]).lower()
        if "fold" in txt or "фолд" in txt:
            return k
    return 0 if tables else None


def report_text(md: str | None) -> str | None:
    """Summary for the UI: the Russian «питч» section if present, else the first paragraph (no headings/tables)."""
    if not md:
        return None
    m = re.search(r"^#{1,6}[^\n]*(питч|кратко|summary)[^\n]*\n(.*?)(?=^#{1,6}\s|\Z)", md, re.S | re.M | re.I)
    if m:
        body = " ".join(ln.strip() for ln in m[2].splitlines() if ln.strip() and "|" not in ln)
        if body:
            return body[:1500]
    paras, cur = [], []
    for ln in md.splitlines():
        if ln.strip().startswith("#") or "|" in ln:
            if cur:
                paras.append(" ".join(cur)); cur = []
            continue
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(" ".join(cur)); cur = []
    if cur:
        paras.append(" ".join(cur))
    return paras[0][:600] if paras else None
