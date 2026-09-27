"""Refinements of anchor blend (w=0.7 all day types, clean level): protect edge hours / schedule changes."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from r2_clean_anchor import anchor
from r2_clean_level import level_clean
from common import full_grid
def fc3(hist, t, w=0.7, variant='plain', skip=()):
    end = hist.date.max(); L = level_clean(end); S = shape(hist,end,4); SA = anchor(hist)
    x = t[['route','date','hour','dt']].join(L, on=['route','dt']).join(S.rename('S'), on=['route','dt','hour']).join(SA.rename('SA'), on=['route','dt','hour'])
    ww = np.full(len(x), w)
    if variant in ('nz','nz_hours'): ww[(x.S.fillna(0).values==0)|(x.SA.fillna(0).values==0)] = 0
    if variant in ('hours','nz_hours'): ww[(x.hour<6)|(x.hour>22)] = 0
    if variant == 'ratio_cap':  # anchor may move a cell at most x1.5 / /1.5
        pass
    for r,dts in skip: ww[(x.route==r)&x.dt.isin(dts)] = 0
    Sb = np.where(x.SA.notna(), (1-ww)*x.S + ww*x.SA, x.S)
    if variant == 'ratio_cap': Sb = np.clip(Sb, x.S/1.5, x.S*1.5)
    Sb = pd.Series(np.nan_to_num(Sb)); Sb = Sb / Sb.groupby([x.route.values, x.date.values]).transform('sum').replace(0,np.nan) * x.S.fillna(0).groupby([x.route.values, x.date.values]).transform('sum').values
    return np.nan_to_num(x.L.values*Sb.values)
if __name__=='__main__':
    B = score(); rows=[]
    for n,kw in {'plain':{}, 'nonzero only':dict(variant='nz'), 'hours 6-22':dict(variant='hours'), 'nz + hours 6-22':dict(variant='nz_hours'),
                 'cap x1.5':dict(variant='ratio_cap'), 'plain, skip r50/r7 weekends':dict(skip=[(50,(5,6)),(7,(5,6))])}.items():
        r={'idea':n}
        for s,e in FOLDS:
            hist, fut = D[D.date<s], D[(D.date>=s)&(D.date<=e)]
            r[s[5:]]=(wape_score(fut.boardings.values, fc3(hist,fut,**kw))-B[s])*1e3
        rows.append(r)
    res=pd.DataFrame(rows); fcs=[s[5:] for s,_ in FOLDS]
    res['mean']=res[fcs].mean(1); res['mean_ex0901']=res[[c for c in fcs if c!='09-01']].mean(1); res['wins']=(res[fcs]>0).sum(1)
    print(res.round(2).to_string()); res.to_csv('experiments/analyst/r2_anchor_refine.csv',index=False)
