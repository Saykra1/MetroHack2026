"""Backtest simple profile models. Folds mimic the 61-day horizon."""
import pandas as pd, numpy as np
from common import load_labels, full_grid, wape_score
d = load_labels(); d['dow'] = d.date.dt.dayofweek
FOLDS = [('2025-09-01','2025-10-31'), ('2025-10-01','2025-10-31'), ('2025-07-01','2025-08-31'), ('2025-05-01','2025-06-30')]

def profile(hist, weeks, agg):
    h = hist[hist.date >= hist.date.max() - pd.Timedelta(weeks=weeks)]
    return h.groupby(['route','dow','hour']).boardings.agg(agg).rename('p').reset_index()

for s, e in FOLDS:
    hist, fut = d[d.date < s], d[(d.date >= s) & (d.date <= e)]
    res = {}
    for w in [2, 4, 6, 8, 12]:
        for agg in ['mean', 'median']:
            p = fut.merge(profile(hist, w, agg), on=['route','dow','hour'], how='left').p.fillna(0)
            res[f'{agg}{w}w'] = round(wape_score(fut.boardings.values, p.values), 4)
    # oracle: same-period profile (upper bound of a perfect level/shape)
    o = fut.merge(fut.groupby(['route','dow','hour']).boardings.median().rename('p').reset_index(), on=['route','dow','hour']).p
    res['ORACLE_inperiod_median'] = round(wape_score(fut.boardings.values, o.values), 4)
    print(s, e, res)
