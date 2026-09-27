"""Model B: level × shape. pred = L(route, daytype) * S(route, daytype, hour).
L = robust daily total over last WL weeks; S = hourly share over last WS weeks."""
import pandas as pd, numpy as np, itertools
from common import load_labels, full_grid, wape_score
from model_profile import daytype

FOLDS = [('2025-10-01','2025-10-31'), ('2025-09-15','2025-10-31'), ('2025-02-01','2025-03-31'),
         ('2025-03-01','2025-04-30'), ('2025-04-01','2025-05-31'), ('2025-09-01','2025-10-31')]

def dtmap(dt, mode):
    if mode == 'dow': return dt
    if mode == 'wk3': return np.select([dt <= 4, dt == 5], [0, 5], 6)          # weekday / sat / sun
    if mode == 'wk4': return np.select([dt <= 3, dt == 4, dt == 5], [0, 4, 5], 6)  # mon-thu / fri / sat / sun

def forecast(hist, target, WL=4, WS=8, mode='dow', lagg='median', shape_mode='sum'):
    end = hist.date.max()
    h = hist.copy(); h['dt'] = dtmap(daytype(h.date), mode)
    daily = h.groupby(['route','date','dt']).boardings.sum().rename('tot').reset_index()
    L = daily[daily.date > end - pd.Timedelta(weeks=WL)].groupby(['route','dt']).tot.agg(lagg).rename('L')
    hs = h[h.date > end - pd.Timedelta(weeks=WS)]
    if shape_mode == 'sum':
        S = hs.groupby(['route','dt','hour']).boardings.sum() / hs.groupby(['route','dt']).boardings.sum()
    else:  # median of daily shares
        hs = hs.merge(daily[['route','date','tot']], on=['route','date'])
        hs['sh'] = np.where(hs.tot > 0, hs.boardings / hs.tot, 0)
        S = hs.groupby(['route','dt','hour']).sh.median()
        S = S / S.groupby(level=[0,1]).transform('sum')
    t = target[['route','date','hour']].copy(); t['dt'] = dtmap(daytype(t.date), mode)
    t = t.join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour'])
    return (t.L * t.S).fillna(0).values

if __name__ == '__main__':
    d = load_labels()
    rows = []
    grid = list(itertools.product([2,3,4,6], [4,8,12], ['dow','wk4'], ['median','mean'], ['sum','med']))
    for WL, WS, mode, lagg, sm in grid:
        r = {'WL':WL,'WS':WS,'mode':mode,'lagg':lagg,'shape':sm}
        for s, e in FOLDS:
            hist, fut = d[d.date < s], d[(d.date >= s) & (d.date <= e)]
            r[s] = wape_score(fut.boardings.values, forecast(hist, fut, WL, WS, mode, lagg, sm))
        rows.append(r)
    res = pd.DataFrame(rows); fc = [s for s,_ in FOLDS]
    res['mean'] = res[fc].mean(1); res['autumn'] = res[fc[:2]].mean(1)
    pd.set_option('display.width', 250)
    print(res.sort_values('mean', ascending=False).head(12).round(4).to_string())
    print(res.sort_values('autumn', ascending=False).head(6).round(4).to_string())
