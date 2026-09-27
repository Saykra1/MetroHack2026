"""Model A: recent median profile by (route, daytype, hour); daytype from production calendar."""
import pandas as pd, numpy as np, sys
from common import load_labels, full_grid, wape_score, ROUTES
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])

def daytype(dates, use_cal=True):
    c = pd.DataFrame({'date': dates}).merge(cal, on='date', how='left')
    dt = c.date.dt.dayofweek.values.copy()
    if use_cal:
        dt[(c.is_dayoff == 1) & (c.date.dt.dayofweek < 5)] = 6        # weekday holiday -> Sunday
        dt[(c.is_transferred_workday == 1)] = 4                        # working Saturday -> Friday
    return dt

def forecast(hist, target, weeks=4, use_cal=True, agg='median'):
    h = hist[hist.date > hist.date.max() - pd.Timedelta(weeks=weeks)].copy()
    h['dt'] = daytype(h.date, use_cal)
    prof = h.groupby(['route','dt','hour']).boardings.agg(agg).rename('prediction').reset_index()
    t = target.copy(); t['dt'] = daytype(t.date, use_cal)
    return t.merge(prof, on=['route','dt','hour'], how='left').prediction.fillna(0).values

if __name__ == '__main__':
    d = load_labels()
    for s, e in [('2025-09-01','2025-10-31'),('2025-10-01','2025-10-31'),('2025-05-01','2025-06-30'),('2025-07-01','2025-08-31')]:
        hist, fut = d[d.date < s], d[(d.date >= s) & (d.date <= e)]
        print(s, {f'{w}w cal={c}': round(wape_score(fut.boardings.values, forecast(hist, fut, w, c)), 4) for w in [3,4,6] for c in [False, True]})
    sub = full_grid('2025-11-01', '2025-12-31')
    sub['prediction'] = np.round(forecast(d, sub, 4, True)).astype(int)
    sub.loc[sub.route == 5, 'prediction'] = 0
    sub['date'] = sub.date.dt.strftime('%Y-%m-%d')
    sub.to_csv('submissions/v01_profile_median4w_cal.csv', sep=';', index=False)
    print(sub.shape, sub.groupby('route').prediction.sum())
