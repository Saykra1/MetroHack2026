"""Component 2 — probabilistic forecast: P10 / P50 / P90 per (route, date, hour) around the structural forecast.

Candidates (validated on rolling-origin folds, training = origins/targets strictly before the fold origin):
  conf_hdh   split-conformal: empirical quantiles of r = y/base by (hour, day type, horizon bucket)
  conf_rbdh  same by (route, hour band, day type, horizon bucket)
  lgb_q      LightGBM quantile regression (alpha 0.1/0.5/0.9) on r, core features
All intervals are centred on the point forecast: p50 = base, pX = base * qX / q50 (so p50 == v08 prediction).
Metrics: coverage of [P10, P90] (target 80 %), coverage weighted by y, mean pinball loss / sum(y) (x100).
Usage:  python src/ml/quantiles.py      ->  experiments/ml/quantile_folds.csv, experiments/ml/intervals.csv"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
from scipy.stats import norm
import lightgbm as lgb

ALPHAS = (0.1, 0.5, 0.9)
HB = np.array([0] * 6 + [1] * 4 + [2] * 6 + [3] * 4 + [4] * 4)       # hour bands: night, am peak, day, pm peak, evening
GROUPS = {'conf_hdh': ['hour', 'dt', 'h_bucket'], 'conf_rbdh': ['route', 'hb', 'dt', 'h_bucket']}
F_Q = ['route', 'hour', 'dt', 'h_days', 'is_dayoff', 'is_holiday', 'is_school_holiday', 'logbase', 'lvl_ratio', 'S4', 'SA']


def prep(P):
    P = P[P.base > 1].copy(); P['hb'] = HB[P.hour]; P['r'] = P.y / P.base; return P


def conformal_table(tr, keys, alphas=ALPHAS):
    q = tr.groupby(keys).r.quantile(list(alphas)).unstack(); q.columns = [f'q{int(a * 100)}' for a in alphas]
    return q


def conformal_predict(tab, te, keys, widen=1.0):
    x = te[keys].join(tab, on=keys)
    for c in tab.columns: x[c] = x[c].fillna(tab[c].median())
    q50 = x.q50.clip(lower=0.05)
    lo, hi = (x.q10 / q50).clip(upper=1), (x.q90 / q50).clip(lower=1, upper=5)
    lo, hi = 1 - (1 - lo) * widen, 1 + (hi - 1) * widen                          # optional symmetric widening
    b = te.base.values
    return b * np.clip(lo.values, 0, 1), b, b * np.maximum(hi.values, 1)


def lgb_quantile(tr, te, F=F_Q):
    out = []
    Xtr = tr[F].copy(); Xtr['route'] = Xtr.route.astype('category')
    Xte = te[F].copy(); Xte['route'] = pd.Categorical(Xte.route, categories=Xtr.route.cat.categories)
    for a in ALPHAS:
        m = lgb.LGBMRegressor(objective='quantile', alpha=a, n_estimators=200, learning_rate=0.03, num_leaves=15,
                              min_child_samples=1000, reg_lambda=10, subsample=0.7, subsample_freq=1, verbose=-1, random_state=0)
        m.fit(Xtr, tr.r.clip(0, 3)); out.append(m.predict(Xte))
    q10, q50, q90 = out; b = te.base.values
    return b * np.clip(q10 / q50, 0, 1), b, b * np.maximum(q90 / q50, 1)


def pinball(y, q, a): d = y - q; return np.sum(np.maximum(a * d, (a - 1) * d))


def metrics(y, p10, p50, p90):
    inside = (y >= p10) & (y <= p90)
    pl = np.mean([pinball(y, p, a) for p, a in zip((p10, p50, p90), ALPHAS)]) / y.sum() * 100
    return {'cov80': inside.mean(), 'cov80_w': np.sum(inside * y) / y.sum(), 'below_p10': (y < p10).mean(),
            'above_p90': (y > p90).mean(), 'pinball_pct': pl, 'rel_width': np.sum(p90 - p10) / np.sum(p50)}


WIDEN = (1.0, 1.15, 1.3, 1.5)


def run_folds(P, recent_weeks=(None, 16)):
    P = prep(P); rows = []
    for s, e in FOLDS:
        tr, te = fold_split(P, s, e)
        if len(tr) < 30000: continue
        for rw in recent_weeks:
            trr = tr if rw is None else tr[tr.origin >= pd.Timestamp(s) - pd.Timedelta(weeks=rw)]
            cands = {f'{n}_x{wd}': conformal_predict(conformal_table(trr, k), te, k, wd) for n, k in GROUPS.items() for wd in WIDEN}
            if rw is None: cands['lgb_q'] = lgb_quantile(trr, te)
            for n, (a, b, c) in cands.items():
                rows.append({'fold': s, 'train': 'all' if rw is None else f'last{rw}w', 'method': n, **metrics(te.y.values, a, b, c)})
        print(s, flush=True)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- capacity risk
def prob_exceed(df, capacity):
    """P(load > capacity) per row from (p10, p50, p90), assuming a split log-normal around p50:
    sigma_lo = ln(p50/p10)/1.2816, sigma_hi = ln(p90/p50)/1.2816.
    capacity: scalar, array aligned with df, dict {hour: cap}, or Series indexed by hour."""
    if isinstance(capacity, dict): capacity = df.hour.map(capacity).values
    elif isinstance(capacity, pd.Series): capacity = df.hour.map(capacity).values
    cap = np.broadcast_to(np.asarray(capacity, float), (len(df),))
    p10, p50, p90 = (df[c].values.astype(float) for c in ('p10', 'p50', 'p90'))
    z = norm.ppf(0.9)
    with np.errstate(divide='ignore', invalid='ignore'):
        s_lo = np.log(np.maximum(p50, 1e-9) / np.maximum(p10, 1e-9)) / z
        s_hi = np.log(np.maximum(p90, 1e-9) / np.maximum(p50, 1e-9)) / z
        zz = np.log(np.maximum(cap, 1e-9) / np.maximum(p50, 1e-9))
        zz = np.where(cap >= p50, zz / np.maximum(s_hi, 1e-9), zz / np.maximum(s_lo, 1e-9))
    p = 1 - norm.cdf(zz)
    return np.where(p50 <= 0, (cap < 0).astype(float), p)


if __name__ == '__main__':
    P = build_panel()
    res = run_folds(P)
    res.to_csv(os.path.join(OUT, 'quantile_folds.csv'), sep=';', index=False)
    summ = res.groupby(['method', 'train'])[['cov80', 'cov80_w', 'below_p10', 'above_p90', 'pinball_pct', 'rel_width']].mean()
    print(summ.round(4).to_string())
    print(res[res.method.str.endswith(('x1.0', 'x1.3')) | (res.method == 'lgb_q')].pivot_table(index='fold', columns=['method', 'train'], values='cov80').round(3).to_string())
    # choose: among candidates with mean coverage within 0.80 ± 0.03, the lowest pinball loss (proper scoring rule)
    ok = summ[(summ.cov80 - 0.8).abs() <= 0.03]
    best = ok.pinball_pct.idxmin(); print('chosen:', best, ok.loc[best].round(4).to_dict())
    method, train = best

    # ---- Nov-Dec intervals aligned to v08
    Pp = prep(P)
    if train != 'all': Pp = Pp[Pp.origin >= pd.Timestamp('2025-11-01') - pd.Timedelta(weeks=int(train[4:-1]))]
    fut = add_features(panel_for_origin('2025-11-01', '2025-12-31', hist=D, with_y=False)); fut['hb'] = HB[fut.hour]
    if method == 'lgb_q':
        lo, _, hi = lgb_quantile(Pp, fut.assign(base=fut.base.clip(lower=1)))
    else:
        gname, wd = method.rsplit('_x', 1); keys = GROUPS[gname]
        lo, _, hi = conformal_predict(conformal_table(Pp, keys), fut.assign(base=fut.base.clip(lower=1)), keys, float(wd))
    fut['rlo'] = lo / fut.base.clip(lower=1); fut['rhi'] = hi / fut.base.clip(lower=1)
    v08 = pd.read_csv(os.path.join(ROOT, 'submissions', 'v08_nov15_weekends.csv'), sep=';', parse_dates=['date'])
    o = v08.merge(fut[['route', 'date', 'hour', 'rlo', 'rhi']], on=['route', 'date', 'hour'], how='left')
    # route 5 (new, proxy-based) and rule cells: wider, documented heuristic bands
    r5 = o.route == 5
    wide = r5 | (o.date >= '2025-12-29') | (o.route.isin([7, 50]) & (o.date >= '2025-11-15') & (o.date.dt.dayofweek >= 5))
    o['rlo'] = o.rlo.fillna(0.5); o['rhi'] = o.rhi.fillna(1.6)
    o.loc[wide, 'rlo'] = np.minimum(o.loc[wide, 'rlo'], 0.6); o.loc[wide, 'rhi'] = np.maximum(o.loc[wide, 'rhi'], 1.5)
    o.loc[r5, 'rlo'] = 0.4; o.loc[r5, 'rhi'] = 1.8
    o['p50'] = o.prediction.astype(float)
    o['p10'] = (o.p50 * o.rlo).round(1); o['p90'] = (o.p50 * o.rhi).round(1)
    ny = (o.date == '2025-12-31') & (o.hour >= 20); o.loc[ny, ['p10', 'p50', 'p90']] = 0.0    # free fare → no validations
    o['date'] = o.date.dt.strftime('%Y-%m-%d')
    o[['route', 'date', 'hour', 'p10', 'p50', 'p90']].to_csv(os.path.join(OUT, 'intervals.csv'), sep=';', index=False)
    print('intervals.csv:', len(o), 'rows; sum p10/p50/p90', o.p10.sum().round(), o.p50.sum().round(), o.p90.sum().round())
    # demo: risk of exceeding 1.3x the typical Oct peak hour on route 17
    demo = o[(o.route == 17)].copy(); cap = 1.1 * demo.p50.max()
    demo['p_exceed'] = prob_exceed(demo, cap)
    print('demo route 17, capacity = 1.1 x max p50:', demo.sort_values('p_exceed', ascending=False).head(5)[['date', 'hour', 'p10', 'p50', 'p90', 'p_exceed']].round(3).to_string())
