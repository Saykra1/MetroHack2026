"""Component 1 — hybrid ensemble: structural base x LightGBM ratio correction.

GBM is trained on many forecast origins (direct multi-horizon, no short lags) to predict r = y / base with an L1
objective weighted by base  ->  sum base*|y/base - r| = sum |y - base*r|  (exactly the WAPE numerator).
Final = base * (1 - w + w * r_hat), w tuned on rolling-origin folds in [0, 0.5].
Usage:  python src/ml/hybrid.py            (folds + Nov-Dec file experiments/ml/hybrid_nov_dec.csv)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import *
import lightgbm as lgb

F_CORE = ['route', 'hour', 'dt', 'dow', 'h_days', 'is_dayoff', 'is_holiday', 'is_preholiday_shortened', 'is_school_holiday',
          'is_transferred_workday', 'logbase', 'logL', 'lvl_ratio', 'shape_dev', 'S4', 'SA', 'dom']
F_WEATHER = F_CORE + ['temperature_2m', 'precipitation', 'snowfall', 'wind_speed_10m', 't_day', 'pr_day', 'sn_day', 'snowdepth']
F_TRAFFIC = F_WEATHER + ['traffic_score', 'traffic_reported']
FEATSETS = {'core': F_CORE, 'weather': F_WEATHER, 'weather+traffic': F_TRAFFIC}
PARAMS = dict(objective='l1', n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=1000, reg_lambda=10.0,
              subsample=0.7, subsample_freq=1, colsample_bytree=0.7, max_bin=63, verbose=-1)
W_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
MIN_TRAIN = 30000          # folds with fewer training rows are reported as n/a (GBM cannot be trained honestly)


def fit(tr, F, seed=0, params=PARAMS):
    tr = tr[tr.base > 1]
    m = lgb.LGBMRegressor(random_state=seed, **params)
    X = tr[F].copy()
    if 'route' in F: X['route'] = X.route.astype('category')
    m.fit(X, (tr.y / tr.base).clip(0, 3), sample_weight=tr.base)
    return m


def predict_ratio(m, te, F):
    X = te[F].copy()
    if 'route' in F: X['route'] = pd.Categorical(X.route, categories=m.booster_.pandas_categorical[0])
    r = m.predict(X)
    return np.where(te.base.values > 1, np.clip(r, 0.5, 1.5), 1.0)   # safety cap: ML may move a cell at most ±50 %


def blend(base, r, w): return base * (1 - w + w * r)


def run_folds(P, featsets=FEATSETS):
    rows = []
    for s, e in FOLDS:
        tr, te = fold_split(P, s, e)
        y, b = te.y.values, te.base.values
        if len(tr) < MIN_TRAIN:
            rows.append({'fold': s, 'feats': 'n/a', 'n_train': len(tr), 'base': wape_score(y, b)}); continue
        for name, F in featsets.items():
            m = fit(tr, F); r = predict_ratio(m, te, F)
            row = {'fold': s, 'feats': name, 'n_train': len(tr), 'base': wape_score(y, b), 'gbm': wape_score(y, b * r)}
            for w in W_GRID: row[f'w{w:.1f}'] = wape_score(y, blend(b, r, w))
            rows.append(row); print(row['fold'], name, round(row['base'], 5), round(row['gbm'], 5), flush=True)
    return pd.DataFrame(rows)


if __name__ == '__main__':
    P = build_panel()
    res = run_folds(P)
    res.to_csv(os.path.join(OUT, 'hybrid_folds.csv'), sep=';', index=False)
    ok = res[res.feats != 'n/a']
    wcols = [f'w{w:.1f}' for w in W_GRID]
    summ = ok.groupby('feats')[['base', 'gbm'] + wcols].mean()
    delta = ok.assign(**{c: ok[c] - ok.base for c in ['gbm'] + wcols}).groupby('feats')[['gbm'] + wcols]
    print('\nmean WAPE-score over trainable folds\n', summ.round(5).to_string())
    print('\nmean delta vs base (x1e3)\n', (delta.mean() * 1e3).round(2).to_string())
    print('\nwins vs base (folds)\n', ok.assign(**{c: ok[c] > ok.base + 1e-9 for c in wcols[1:]}).groupby('feats')[wcols[1:]].sum().to_string())
    # choose feature set and w by mean delta; w=0 unless the gain is positive on a majority of folds
    d = delta.mean(); best_fs = d[wcols[1:]].max(1).idxmax(); best_w = float(d.loc[best_fs, wcols].idxmax()[1:])
    wins = (ok[ok.feats == best_fs][f'w{best_w:.1f}'] > ok[ok.feats == best_fs].base).sum()
    nf = (ok.feats == best_fs).sum()
    if best_w > 0 and wins <= nf / 2: best_w = 0.0
    print(f'\nchosen: feats={best_fs}, w={best_w} (wins {wins}/{nf})')

    # ---- Nov-Dec: train on all origins (targets <= 31 Oct), apply to v08
    F = FEATSETS[best_fs]
    m = fit(P, F)
    fut = add_features(panel_for_origin('2025-11-01', '2025-12-31', hist=D, with_y=False))
    fut['ml_ratio'] = predict_ratio(m, fut, F)
    imp = pd.Series(m.booster_.feature_importance('gain'), index=F).sort_values(ascending=False)
    print('top features (gain share):', (imp / imp.sum()).head(8).round(3).to_dict())
    v08 = pd.read_csv(os.path.join(ROOT, 'submissions', 'v08_nov15_weekends.csv'), sep=';', parse_dates=['date'])
    out = v08.rename(columns={'prediction': 'base'}).merge(fut[['route', 'date', 'hour', 'ml_ratio']], on=['route', 'date', 'hour'], how='left')
    out['ml_ratio'] = out.ml_ratio.fillna(1.0)
    # rule cells without a history analogue keep v08: route 5, Nov-1 00-01h (exact), NY night zeros, Dec 29-31 (special
    # multipliers), r7/r50 weekends from 15.11 (rebuilt from the pre-repair profile, not from the structural base)
    keep = (out.route == 5) | ((out.date == '2025-11-01') & (out.hour <= 1)) | (out.date >= '2025-12-29') | \
           (out.route.isin([7, 50]) & (out.date >= '2025-11-15') & (out.date.dt.dayofweek >= 5))
    out.loc[keep, 'ml_ratio'] = 1.0
    out['prediction'] = blend(out.base.values, out.ml_ratio.values, best_w).round().astype(int)
    out['date'] = out.date.dt.strftime('%Y-%m-%d')
    out[['route', 'date', 'hour', 'base', 'ml_ratio']].assign(ml_ratio=out.ml_ratio.round(4), prediction=out.prediction) \
        .to_csv(os.path.join(OUT, 'hybrid_nov_dec.csv'), sep=';', index=False)
    print(f'Nov-Dec: v08 total {out.base.sum():,}, hybrid total {out.prediction.sum():,}, '
          f'L1 moved {np.abs(out.prediction - out.base).sum():,}; ratio (w=1) weighted mean '
          f'{np.average(out.ml_ratio, weights=out.base + 1e-9):.4f}')
    # also write the w=1 GBM-implied totals by month for the report
    out['m'] = out.date.str[:7]
    print(out.assign(g=out.base * out.ml_ratio).groupby('m')[['base', 'g']].sum().round().to_string())
