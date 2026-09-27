import pandas as pd, numpy as np, sys
sys.path.insert(0,'src')
from common import load_labels, wape_score
from model_ls import forecast
d=load_labels()
cs=np.round(np.arange(0.86,1.141,0.02),2)
for s,e in [('2025-02-01','2025-03-31'),('2025-03-01','2025-04-30'),('2025-04-01','2025-05-31'),('2025-09-15','2025-10-31'),('2025-10-01','2025-10-31'),('2025-09-01','2025-10-31')]:
    hist,fut=d[d.date<s],d[(d.date>=s)&(d.date<=e)]
    p=forecast(hist,fut,2,4,'wk4','median','sum'); y=fut.boardings.values
    sc={c:wape_score(y,p*c) for c in cs}; best=max(sc,key=sc.get)
    # "oracle daily level": rescale each route-day to true total
    f=fut[['route','date']].copy(); f['y']=y; f['p']=p
    g=f.groupby(['route','date']); ratio=(g.y.transform('sum')/g.p.transform('sum').replace(0,np.nan)).fillna(1)
    orc=wape_score(y,p*ratio)
    print(f"{s}..{e}: bias Σp/Σy={p.sum()/y.sum():.3f} score@1={sc[1.0]:.4f} best c={best} score={sc[best]:.4f} oracleDaily={orc:.4f} | "+' '.join(f'{c}:{sc[c]:.3f}' for c in cs[::2]))
