"""Control for idea 1b: does ANY long clean-period shape help equally (noise reduction), or specifically winter?"""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
calx = cal.set_index('date')
BAD = set(calx.index[(calx.is_school_holiday==1)|((calx.is_holiday==1)&(calx.dow<5))])
def SAof(a,b):
    A = D[(D.date>=a)&(D.date<=b)&~D.date.isin(BAD)]
    g = A.groupby(['route','dt','hour']).boardings.sum(); return g/g.groupby(level=[0,1]).transform('sum')
def fc_blend(hist, t, w, SA):
    end = hist.date.max(); L = level(DAILY[DAILY.date<=end], end); S = shape(hist, end)
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour']).join(SA.rename('SA'), on=['route','dt','hour'])
    Sb = np.where(x.SA.notna(), (1-w)*x.S + w*x.SA, x.S); return np.nan_to_num(x.L.values*Sb)
B = score()
analogs = {'winter Jan13-Feb28':('2025-01-13','2025-02-28'),'Feb-Mar':('2025-02-01','2025-03-23'),'spring Apr1-May20':('2025-04-01','2025-05-20'),'Mar-May20':('2025-03-01','2025-05-20')}
rows=[]
for n,(a,b) in analogs.items():
    SA=SAof(a,b)
    for s,e in FOLDS:
        if pd.Timestamp(b) >= pd.Timestamp(s): continue
        hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
        rows.append({'analog':n,'fold':s,'d':(wape_score(fut.boardings.values, fc_blend(hist,fut,0.5,SA))-B[s])*1e3})
print(pd.DataFrame(rows).pivot(index='analog',columns='fold',values='d').round(2).to_string())
# per-route: which routes' shapes differ between Oct and winter
Sw=SAof('2025-01-13','2025-02-28'); So=SAof('2025-10-01','2025-10-24')
x=pd.DataFrame({'w':Sw,'o':So}).dropna(); x['ad']=(x.w-x.o).abs()
print('L1 dist winter vs Oct (share mass moved/2) by route,dt'); print((x.groupby(level=[0,1]).ad.sum()/2*100).unstack().round(1))
