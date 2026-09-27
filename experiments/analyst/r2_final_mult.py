"""Constant multiplier on top of the recommended config (clean level + anchor w0.7 cap1.5)."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from r2_anchor_refine import fc3
B = score(); rows=[]; P={}
for s,e in FOLDS:
    hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]; P[s]=(fut.boardings.values, fc3(hist,fut,0.7,'ratio_cap'))
for m in [0.99,1.0,1.01,1.02,1.03]:
    r={'mult':m, **{s[5:]:(wape_score(y,p*m)-B[s])*1e3 for s,(y,p) in P.items()}}; rows.append(r)
res=pd.DataFrame(rows); fcs=[s[5:] for s,_ in FOLDS]; res['mean']=res[fcs].mean(1); res['mean_ex0901']=res[[c for c in fcs if c!='09-01']].mean(1); res['wins']=(res[fcs]>0).sum(1)
print(res.round(2).to_string()); print('abs scores m=1:', {s[5:]:round(wape_score(y,p),4) for s,(y,p) in P.items()}, 'base', B.round(4).to_dict())
