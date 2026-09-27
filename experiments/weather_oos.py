"""Out-of-sample check of the weather multiplier: coefficients fitted ONLY on days before each fold origin."""
import sys, os; sys.path.insert(0, 'src')
import pandas as pd, numpy as np, statsmodels.api as sm
from common import load_labels, wape_score
from model_ls import forecast
d = load_labels(); d = d[d.route != 5]
w = pd.read_csv('research/weather_moscow_2025.csv'); w['ts'] = pd.to_datetime(w.datetime); w = w[(w.ts.dt.hour >= 6) & (w.ts.dt.hour <= 21)]
wd = w.groupby(w.ts.dt.normalize()).agg(pr=('precipitation','sum'), t=('temperature_2m','mean'))
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date']).set_index('date')
res = []
for o in pd.date_range('2025-02-03', '2025-10-27', freq='7D'):
    hist, fut = d[d.date < o], d[(d.date >= o) & (d.date < o + pd.Timedelta(days=7))].copy()
    fut['p'] = forecast(hist, fut, 2, 4, 'wk4', 'median', 'sum'); res.append(fut)
R = pd.concat(res); R = R[R.p > 0]
day = R.groupby('date')[['boardings','p']].sum(); day['lr'] = np.log(day.boardings / day.p)
day = day.join(wd).join(cal[['is_holiday','is_preholiday_shortened']])
ok = (day.is_preholiday_shortened == 0) & (day.lr.abs() < 0.4) & ~((day.is_holiday == 1) & (day.index.dayofweek < 5))
out = []
for s, e in [('2025-05-01','2025-06-30'), ('2025-07-01','2025-08-31'), ('2025-09-01','2025-10-31'), ('2025-04-01','2025-05-31')]:
    tr = day[ok & (day.index < s)]
    X = sm.add_constant(np.c_[tr.pr - tr.pr.mean(), (tr.t < -10).astype(int)]); b = sm.OLS(tr.lr, X).fit().params.values
    te = R[(R.date >= s) & (R.date <= e)].join(wd, on='date')
    ref = day[(day.index < s)].pr.tail(14).mean()
    m = np.clip(np.exp(b[1] * (te.pr - ref) + b[2] * (te.t < -10)), 0.9, 1.05)
    out.append((s, round(b[1], 4), round(wape_score(te.boardings, te.p), 4), round(wape_score(te.boardings, te.p * m), 4)))
print(pd.DataFrame(out, columns=['fold', 'b_precip(fit before fold)', 'no weather', 'with weather']).to_string())
