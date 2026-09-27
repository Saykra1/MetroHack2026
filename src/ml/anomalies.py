"""Component 3 — unsupervised anomaly detection on route-days (Jan-Oct 2025) + "auto-clean" test.

Per route-day features (day category = Mon-Fri / Sat / Sun by weekday, NOT the holiday-aware day type, so holidays show up):
  z_loc    robust z of log(total / median of same-category days within ±21 d, self excluded)  -> short drops/spikes
  z_share  robust z of log(route share of network total / route's median share for the category) -> route-specific
           long disruptions (repairs) that a local window would absorb
  z_shape  robust z of L1 distance between the day's hourly shares and the median profile (±28 d, same category)
Robust z = (x - median) / (1.4826 MAD) per route x category. IsolationForest on (z_loc, z_share, z_shape), fitted
separately for weekdays and weekends; score = IF anomaly score in [0, 1]. Flag = IF top CONTAM share or max|z| > ZMAX.
kind: drop / spike (level dominates, by sign) or shape. label: known cause from calendar / Deptrans facts, else unknown.
Usage:  python src/ml/anomalies.py   ->  experiments/ml/anomalies.csv, experiments/ml/anomaly_autoclean_folds.csv"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
from sklearn.ensemble import IsolationForest
from r2_harness import shape

CONTAM, ZMAX = 0.05, 4.0
CALX = cal.set_index('date')
HOURLY = D[D.route != 5].pivot_table(index=['route', 'date'], columns='hour', values='boardings', aggfunc='sum').fillna(0)


def robust_z(x, groups):
    med = x.groupby(groups).transform('median'); mad = (x - med).abs().groupby(groups).transform('median')
    return (x - med) / (1.4826 * mad.replace(0, np.nan))


def _centred_median(s, days, cat):
    """For each date: median of s over same-category dates within ±days, excluding the date itself. s indexed by date."""
    out = pd.Series(np.nan, index=s.index)
    dates = s.index.values; vals = s.values; c = cat.reindex(s.index).values
    for i, d in enumerate(dates):
        m = (np.abs((dates - d).astype('timedelta64[D]').astype(int)) <= days) & (c == c[i]); m[i] = False
        if m.sum() >= 2: out.iloc[i] = np.median(vals[m])
    return out


def features(end=None):
    """Route-day feature table using only data up to `end` (inclusive)."""
    dd = DAILY if end is None else DAILY[DAILY.date <= end]
    dd = dd[(dd.date >= '2025-01-01')].copy()
    dow = dd.date.dt.dayofweek; dd['cat'] = np.select([dow <= 4, dow == 5], ['wd', 'sat'], 'sun')
    net = dd.groupby('date').tot.sum()
    dd['share'] = dd.tot / dd.date.map(net)
    H = HOURLY.loc[HOURLY.index.get_level_values('date').isin(dd.date.unique())]
    Hs = H.div(H.sum(1).replace(0, np.nan), axis=0).fillna(0)
    rows = []
    for rt, g in dd.groupby('route'):
        g = g.set_index('date').sort_index(); cat = g.cat
        loc = _centred_median(g.tot, 21, cat)
        r_loc = np.log((g.tot + 50) / (loc + 50))
        r_share = np.log((g.share + 1e-4) / (g.groupby('cat').share.transform('median') + 1e-4))
        hs = Hs.loc[rt].reindex(g.index).fillna(0).values
        dist = np.full(len(g), np.nan); dts = g.index.values; c = cat.values
        for i, d in enumerate(dts):
            m = (np.abs((dts - d).astype('timedelta64[D]').astype(int)) <= 28) & (c == c[i]); m[i] = False
            if m.sum() >= 2: dist[i] = np.abs(hs[i] - np.median(hs[m], axis=0)).sum()
        rows.append(pd.DataFrame({'route': rt, 'date': g.index, 'cat': c, 'tot': g.tot.values,
                                  'r_loc': r_loc.values, 'r_share': r_share.values, 'shape_dist': dist}))
    F = pd.concat(rows, ignore_index=True)
    grp = [F.route, F.cat]
    F['z_loc'] = robust_z(F.r_loc, grp); F['z_share'] = robust_z(F.r_share, grp); F['z_shape'] = robust_z(F.shape_dist, grp)
    return F


def detect(F, contam=CONTAM, zmax=ZMAX, seed=0):
    F = F.copy(); Z = ['z_loc', 'z_share', 'z_shape']
    X = F[Z].fillna(0).clip(-15, 15)
    F['score'] = 0.0
    for wk in (True, False):
        m = (F.cat == 'wd') if wk else (F.cat != 'wd')
        iso = IsolationForest(n_estimators=300, contamination=contam, random_state=seed).fit(X[m])
        s = -iso.score_samples(X[m]); F.loc[m, 'score'] = (s - s.min()) / (s.max() - s.min())
        F.loc[m, 'if_flag'] = iso.predict(X[m]) == -1
    zabs = X.abs().max(1)
    F['flag'] = F.if_flag.astype(bool) | (zabs > zmax)
    lvl = np.where(X.z_loc.abs() >= X.z_share.abs(), X.z_loc, X.z_share)
    F['kind'] = np.where(X.z_shape > np.abs(lvl), 'shape', np.where(lvl < 0, 'drop', 'spike'))
    return F


def known_label(route, date):
    c = CALX.loc[date]; dow = date.dayofweek
    if date <= pd.Timestamp('2025-01-12') or c.is_new_year_period == 1: return 'holiday (New Year period)'
    if (c.is_holiday == 1 and dow < 5) or c.is_transferred_workday == 1 or c.is_preholiday_shortened == 1: return 'holiday / bridge / pre-holiday'
    if route == 7 and pd.Timestamp('2025-07-01') <= date <= pd.Timestamp('2025-08-31'): return 'repairs: route 7 Jul-Aug'
    if route == 50 and pd.Timestamp('2025-07-01') <= date <= pd.Timestamp('2025-07-31'): return 'repairs: route 50 Jul'
    if route in (7, 50) and date >= pd.Timestamp('2025-09-01') and dow >= 5: return f'repairs: route {route} weekends (Sep-Nov 14)'
    if c.is_holiday == 1 and dow >= 5: return 'holiday weekend'
    if c.is_school_holiday == 1: return 'school break'
    if date == pd.Timestamp('2025-10-31'): return 'manual exclusion (Oct 31)'
    return 'unknown'


def manual_set():
    """Route-days excluded by hand somewhere in the pipeline (level: SHORTBAD; anchor: BAD; repairs rules)."""
    rd = DAILY[['route', 'date']].copy()
    lab = [known_label(r, d) for r, d in zip(rd.route, rd.date)]
    rd['manual'] = lab
    return rd[rd.manual != 'unknown']


# ---------------------------------------------------------------- auto-clean forecast
def level_clean_rd(end, drop_rd, K=KDEF):
    dd = DAILY[DAILY.date <= end]
    dd = dd[~pd.MultiIndex.from_frame(dd[['route', 'date']]).isin(drop_rd)].sort_values('date')
    out = []
    for dt, k in K.items():
        g = dd[dd.dt == dt].groupby('route').tail(k); g = g[g.date > end - pd.Timedelta(weeks=6)]
        out.append(g.groupby('route').tot.median().rename('L').reset_index().assign(dt=dt))
    return pd.concat(out).set_index(['route', 'dt']).L


def anchor_rd(hist, drop_rd):
    A = hist[~pd.MultiIndex.from_frame(hist[['route', 'date']]).isin(drop_rd)]
    g = A.groupby(['route', 'dt', 'hour']).boardings.sum(); return g / g.groupby(level=[0, 1]).transform('sum')


def fc_custom(hist, t, L, SA, w=0.7):
    """Same as analyst fc3(variant='ratio_cap') with injected level L and anchor shape SA."""
    end = hist.date.max(); S = shape(hist, end, 4)
    x = t[['route', 'date', 'hour', 'dt']].join(L, on=['route', 'dt']).join(S.rename('S'), on=['route', 'dt', 'hour']).join(SA.rename('SA'), on=['route', 'dt', 'hour'])
    Sb = np.where(x.SA.notna(), (1 - w) * x.S + w * x.SA, x.S); Sb = np.clip(Sb, x.S / 1.5, x.S * 1.5)
    Sb = pd.Series(np.nan_to_num(Sb))
    Sb = Sb / Sb.groupby([x.route.values, x.date.values]).transform('sum').replace(0, np.nan) * x.S.fillna(0).groupby([x.route.values, x.date.values]).transform('sum').values
    return np.nan_to_num(x.L.values * Sb.values)


def regime_guard(det):
    """Un-flag the trailing run of flagged days per route x category: if the latest days are still anomalous the
    anomaly is the *current regime* (e.g. ongoing weekend repairs) and must stay in the level window."""
    det = det.sort_values('date').copy()
    for _, g in det.groupby(['route', 'cat']):
        run = []
        for i in g.index[::-1]:
            if det.at[i, 'flag']: run.append(i)
            else: break
        det.loc[run, 'flag'] = False
    return det


def rd_index(df): return pd.MultiIndex.from_frame(df[['route', 'date']])


def autoclean_folds():
    rows = []
    allrd = DAILY[['route', 'date']]
    for s, e in FOLDS:
        hist, fut = D[D.date < s], D[(D.date >= s) & (D.date <= e) & (D.route != 5)]
        end = hist.date.max()
        det = detect(features(end)); gdet = regime_guard(det)
        auto = rd_index(det[det.flag]); auto_g = rd_index(gdet[gdet.flag])
        auto_drop = rd_index(det[det.flag & (det.kind == 'drop')])
        man_lvl = rd_index(allrd[allrd.date.isin(SHORTBAD)]); man_anc = rd_index(allrd[allrd.date.isin(BAD)])
        y = fut.boardings.values
        cand = {
            'manual (v07/v08 base)': (man_lvl, man_anc),
            'auto only (all flags)': (auto, auto),
            'auto only (drops)': (auto_drop, auto_drop),
            'manual + auto (all flags)': (man_lvl.union(auto), man_anc.union(auto)),
            'manual + auto (drops)': (man_lvl.union(auto_drop), man_anc.union(auto_drop)),
            'auto only + regime guard': (auto_g, auto_g),
            'manual + auto + regime guard': (man_lvl.union(auto_g), man_anc.union(auto_g)),
            'manual level + auto-guard level, manual anchor': (man_lvl.union(auto_g), man_anc),
        }
        r = {'fold': s, 'fc3_check': wape_score(y, base_forecast(hist, fut))}
        for n, (lv, an) in cand.items():
            r[n] = wape_score(y, fc_custom(hist, fut, level_clean_rd(end, lv), anchor_rd(hist, an)))
        rows.append(r); print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    return pd.DataFrame(rows)


if __name__ == '__main__':
    F = detect(features())
    F['label'] = [known_label(r, d) for r, d in zip(F.route, F.date)]
    A = F[F.flag].sort_values('score', ascending=False)
    o = A[['route', 'date', 'score', 'kind', 'label', 'tot', 'z_loc', 'z_share', 'z_shape']].copy()
    o['date'] = o.date.dt.strftime('%Y-%m-%d')
    o.round(3).to_csv(os.path.join(OUT, 'anomalies.csv'), sep=';', index=False)
    print(f'flagged {len(A)} of {len(F)} route-days ({len(A) / len(F):.1%}); explained by a known cause: {(A.label != "unknown").mean():.1%}')
    print(A.groupby(['label', 'kind']).size().unstack(fill_value=0).to_string())
    # recall of manual exclusions by category
    M = F.assign(cat_m=F.label)
    rec = M[M.label != 'unknown'].groupby('label').agg(n=('flag', 'size'), flagged=('flag', 'sum'))
    rec['recall'] = rec.flagged / rec.n
    # repairs: weekend-only days that are really disrupted
    print('\nrecall of known causes:\n', rec.round(3).to_string())
    base_rate = F.flag.mean(); print(f'base flag rate {base_rate:.3f}')
    print('\ntop unknown anomalies:\n', A[A.label == 'unknown'].head(15)[['route', 'date', 'score', 'kind', 'z_loc', 'z_share', 'z_shape']].round(2).to_string())
    rec.to_csv(os.path.join(OUT, 'anomaly_recall.csv'), sep=';')
    res = autoclean_folds()
    res.to_csv(os.path.join(OUT, 'anomaly_autoclean_folds.csv'), sep=';', index=False)
    cols = [c for c in res.columns if c not in ('fold', 'fc3_check')]
    ref = 'manual (v07/v08 base)'
    print('\nmean WAPE-score:', res[cols].mean().round(5).to_dict())
    print('delta vs manual x1e3 per fold:\n', (res[cols].sub(res[ref], axis=0) * 1e3).round(2).assign(fold=res.fold).to_string())
    # Nov-Dec implication of "manual + auto + regime guard" (structural base only, before v08 rules)
    end = D.date.max(); det = regime_guard(detect(features(end))); ag = rd_index(det[det.flag])
    allrd = DAILY[['route', 'date']]; ml_ = rd_index(allrd[allrd.date.isin(SHORTBAD)]); ma_ = rd_index(allrd[allrd.date.isin(BAD)])
    t = make_target('2025-11-01', '2025-12-31')
    p0 = fc_custom(D, t, level_clean_rd(end, ml_), anchor_rd(D, ma_)); p1 = fc_custom(D, t, level_clean_rd(end, ml_.union(ag)), anchor_rd(D, ma_.union(ag)))
    print(f'Nov-Dec base: manual {p0.sum():,.0f}, manual+auto+guard {p1.sum():,.0f} ({p1.sum() / p0.sum() - 1:+.2%}), L1 moved {np.abs(p1 - p0).sum():,.0f}')
    print('route-days newly excluded in the last 6 weeks:', det[det.flag & (det.date > end - pd.Timedelta(weeks=6))][['route', 'date', 'kind']].assign(date=lambda x: x.date.dt.strftime('%m-%d')).values.tolist())
