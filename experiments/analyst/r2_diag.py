import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
rows=[]
for s,e in FOLDS:
    hist, fut = D[D.date < s], D[(D.date >= s) & (D.date <= e)].copy()
    fut['p']=forecast(hist,fut)
    g=fut.groupby('dt')[['boardings','p']].sum()
    r={'fold':s,'bias':fut.p.sum()/fut.boardings.sum()}
    for dt in [0,4,5,6]: r[f'b{dt}']=g.loc[dt,'p']/g.loc[dt,'boardings']
    # oracle level decomposition: daily-level error vs shape error
    dd=fut.groupby(['route','date']).agg(y=('boardings','sum'),p=('p','sum'))
    r['daylevel_wape']=1-np.abs(dd.y-dd.p).sum()/dd.y.sum()
    # best const mult
    ms=np.arange(0.9,1.15,0.01); sc=[wape_score(fut.boardings.values,fut.p.values*m) for m in ms]
    r['best_mult']=ms[int(np.argmax(sc))]; r['gain']=max(sc)-wape_score(fut.boardings.values,fut.p.values)
    rows.append(r)
print(pd.DataFrame(rows).round(4).to_string())
