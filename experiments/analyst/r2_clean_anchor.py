"""Idea 1c/3: shrink the 4-week shape toward a 'clean anchor' = all history before the fold origin, excluding school
breaks (incl. summer), weekday holidays, Jan 1-12; optionally also the last 4 weeks. Blend weight w."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from common import full_grid
calx = cal.set_index('date')
BAD = set(calx.index[(calx.is_school_holiday==1)|((calx.is_holiday==1)&(calx.dow<5))]) | set(pd.date_range('2025-01-01','2025-01-12'))
def anchor(hist, a=None):
    A = hist[~hist.date.isin(BAD)]
    if a: A = A[A.date>=a]
    g = A.groupby(['route','dt','hour']).boardings.sum(); return g/g.groupby(level=[0,1]).transform('sum')
def fc_anchor(hist, t, w, dts=(0,4,5,6), a=None, WS=4):
    end = hist.date.max(); L = level(DAILY[DAILY.date<=end], end); S = shape(hist, end, WS); SA = anchor(hist, a)
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour']).join(SA.rename('SA'), on=['route','dt','hour'])
    ww = np.where(x.dt.isin(dts), w, 0.0)
    Sb = np.where(x.SA.notna(), (1-ww)*x.S + ww*x.SA, x.S); return np.nan_to_num(x.L.values*Sb)
if __name__=='__main__':
    B = score(); rows=[]
    for w in [0.3,0.5,0.7]:
        for dts in [(0,4,5,6),(0,4),(5,6)]:
            r={'w':w,'dts':str(dts)}
            for s,e in FOLDS:
                hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
                r[s[5:]]=(wape_score(fut.boardings.values, fc_anchor(hist,fut,w,dts))-B[s])*1e3
            rows.append(r); print(r, flush=True)
    res=pd.DataFrame(rows); fc=[s[5:] for s,_ in FOLDS]
    res['mean']=res[fc].mean(1); res['mean_ex0901']=res[[c for c in fc if c!='09-01']].mean(1); res['wins']=(res[fc]>0).sum(1)
    print(res.round(2).to_string()); res.to_csv('experiments/analyst/r2_clean_anchor.csv',index=False)
    t = full_grid('2025-11-01','2025-12-31'); t['dt']=dtmap(daytype(t.date),'wk4')
    p0=forecast(D,t); p1=fc_anchor(D,t,0.5)
    print('Nov-Dec w=0.5 mass moved', round(np.abs(p1-p0).sum()/p0.sum()*100,2),'%, total change', round(p1.sum()-p0.sum()))
