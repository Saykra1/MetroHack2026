"""Component 1 ablation: simpler / slower / recent-only GBM variants (all lose to the structural base, see REPORT.md)."""
import sys; import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hybrid import *
P = build_panel()
P['cold'] = (P.t_day < -10).astype(int)
FS = {'minimal': ['route','hour','dt','h_days','is_school_holiday','is_holiday','is_preholiday_shortened','pr_day','sn_day','cold'],
      'shape_only': ['route','hour','dt','S4','SA','shape_dev','h_days'],
      'weather_only': ['hour','dt','pr_day','sn_day','t_day','precipitation','snowfall','cold']}
slow = dict(PARAMS, n_estimators=150, learning_rate=0.02, num_leaves=7, min_child_samples=3000, reg_lambda=50.0)
for pname, prm in [('slow', slow), ('std', PARAMS)]:
  for recent in [None, 12]:
    for fs, F in FS.items():
        ds=[]
        for s,e in FOLDS:
            tr,te = fold_split(P,s,e)
            if recent: tr = tr[tr.origin >= pd.Timestamp(s) - pd.Timedelta(weeks=recent)]
            if len(tr) < MIN_TRAIN: continue
            m = fit(tr, F, params=prm); r = predict_ratio(m, te, F)
            ds.append([wape_score(te.y, te.base*r)-wape_score(te.y, te.base), wape_score(te.y, blend(te.base.values,r,0.3))-wape_score(te.y, te.base)])
        ds=np.array(ds)*1e3
        print(pname, recent, fs, 'gbm', ds[:,0].round(1), 'w0.3', ds[:,1].round(2), 'mean', ds.mean(0).round(2), flush=True)
