"""Shared ML utilities: structural base (analyst clean level x anchor shape, = v07/v08 base without rules),
multi-origin panel builder, feature engineering. Read-only use of existing code (src/, experiments/analyst/).
Run everything from the repo root:  python src/ml/<module>.py"""
import os, sys, io, contextlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'src')); sys.path.insert(0, os.path.join(ROOT, 'experiments', 'analyst'))
import pandas as pd, numpy as np
with contextlib.redirect_stdout(io.StringIO()):          # analyst modules print diagnostics on import
    from r2_harness import D, DAILY, dtmap, shape, level  # noqa: F401  (D has column dt = wk4 day type)
    from r2_clean_anchor import anchor, BAD                # noqa: F401
    from r2_clean_level import level_clean, SHORTBAD, KDEF  # noqa: F401
    from r2_anchor_refine import fc3
from common import wape_score, full_grid, ROUTES          # noqa: F401
from model_ls import FOLDS                                # noqa: F401
from model_profile import daytype, cal

OUT = os.path.join(ROOT, 'experiments', 'ml'); os.makedirs(OUT, exist_ok=True)
HMAX = 61                                                 # max horizon (days) = 2 months

# ---------------------------------------------------------------- external data
_w = pd.read_csv(os.path.join(ROOT, 'research', 'weather_moscow_2025.csv')); _w['ts'] = pd.to_datetime(_w.datetime)
_w['date'] = _w.ts.dt.normalize(); _w['hour'] = _w.ts.dt.hour
_wd = _w[(_w.hour >= 6) & (_w.hour <= 21)].groupby('date').agg(t_day=('temperature_2m', 'mean'), pr_day=('precipitation', 'sum'),
                                                                 sn_day=('snowfall', 'sum'), snowdepth=('snow_depth', 'mean')).reset_index()
WEATHER = _w[['date', 'hour', 'temperature_2m', 'precipitation', 'snowfall', 'wind_speed_10m']].merge(_wd, on='date')
_tr = pd.read_csv(os.path.join(ROOT, 'research', 'traffic_moscow_2025_daily.csv'), parse_dates=['date'])
TRAFFIC = _tr[['date', 'max_score', 'reported']].rename(columns={'max_score': 'traffic_score', 'reported': 'traffic_reported'})
CAL = cal[['date', 'is_dayoff', 'is_holiday', 'is_preholiday_shortened', 'is_school_holiday', 'is_transferred_workday',
           'is_new_year_period']]

# ---------------------------------------------------------------- structural base
def base_forecast(hist, t, **kw):
    """Structural base = analyst fc3 (clean level, 0.3*4w + 0.7*anchor shape, cap x1.5). t needs route,date,hour,dt."""
    return fc3(hist, t, 0.7, 'ratio_cap', **kw)


def base_components(hist):
    """Level per (route, dt) and 4-week shape per (route, dt, hour) at the origin — used as model features."""
    end = hist.date.max()
    L = level_clean(end).rename('L')
    S = shape(hist, end, 4).rename('S4')
    SA = anchor(hist).rename('SA')
    # long-run level (12 weeks, clean) vs recent level -> "is the level currently depressed/elevated"
    dd = DAILY[(DAILY.date <= end) & (DAILY.date > end - pd.Timedelta(weeks=12)) & ~DAILY.date.isin(SHORTBAD)]
    L12 = dd.groupby(['route', 'dt']).tot.median().rename('L12')
    return L, S, SA, L12


def make_target(start, end, routes=None):
    t = full_grid(start, end)
    t = t[t.route != 5] if routes is None else t[t.route.isin(routes)]
    t['dt'] = dtmap(daytype(t.date), 'wk4')
    return t.reset_index(drop=True)


def panel_for_origin(origin, end=None, hist=None, with_y=True):
    """Rows (route, date, hour) for [origin, origin+HMAX) with base, features and (optionally) y."""
    origin = pd.Timestamp(origin)
    end = pd.Timestamp(end) if end is not None else origin + pd.Timedelta(days=HMAX - 1)
    hist = D[D.date < origin] if hist is None else hist
    t = make_target(origin, end)
    t['base'] = base_forecast(hist, t)
    L, S, SA, L12 = base_components(hist)
    t = t.join(L, on=['route', 'dt']).join(S, on=['route', 'dt', 'hour']).join(SA, on=['route', 'dt', 'hour']).join(L12, on=['route', 'dt'])
    t['origin'] = origin
    if with_y:
        t = t.merge(D[['route', 'date', 'hour', 'boardings']].rename(columns={'boardings': 'y'}), on=['route', 'date', 'hour'], how='left')
    return t


def add_features(t):
    t = t.merge(CAL, on='date', how='left').merge(WEATHER, on=['date', 'hour'], how='left').merge(TRAFFIC, on='date', how='left')
    t['dow'] = t.date.dt.dayofweek
    t['h_days'] = (t.date - t.origin).dt.days
    t['h_bucket'] = np.minimum(t.h_days // 14, 4)
    t['logbase'] = np.log1p(t.base)
    t['logL'] = np.log1p(t.L)
    t['lvl_ratio'] = np.log((t.L + 1) / (t.L12 + 1))            # recent vs 12-week clean level
    t['shape_dev'] = np.log((t.S4 + 1e-4) / (t.SA + 1e-4))      # recent vs anchor share
    t['dom'] = t.date.dt.day                                     # month-end / payday effects
    t['days_to_ny'] = (pd.Timestamp('2026-01-01') - t.date).dt.days.clip(upper=60)  # constant 60 in history (no NY analogue)
    return t


def origins_all():
    """Weekly origins + 1st/15th of each month (fold origins included) from 20 Jan (after Jan holidays)."""
    o = set(pd.date_range('2025-01-20', '2025-10-25', freq='7D'))
    o |= set(pd.date_range('2025-02-01', '2025-10-01', freq='MS')) | set(pd.date_range('2025-02-15', '2025-10-15', freq='MS') + pd.Timedelta(days=14))
    return sorted(o)


def build_panel(cache=True):
    """All origins, targets clipped to 31 Oct. Cached as parquet (≈40 origins x 13k rows)."""
    path = os.path.join(OUT, 'panel_cache.parquet')
    if cache and os.path.exists(path):
        return pd.read_parquet(path)
    parts = []
    for o in origins_all():
        e = min(o + pd.Timedelta(days=HMAX - 1), pd.Timestamp('2025-10-31'))
        parts.append(panel_for_origin(o, e))
    P = add_features(pd.concat(parts, ignore_index=True))
    P.to_parquet(path)
    return P


def fold_split(P, s, e):
    """Train: origins < s with targets < s. Test: the fold origin itself, targets in [s, e]."""
    s, e = pd.Timestamp(s), pd.Timestamp(e)
    tr = P[(P.origin < s) & (P.date < s)]
    te = P[(P.origin == s) & (P.date <= e)]
    return tr, te
