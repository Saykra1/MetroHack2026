"""Composable, explainable adjustments on top of the v02 explain file.
Each adjustment = one business rule with a source; LB probes toggle one rule at a time."""
import pandas as pd, numpy as np
from common import load_labels

E0 = pd.read_csv('submissions/v02_ls_special_explain.csv', sep=';', parse_dates=['date'])
D = load_labels(); DD = D.groupby(['route','date']).boardings.sum().unstack(0)
PRE = pd.date_range('2025-03-01','2025-06-04').union(pd.date_range('2025-08-08','2025-09-05'))  # pre-repair, no disruptions

def normal_weekend_profile(rt):
    """Hourly weekend profile before repairs, rescaled to the current (Oct) weekday level. Returns {(dow, hour): value}."""
    h = D[(D.route == rt) & D.date.isin(PRE)].copy(); h['dow'] = h.date.dt.dayofweek
    tot = DD.loc[PRE, rt]; wk_pre = tot[tot.index.dayofweek <= 4].median()
    cur = DD[rt]['2025-10-06':'2025-10-31']; wk_cur = cur[cur.index.dayofweek <= 4].median()
    prof = h[h.dow >= 5].groupby(['dow','hour']).boardings.median() / wk_pre * wk_cur
    return prof.to_dict()

def ny_night(E):            # free fare 31.12 20:00 – 01.01 06:00 (transport.mos.ru)
    E.loc[(E.date == '2025-12-31') & (E.hour >= 20), 'prediction'] = 0; return E

def route5(E, k=0.5, proxy=28, start='2025-12-16'):   # route 5 opened 16.12.2025 (organizer GTFS directory)
    src = E[(E.route == proxy) & (E.date >= start)].prediction.values
    E.loc[(E.route == 5) & (E.date >= start), 'prediction'] = src * k; return E

def weekend_restore(E, rt, start, end, k=1.0):  # weekend track repairs ended → weekend service back
    p = normal_weekend_profile(rt)
    m = (E.route == rt) & (E.date >= start) & (E.date <= end) & (E.date.dt.dayofweek >= 5)
    new = np.array([p.get((d.dayofweek, h), 0.0) for d, h in zip(E.loc[m,'date'], E.loc[m,'hour'])])
    E.loc[m, 'prediction'] = E.loc[m, 'prediction'] * (1 - k) + new * k; return E

def scale(E, k, start='2025-11-01', end='2025-12-31', routes=None):
    m = (E.date >= start) & (E.date <= end) & (E.route != 5)
    if routes is not None: m &= E.route.isin(routes)
    E.loc[m, 'prediction'] *= k; return E

def build(steps):
    E = E0.copy(); E['prediction'] = E.prediction.astype(float)
    for f, kw in steps: E = f(E, **kw)
    return E

def save(E, name, ref=None):
    o = E[['route','date','hour','prediction']].copy(); o['date'] = o.date.dt.strftime('%Y-%m-%d')
    o['prediction'] = o.prediction.clip(lower=0).round().astype(int)
    o.to_csv(f'submissions/{name}.csv', sep=';', index=False)
    msg = f'{name}: total {o.prediction.sum():,}'
    if ref is not None: msg += f' | vs ref d {o.prediction.sum() - ref.prediction.round().sum():+,.0f}, L1 {np.abs(o.prediction.values - ref.prediction.round().values).sum():,.0f}'
    print(msg); return o

BEST = [(ny_night, {}), (route5, {'k': 0.5})]   # LB 0.88836

# Weather: fitted on 260 days of 1-week-ahead nowcast residuals (Feb–Oct 2025), see INSIGHTS #24.
_W = pd.read_csv('research/weather_moscow_2025.csv'); _W['ts'] = pd.to_datetime(_W.datetime)
_WD = _W[(_W.ts.dt.hour >= 6) & (_W.ts.dt.hour <= 21)].groupby(_W.ts.dt.normalize()).agg(pr=('precipitation','sum'), t=('temperature_2m','mean'))

def weather(E, b_pr=-0.011, b_cold=-0.034, floor=0.9):
    """Centered on the precipitation of the level window (Oct 18–31), so a 'typical' day keeps multiplier 1."""
    ref_pr = _WD.loc['2025-10-18':'2025-10-31', 'pr'].mean()
    w = _WD.reindex(E.date)
    mult = np.exp(b_pr * (w.pr.fillna(0).values - ref_pr) + b_cold * (w.t.values < -10))
    E['weather_mult'] = np.clip(mult, floor, 1.05)
    m = E.route != 5
    E.loc[m, 'prediction'] *= E.loc[m, 'weather_mult']; return E

def scale_ordinary(E, k, start='2025-11-05', end='2025-12-25', skip_restored=True):
    """Level correction on ordinary days only (not special days, not route 5, not the rebuilt r50/r7 Dec weekends)."""
    m = (E.date >= start) & (E.date <= end) & (E.route != 5)
    if skip_restored: m &= ~(E.route.isin([7, 50]) & (E.date >= '2025-12-01') & (E.date.dt.dayofweek >= 5))
    E.loc[m, 'prediction'] *= k; return E

BEST = [(ny_night, {}), (route5, {'k': 0.5}),
        (weekend_restore, {'rt': 50, 'start': '2025-12-01', 'end': '2025-12-31'}),
        (weekend_restore, {'rt': 7, 'start': '2025-12-01', 'end': '2025-12-31'})]   # LB 0.89480 (v06)

# Analyst round 2 (offline-validated, +0.0049 mean on 6/6 folds): shape = 0.3·4-week + 0.7·clean long-history anchor
# (capped ±50 %), level = median of clean recent days (no school break / Oct 31). Applied as per-cell ratio to the base.
def clean_level_anchor_shape(E, path='experiments/analyst/r2_nov_dec_ratio.csv'):
    r = pd.read_csv(path, sep=';', parse_dates=['date'])
    E = E.merge(r, on=['route','date','hour'], how='left'); E['ratio'] = E.ratio.fillna(1.0)
    keep = ((E.date == '2025-11-01') & (E.hour <= 1)) | \
           ((E.route == 50) & (E.date < '2025-12-01') & (E.date.dt.dayofweek >= 5))   # exact leak cells; r50 Nov weekends under repair
    E.loc[keep, 'ratio'] = 1.0
    E['base'] *= E.ratio; E['prediction'] *= E.ratio
    return E.drop(columns='ratio')

BEST_V07 = [(clean_level_anchor_shape, {})] + BEST

def route5_opening(E, day='2025-12-16', hour=18):   # opening ceremony 16.12 ~18:06 (Deptrans) → no service before
    E.loc[(E.route == 5) & (E.date == day) & (E.hour < hour), 'prediction'] = 0; return E

# Deptrans t.me/DtOperativno/23565: routes 7 & 50 normal weekend service from 15.11.2025
BEST_V08 = [(clean_level_anchor_shape, {}), (ny_night, {}), (route5, {'k': 0.5}), (route5_opening, {}),
            (weekend_restore, {'rt': 50, 'start': '2025-11-15', 'end': '2025-12-31'}),
            (weekend_restore, {'rt': 7,  'start': '2025-11-15', 'end': '2025-12-31'})]
