"""Round-2 analyst harness: generalised level x shape forecast, scored on model_ls.FOLDS.
Run from hach_metro dir:  python experiments/analyst/r2_harness.py"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src'))
import pandas as pd, numpy as np
from common import load_labels, wape_score, ROUTES
from model_ls import FOLDS, dtmap, forecast as base_forecast
from model_profile import daytype, cal

D = load_labels()
D['dt'] = dtmap(daytype(D.date), 'wk4')
DAILY = D.groupby(['route', 'date', 'dt']).boardings.sum().rename('tot').reset_index()
DAILY = DAILY[DAILY.route != 5]


def trimmed(x):
    x = np.sort(np.asarray(x, float))
    return x[1:-1].mean() if len(x) >= 4 else np.median(x)


def level(hist_daily, end, WL=2, lagg='median', WL_we=None, excl=(), outlier=None, pooled_long=None):
    dd = hist_daily[~hist_daily.date.isin(pd.to_datetime(list(excl)))]
    out = []
    for dt in [0, 4, 5, 6]:
        w = WL_we if (WL_we is not None and dt in (5, 6)) else WL
        g = dd[(dd.dt == dt) & (dd.date > end - pd.Timedelta(weeks=w))]
        if outlier is not None:  # drop days < outlier * route median in the window (e.g. disruptions)
            med = g.groupby('route').tot.transform('median')
            g = g[g.tot >= outlier * med]
        if lagg == 'median': L = g.groupby('route').tot.median()
        elif lagg == 'mean': L = g.groupby('route').tot.mean()
        elif lagg == 'trim': L = g.groupby('route').tot.agg(trimmed)
        elif lagg == 'max': L = g.groupby('route').tot.max()
        elif lagg == 'last': L = g.sort_values('date').groupby('route').tot.last()
        elif lagg.startswith('ew'):  # exponentially weighted by age, half-life in days
            hl = float(lagg[2:]); g = g.assign(wt=0.5 ** ((end - g.date).dt.days / hl))
            L = (g.tot * g.wt).groupby(g.route).sum() / g.wt.groupby(g.route).sum()
        out.append(pd.DataFrame({'route': L.index, 'dt': dt, 'L': L.values}))
    L = pd.concat(out)
    if pooled_long is not None:
        # weekday-ratio approach: level_dt = recent Mon-Thu level * long-window ratio(dt / Mon-Thu)
        g = dd[dd.date > end - pd.Timedelta(weeks=pooled_long)]
        r = g.groupby(['route', 'dt']).tot.median().unstack()
        r = r.div(r[0], axis=0)
        L = L.merge(r.stack().rename('ratio').reset_index(), on=['route', 'dt'])
        base = L[L.dt == 0].set_index('route').L
        L['L'] = np.where(L.dt == 0, L.L, L.route.map(base) * L.ratio)
        L = L.drop(columns='ratio')
    return L.set_index(['route', 'dt']).L


def shape(hist, end, WS=4, est='sum', shrink_k=0.0, prior_WS=None, prior='long'):
    hs = hist[hist.date > end - pd.Timedelta(weeks=WS)]
    num = hs.groupby(['route', 'dt', 'hour']).boardings.sum()
    den = num.groupby(level=[0, 1]).transform('sum')
    if est == 'sum':
        S = num / den
    else:  # median / mean of daily shares
        tot = hs.groupby(['route', 'date']).boardings.transform('sum')
        sh = (hs.boardings / tot.replace(0, np.nan)).fillna(0)
        S = sh.groupby([hs.route, hs.dt, hs.hour]).agg(est)
        S = S / S.groupby(level=[0, 1]).transform('sum')
    if shrink_k > 0:
        # James-Stein-like: S* = (n*S + k*P)/(n+k), n = boardings in window per route-dt (in thousands)
        if prior == 'long':
            hp = hist[hist.date > end - pd.Timedelta(weeks=prior_WS)]
            pn = hp.groupby(['route', 'dt', 'hour']).boardings.sum()
            P = pn / pn.groupby(level=[0, 1]).transform('sum')
        elif prior == 'pooled':  # all routes pooled, per dt
            pn = hs.groupby(['dt', 'hour']).boardings.sum()
            P = (pn / pn.groupby(level=0).transform('sum'))
            P = S.to_frame('S').join(P.rename('P'), on=['dt', 'hour']).P
        n = den / 1000.0
        P = P.reindex(S.index).fillna(S)
        S = (n * S + shrink_k * P) / (n + shrink_k)
    return S


def forecast(hist, target, WL=2, WS=4, lagg='median', WL_we=None, excl=(), outlier=None, mult=1.0,
             pooled_long=None, est='sum', shrink_k=0.0, prior_WS=12, prior='long', shape_adj=None, mult_dt=None):
    end = hist.date.max()
    hd = DAILY[DAILY.date <= end]
    L = level(hd, end, WL, lagg, WL_we, excl, outlier, pooled_long)
    S = shape(hist, end, WS, est, shrink_k, prior_WS, prior)
    t = target[['route', 'date', 'hour', 'dt']].join(L, on=['route', 'dt']).join(S.rename('S'), on=['route', 'dt', 'hour'])
    p = (t.L * t.S).fillna(0).values * mult
    if mult_dt is not None:
        p = p * t.dt.map(mult_dt).fillna(1.0).values
    if shape_adj is not None:
        p = shape_adj(t, p, hist)
    return p


def score(**kw):
    r = {}
    for s, e in FOLDS:
        hist, fut = D[D.date < s], D[(D.date >= s) & (D.date <= e)]
        r[s] = wape_score(fut.boardings.values, forecast(hist, fut, **kw))
    return pd.Series(r)


if __name__ == '__main__':
    b = score()
    # sanity: reproduce model_ls
    chk = {}
    for s, e in FOLDS:
        hist, fut = D[D.date < s], D[(D.date >= s) & (D.date <= e)]
        chk[s] = wape_score(fut.boardings.values, base_forecast(hist.drop(columns='dt'), fut, 2, 4, 'wk4', 'median'))
    print(pd.DataFrame({'harness': b, 'model_ls': pd.Series(chk)}).round(5), b.mean())
