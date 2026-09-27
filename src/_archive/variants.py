"""Hypothesis probes on top of v02. Each variant changes ONE thing vs base v03, so LB delta isolates it.
base v03 = v02 + Dec 31 20–23h ≈ 0 (free fare on New Year night, validators not used)."""
import pandas as pd, numpy as np
from common import load_labels
E = pd.read_csv('submissions/v02_ls_special_explain.csv', sep=';', parse_dates=['date'])
d = load_labels(); dd = d.groupby(['route','date']).boardings.sum().unstack(0)
dec = E.date >= '2025-12-01'; wkend = E.date.dt.dayofweek >= 5

def save(df, name):
    o = df[['route','date','hour','prediction']].copy(); o['date'] = o.date.dt.strftime('%Y-%m-%d')
    o['prediction'] = o.prediction.clip(lower=0).round().astype(int); o.to_csv(f'submissions/{name}.csv', sep=';', index=False)
    print(name, 'total', o.prediction.sum())

base = E.copy(); base.loc[(base.date == '2025-12-31') & (base.hour >= 20), 'prediction'] = 0
save(base, 'v03_base')

def normal_weekend(rt, periods):
    """Pre-repair weekend profile: hourly shares × (Sat/Sun-to-weekday ratio) × current weekday level."""
    h = d[(d.route == rt) & d.date.isin(periods)].copy(); h['dt'] = np.where(h.date.dt.dayofweek == 5, 5, 6)
    wk = dd.loc[periods, rt]; wkday = wk[wk.index.dayofweek <= 4].median()
    prof = h.groupby(['dt','hour']).boardings.median() / wkday     # per-hour fraction of a weekday total
    cur = dd[rt]['2025-10-13':'2025-10-31']; cur_wk = cur[cur.index.dayofweek <= 4].median()
    return prof * cur_wk

per = pd.date_range('2025-03-01','2025-06-04').union(pd.date_range('2025-08-08','2025-09-05'))
for rt in [50, 7]:
    v = base.copy(); p = normal_weekend(rt, per)
    m = (v.route == rt) & dec & wkend
    v.loc[m, 'prediction'] = [p.get((5 if x.dayofweek == 5 else 6, h), 0) for x, h in zip(v.loc[m,'date'], v.loc[m,'hour'])]
    save(v, f'v03_probe_r{rt}_dec_weekend_normal')

# route 5 opened 2025-12-16 (organizer GTFS directory). Shape/level proxy = route 28 (similar short central route), scale k.
for k in [0.5, 1.0]:
    v = base.copy(); src = v[(v.route == 28) & (v.date >= '2025-12-16')].prediction.values
    v.loc[(v.route == 5) & (v.date >= '2025-12-16'), 'prediction'] = src * k
    save(v, f'v03_probe_r5_k{k}')
