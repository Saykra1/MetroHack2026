"""Idea 2b: level from the last k CLEAN days per (route, daytype), skipping short school breaks (<14 d) and weekday
holidays (+ Jan 1-12). k = 8 Mon-Thu, 2 Fri, 2 Sat, 2 Sun reproduces the 2-week window when nothing is excluded.
Combined with the clean-anchor shape (r2_clean_anchor)."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from r2_clean_anchor import anchor
from common import full_grid
calx = cal.set_index('date')
sh = calx[calx.is_school_holiday==1].index.to_series(); blk=(sh.diff().dt.days!=1).cumsum()
short = set(sh[blk.map(blk.value_counts())<14])
SHORTBAD = short | set(calx.index[(calx.is_holiday==1)&(calx.dow<5)]) | set(pd.date_range('2025-01-01','2025-01-12'))
print('excluded short-break days:', sorted(d.strftime('%m-%d') for d in short))
KDEF = {0:8,4:2,5:2,6:2}
def level_clean(end, K=KDEF, excl=SHORTBAD, agg='median'):
    dd = DAILY[(DAILY.date<=end)&~DAILY.date.isin(excl)].sort_values('date')
    out=[]
    for dt,k in K.items():
        g = dd[dd.dt==dt].groupby('route').tail(k)
        g = g[g.date > end - pd.Timedelta(weeks=6)]   # do not reach back more than 6 weeks
        out.append(g.groupby('route').tot.agg(agg).rename('L').reset_index().assign(dt=dt))
    return pd.concat(out).set_index(['route','dt']).L
def fc(hist, t, clean_level=True, w=0.0, K=KDEF, dts=(0,4,5,6), shape_excl=False, mult=1.0):
    end = hist.date.max()
    L = level_clean(end, K) if clean_level else level(DAILY[DAILY.date<=end], end)
    h2 = hist[~hist.date.isin(SHORTBAD)] if shape_excl else hist
    S = shape(h2, end, 4) if not shape_excl else shape(h2[h2.date> end-pd.Timedelta(weeks=5)], end, 5)
    SA = anchor(hist)
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour']).join(SA.rename('SA'), on=['route','dt','hour'])
    ww = np.where(x.dt.isin(dts), w, 0.0)
    Sb = np.where(x.SA.notna(), (1-ww)*x.S + ww*x.SA, x.S); return np.nan_to_num(x.L.values*Sb)*mult
if __name__=='__main__':
    B = score(); rows=[]
    cfgs = {'clean level': dict(), 'clean level K Sat/Sun=3': dict(K={0:8,4:2,5:3,6:3}),
            'clean level K Fri=3': dict(K={0:8,4:3,5:2,6:2}),
            'anchor w0.5': dict(clean_level=False, w=0.5), 'anchor w0.7': dict(clean_level=False, w=0.7),
            'clean level + anchor w0.5': dict(w=0.5), 'clean level + anchor w0.7': dict(w=0.7),
            'anchor w0.5 + clean recent shape': dict(clean_level=False, w=0.5, shape_excl=True),
            'clean level + anchor w0.5 + x1.01': dict(w=0.5, mult=1.01), 'clean level + anchor w0.5 + x1.02': dict(w=0.5, mult=1.02)}
    for n,kw in cfgs.items():
        r={'idea':n}
        for s,e in FOLDS:
            hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
            r[s[5:]]=(wape_score(fut.boardings.values, fc(hist,fut,**kw))-B[s])*1e3
        rows.append(r); print(n, flush=True)
    res=pd.DataFrame(rows); fcs=[s[5:] for s,_ in FOLDS]
    res['mean']=res[fcs].mean(1); res['mean_ex0901']=res[[c for c in fcs if c!='09-01']].mean(1); res['wins']=(res[fcs]>0).sum(1)
    print(res.round(2).to_string()); res.to_csv('experiments/analyst/r2_clean_level.csv',index=False)
    # production implication
    t = full_grid('2025-11-01','2025-12-31'); t['dt']=dtmap(daytype(t.date),'wk4')
    L0 = level(DAILY, D.date.max()); L1 = level_clean(D.date.max())
    cmp = pd.DataFrame({'L0':L0,'L1':L1}); cmp['ratio']=cmp.L1/cmp.L0
    print(cmp.ratio.unstack().round(3)); print('network by dt', cmp.groupby(level=1)[['L0','L1']].sum().assign(r=lambda x:x.L1/x.L0).round(3))
    p0=forecast(D,t); p1=fc(D,t,w=0.5)
    print('Nov-Dec total base', round(p0.sum()), 'clean+anchor', round(p1.sum()), 'diff', round(p1.sum()-p0.sum()))
