"""Model C: LightGBM correction on top of level×shape base (direct multi-horizon, many origins).
target = y/base (L1, weight=base) ⇔ minimizes Σ|y−ŷ| (WAPE)."""
import pandas as pd, numpy as np, lightgbm as lgb, sys
from common import load_labels, full_grid, wape_score
from build_submission import predict as base_predict

cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])
w = pd.read_csv('research/weather_moscow_2025.csv'); w['ts'] = pd.to_datetime(w.datetime)
w['date'] = w.ts.dt.normalize(); w['hour'] = w.ts.dt.hour
wd = w.groupby('date').agg(t_day=('temperature_2m','mean'), pr_day=('precipitation','sum'), sn_day=('snowfall','sum')).reset_index()
W = w[['date','hour','temperature_2m','precipitation','snowfall','wind_speed_10m']].merge(wd, on='date')

def feats(t, origin):
    t = t.merge(cal[['date','is_dayoff','is_holiday','is_preholiday_shortened','is_school_holiday','is_transferred_workday']], on='date', how='left')
    t = t.merge(W, on=['date','hour'], how='left')
    t['dow'] = t.date.dt.dayofweek; t['h_days'] = (t.date - origin).dt.days
    t['logbase'] = np.log1p(t.base)
    return t

def make(d, origin, end, WS=True):
    hist = d[d.date < origin]; tgt = d[(d.date >= origin) & (d.date <= end)]
    t = base_predict(hist, tgt, special=False)[['route','date','hour','base']]
    t = feats(t, origin)
    t['y'] = tgt.boardings.values
    return t

F_ALL = ['route','hour','dow','h_days','logbase','is_dayoff','is_holiday','is_preholiday_shortened','is_school_holiday',
         'temperature_2m','precipitation','snowfall','wind_speed_10m','t_day','pr_day','sn_day']
F_NOTEMP = [f for f in F_ALL if f not in ('temperature_2m','t_day')]

def train(tr, F, seed=0):
    tr = tr[tr.base > 0]
    m = lgb.LGBMRegressor(objective='l1', n_estimators=400, learning_rate=0.03, num_leaves=31, min_child_samples=200,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=seed, verbose=-1)
    m.fit(tr[F], (tr.y / tr.base).clip(0, 5), sample_weight=tr.base, categorical_feature=['route'])
    return m

def origins(start, stop): return pd.date_range(start, stop, freq='7D')

if __name__ == '__main__':
    d = load_labels(); d = d[d.route != 5]
    folds = [('2025-10-01','2025-10-31'), ('2025-09-15','2025-10-31'), ('2025-04-01','2025-05-31')]
    cache = {}
    for s, e in folds:
        s = pd.Timestamp(s); e = pd.Timestamp(e)
        tr = pd.concat([make(d, o, min(o + pd.Timedelta(days=60), s - pd.Timedelta(days=1))) for o in origins('2025-02-03', s - pd.Timedelta(days=14))])
        te = make(d, s, e)
        out = {'base': wape_score(te.y, te.base)}
        for name, F in [('all', F_ALL), ('notemp', F_NOTEMP)]:
            m = train(tr, F); out[name] = wape_score(te.y, te.base * m.predict(te[F]))
        print(s.date(), {k: round(v, 4) for k, v in out.items()}, flush=True)
