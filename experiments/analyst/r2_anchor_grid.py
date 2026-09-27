"""Grid over anchor weights (weekday w_wk, weekend w_we) with clean level; final-candidate check."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from r2_clean_anchor import anchor
from r2_clean_level import level_clean
LC = {}; SC = {}; AC = {}
def fc2(hist, t, w_wk, w_we, clean=True, mult=1.0):
    end = hist.date.max()
    if end not in LC: LC[end]=(level_clean(end), level(DAILY[DAILY.date<=end], end)); SC[end]=shape(hist,end,4); AC[end]=anchor(hist)
    L = LC[end][0] if clean else LC[end][1]
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(SC[end].rename('S'), on=['route','dt','hour']).join(AC[end].rename('SA'), on=['route','dt','hour'])
    ww = np.where(x.dt.isin([0,4]), w_wk, w_we)
    Sb = np.where(x.SA.notna(), (1-ww)*x.S + ww*x.SA, x.S); return np.nan_to_num(x.L.values*Sb)*mult
B = score(); rows=[]
for wk in [0.0,0.5,0.7,0.85,1.0]:
    for we in [0.0,0.5,0.7,0.85,1.0]:
        r={'w_wk':wk,'w_we':we}
        for s,e in FOLDS:
            hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
            r[s[5:]]=(wape_score(fut.boardings.values, fc2(hist,fut,wk,we))-B[s])*1e3
        rows.append(r)
res=pd.DataFrame(rows); fcs=[s[5:] for s,_ in FOLDS]
res['mean']=res[fcs].mean(1); res['mean_ex0901']=res[[c for c in fcs if c!='09-01']].mean(1); res['wins']=(res[fcs]>0).sum(1)
print(res.sort_values('mean',ascending=False).round(2).to_string()); res.to_csv('experiments/analyst/r2_anchor_grid.csv',index=False)
