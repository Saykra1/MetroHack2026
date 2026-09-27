import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
B = score()
exps = {
 'L mean WL2': dict(lagg='mean'), 'L trim WL3': dict(WL=3,lagg='trim'), 'L trim WL4': dict(WL=4,lagg='trim'),
 'L median WL3': dict(WL=3), 'L ew7 WL3': dict(WL=3,lagg='ew7'), 'L ew7 WL4': dict(WL=4,lagg='ew7'), 'L ew10 WL4': dict(WL=4,lagg='ew10'),
 'L last(1wk)': dict(WL=1),
 'L WL_we=3': dict(WL_we=3), 'L WL_we=4': dict(WL_we=4), 'L WL_we=6': dict(WL_we=6),
 'L WL_we=4 mean': dict(WL_we=4, lagg='mean'),
 'L ratio long4': dict(pooled_long=4), 'L ratio long6': dict(pooled_long=6), 'L ratio long8': dict(pooled_long=8),
 'L outlier0.8': dict(outlier=0.8), 'L outlier0.8 WL3': dict(outlier=0.8, WL=3),
 'mult 1.01': dict(mult=1.01), 'mult 1.02': dict(mult=1.02), 'mult 1.03': dict(mult=1.03),
 'S WS3': dict(WS=3), 'S WS6': dict(WS=6), 'S WS8': dict(WS=8),
 'S med shares': dict(est='median'), 'S mean shares': dict(est='mean'),
 'S shrink long12 k5': dict(shrink_k=5), 'S shrink long12 k20': dict(shrink_k=20), 'S shrink long12 k50': dict(shrink_k=50),
 'S shrink long8 k20': dict(shrink_k=20, prior_WS=8),
 'S shrink pooled k5': dict(shrink_k=5, prior='pooled'), 'S shrink pooled k20': dict(shrink_k=20, prior='pooled'),
}
rows=[]
for n,kw in exps.items():
    s = score(**kw) - B
    r = {'idea':n, **{k[5:]:v*1e3 for k,v in s.items()}}
    r['mean']=s.mean()*1e3; r['mean_ex0901']=s.drop('2025-09-01').mean()*1e3; r['wins']=(s>0).sum()
    rows.append(r); print(n, round(r['mean'],2), flush=True)
res=pd.DataFrame(rows)
print('delta x1e-3 vs base', B.round(4).to_dict(), round(B.mean(),5))
print(res.round(2).to_string())
res.to_csv('experiments/analyst/r2_level_shape.csv', index=False)
