"""Idea 1b: blend the recent 4-week shape with a 'winter analog' shape (Jan 13 - Feb 28, no holidays).
Validated on autumn folds (Oct, Sep15-Oct, Sep-Oct) where the target is darker/colder than the shape window."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from common import full_grid
calx = cal.set_index('date')
BAD = set(calx.index[(calx.is_school_holiday==1)|((calx.is_holiday==1)&(calx.dow<5))])
A = D[(D.date>='2025-01-13')&(D.date<='2025-02-28')&~D.date.isin(BAD)]
g = A.groupby(['route','dt','hour']).boardings.sum(); SA = g/g.groupby(level=[0,1]).transform('sum')

def fc_blend(hist, t, w, dts=(0,4,5,6)):
    end = hist.date.max()
    L = level(DAILY[DAILY.date<=end], end); S = shape(hist, end)
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour']).join(SA.rename('SA'), on=['route','dt','hour'])
    ww = np.where(x.dt.isin(dts), w, 0.0)
    Sb = np.where(x.SA.notna(), (1-ww)*x.S + ww*x.SA, x.S)
    return np.nan_to_num(x.L.values*Sb)

B = score(); rows=[]
for w in [0.25,0.5,0.75]:
    for dts in [(0,4,5,6),(0,4),(5,6)]:
        r={'w':w,'dts':str(dts)}
        for s,e in FOLDS[:2]+FOLDS[5:]:
            hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
            r[s[5:]] = (wape_score(fut.boardings.values, fc_blend(hist,fut,w,dts)) - B[s])*1e3
        rows.append(r)
res=pd.DataFrame(rows); res['mean']=res[['10-01','09-15','09-01']].mean(1); print(res.round(2).to_string())
t = full_grid('2025-11-01','2025-12-31'); t['dt']=dtmap(daytype(t.date),'wk4')
p0=forecast(D,t); p1=fc_blend(D,t,0.5)
print('Nov-Dec w=0.5 mass moved', round(np.abs(p1-p0).sum()/p0.sum()*100,2),'%')
tt=t.assign(p0=p0,p1=p1); g=tt.groupby('hour')[['p0','p1']].sum(); print(((g.p1/g.p0-1)*100).round(1).loc[5:23].to_dict())
