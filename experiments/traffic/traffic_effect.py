"""Effect of road congestion (ЦОДД score from t.me/DtOperativno) on tram ridership nowcast residuals.
Run from hach_metro: python experiments/traffic/traffic_effect.py
"""
import sys; sys.path.insert(0, 'src')
import pandas as pd, numpy as np, statsmodels.api as sm
from common import load_labels
from model_ls import forecast

d = load_labels(); d = d[d.route != 5]
res = []
for o in pd.date_range('2025-02-03', '2025-10-27', freq='7D'):
    hist, fut = d[d.date < o], d[(d.date >= o) & (d.date < o + pd.Timedelta(days=7))].copy()
    fut['p'] = forecast(hist, fut, 2, 4, 'wk4', 'median', 'sum'); res.append(fut)
R = pd.concat(res); R = R[R.p > 0]
R.to_parquet('experiments/traffic/nowcast_hourly.parquet')

w = pd.read_csv('research/weather_moscow_2025.csv'); w['ts'] = pd.to_datetime(w.datetime)
w6 = w[(w.ts.dt.hour >= 6) & (w.ts.dt.hour <= 21)]
wd = w6.groupby(w6.ts.dt.normalize()).agg(pr=('precipitation', 'sum'), snow=('snowfall', 'sum'), t=('temperature_2m', 'mean'))
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date']).set_index('date')
T = pd.read_csv('research/traffic_moscow_2025_daily.csv', parse_dates=['date']).set_index('date')

day = R.groupby('date')[['boardings', 'p']].sum(); day['lr'] = np.log(day.boardings / day.p)
day = day.join(wd).join(cal[['is_dayoff', 'is_holiday', 'is_preholiday_shortened']]).join(T)
day['dow'] = day.index.dayofweek
ok = (day.is_preholiday_shortened == 0) & (day.lr.abs() < 0.4) & (day.is_dayoff == 0)
wk = day[ok & (day.dow < 5)].copy()   # working days only (ЦОДД reports practically only on working days)
wk['fri'] = (wk.dow == 4).astype(int)
wk['heavy'] = (wk.max_score >= 7).astype(int)          # evening "7+ баллов" alert
wk['score0'] = wk.max_score.fillna(4)                   # unreported working day ~ normal (≈4)
# anomaly vs same weekday: score minus mean score of that weekday (over reported days)
wk['score_anom'] = wk.score0 - wk.groupby('dow').score0.transform('mean')
wk['score_anom3w'] = wk.score0 - wk.score0.rolling(15, min_periods=5).mean()
wk['cold'] = (wk.t < -10).astype(int)


def fit(y, cols, df, name):
    df = df.dropna(subset=cols); y = y.loc[df.index]
    X = sm.add_constant(df[cols].astype(float)); m = sm.OLS(y, X).fit(cov_type='HC1')
    c = cols[0]
    return {'spec': name, 'n': int(m.nobs), 'var': c, 'coef': m.params[c], 'se': m.bse[c], 'p': m.pvalues[c],
            'b_precip': m.params.get('pr', np.nan), 'p_precip': m.pvalues.get('pr', np.nan), 'R2': m.rsquared}


rows = []
ctrl = ['pr', 'cold', 'fri']
rows.append(fit(wk.lr, ['heavy'] + ctrl, wk, 'A heavy(>=7) flag, all working days'))
rows.append(fit(wk.lr, ['heavy'], wk, 'A0 heavy flag, no controls'))
rows.append(fit(wk.lr, ['score_anom'] + ctrl, wk, 'B score anomaly vs weekday mean (unreported=4)'))
rows.append(fit(wk.lr, ['score_anom3w'] + ctrl, wk.dropna(subset=['score_anom3w']), 'C score − rolling 3-wk mean'))
rep = wk[wk.reported == 1]
rows.append(fit(rep.lr, ['max_score'] + ctrl, rep.dropna(subset=['max_score']), 'D score, reported days only'))
rows.append(fit(wk.lr, ['reported'] + ctrl, wk, 'E any ЦОДД post that day'))
nof = wk[wk.fri == 0]
rows.append(fit(nof.lr, ['heavy', 'pr', 'cold'], nof, 'F heavy flag, Mon–Thu only'))
sp = wk.dropna(subset=['min_speed'])
rows.append(fit(sp.lr, ['min_speed', 'pr', 'cold', 'fri'], sp, 'G min avg speed km/h (days with speed)'))
out = pd.DataFrame(rows)
pd.set_option('display.width', 250)
print(out.round(4).to_string(index=False))
print('\nheavy vs normal working days: mean lr', wk.groupby('heavy').lr.agg(['mean', 'count']).round(4).to_dict())
print('precip on heavy vs not:', wk.groupby('heavy').pr.mean().round(2).to_dict())

# hourly: does the evening (17-20h) share of the residual rise on heavy days?
H = R[R.date.isin(wk.index)].copy()
H['blk'] = np.select([H.hour.between(7, 10), H.hour.between(17, 20)], ['am', 'pm'], 'other')
B = H.groupby(['date', 'blk'])[['boardings', 'p']].sum().unstack()
hb = pd.DataFrame({'lr_pm': np.log(B.boardings.pm / B.p.pm), 'lr_am': np.log(B.boardings.am / B.p.am),
                   'lr_day': wk.lr}).join(wk[['heavy', 'pr', 'cold', 'fri', 'score_anom']])
hb['pm_minus_day'] = hb.lr_pm - hb.lr_day
hb = hb.dropna(subset=["lr_pm", "lr_am", "lr_day"])
hrows = [fit(hb.pm_minus_day, ['heavy', 'pr', 'cold', 'fri'], hb, 'H1 evening(17-20) resid − day resid ~ heavy'),
         fit(hb.lr_pm, ['heavy', 'pr', 'cold', 'fri'], hb, 'H2 evening(17-20) resid ~ heavy'),
         fit(hb.lr_am, ['heavy', 'pr', 'cold', 'fri'], hb, 'H3 morning(7-10) resid ~ heavy')]
# hour-level alignment: residual in the hour of the post vs same hour on non-alert days
P = pd.read_csv('research/traffic_moscow_2025.csv', parse_dates=['date'])
P = P[P.score >= 7]
hh = H.groupby(['date', 'hour'])[['boardings', 'p']].sum(); hh['lr'] = np.log(hh.boardings / hh.p)
hh = hh.reset_index().merge(wk[['lr']].rename(columns={'lr': 'lr_day'}), left_on='date', right_index=True)
hh['rel'] = hh.lr - hh.lr_day
key = set(zip(P.date, P.hour)) | set(zip(P.date, P.hour + 1))
hh['alert_hr'] = [int((a, b) in key) for a, b in zip(hh.date, hh.hour)]
hh = hh[hh.hour.between(15, 21)].join(wk[['pr', 'fri']], on='date')
hh = pd.concat([hh, pd.get_dummies(hh.hour, prefix='h', drop_first=True).astype(int)], axis=1)
hrows.append(fit(hh.rel, ['alert_hr'] + [c for c in hh.columns if c.startswith('h_')], hh,
                 'H4 hour-of-alert (+1h) rel. resid, 15-21h, hour FE'))
print(pd.DataFrame(hrows).round(4).to_string(index=False))
out.to_csv('experiments/traffic/effect_daily.csv', index=False)
pd.DataFrame(hrows).to_csv('experiments/traffic/effect_hourly.csv', index=False)
