"""OOS check: fit heavy-day multiplier on working days before fold start, apply in fold (hourly WAPE).
Uses experiments/traffic/nowcast_hourly.parquet from traffic_effect.py."""
import sys; sys.path.insert(0, 'src')
import pandas as pd, numpy as np, statsmodels.api as sm
from common import wape_score
R = pd.read_parquet('experiments/traffic/nowcast_hourly.parquet')
T = pd.read_csv('research/traffic_moscow_2025_daily.csv', parse_dates=['date']).set_index('date')
P = pd.read_csv('research/traffic_moscow_2025.csv', parse_dates=['date']); P = P[P.score >= 7]
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date']).set_index('date')
w = pd.read_csv('research/weather_moscow_2025.csv'); w['ts'] = pd.to_datetime(w.datetime); w = w[(w.ts.dt.hour >= 6) & (w.ts.dt.hour <= 21)]
wd = w.groupby(w.ts.dt.normalize()).precipitation.sum().rename('pr')
day = R.groupby('date')[['boardings', 'p']].sum(); day['lr'] = np.log(day.boardings / day.p)
day = day.join(T.max_score).join(wd).join(cal.is_dayoff); day['heavy'] = ((day.max_score >= 7) & (day.is_dayoff == 0)).astype(int)
key = set(zip(P.date, P.hour)) | set(zip(P.date, P.hour + 1))
R['alert'] = [int((a, b) in key) for a, b in zip(R.date, R.hour)]
R = R.join(day[['heavy']], on='date')
out = []
for s, e in [('2025-07-01', '2025-08-31'), ('2025-09-01', '2025-10-31'), ('2025-10-01', '2025-10-31')]:
    tr = day[(day.index < s) & (day.is_dayoff == 0) & (day.lr.abs() < 0.4)]
    b = sm.OLS(tr.lr, sm.add_constant(tr[['heavy', 'pr']])).fit().params.heavy
    te = R[(R.date >= s) & (R.date <= e)]
    m1 = np.exp(b * te.heavy)
    m2 = m1 * np.where(te.alert == 1, np.exp(-0.026), 1.0)
    out.append((s, round(b, 4), int(day.loc[s:e].heavy.sum()), round(wape_score(te.boardings, te.p), 5),
                round(wape_score(te.boardings, te.p * m1), 5), round(wape_score(te.boardings, te.p * m2), 5)))
print(pd.DataFrame(out, columns=['fold', 'b_heavy(fit before)', 'heavy days', 'base', '+day mult', '+day&alert-hour']).to_string(index=False))
nd = T.loc['2025-11-01':'2025-12-31']; print('Nov-Dec 2025: reported days', int(nd.reported.sum()), 'heavy(>=7) days', int((nd.max_score >= 7).sum()))
print(nd[nd.max_score >= 7].index.strftime('%m-%d').tolist())
