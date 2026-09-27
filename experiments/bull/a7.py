import sys; sys.path.insert(0,'src')
from common import *
from model_ls import forecast
d = load_labels(); d=d[d.route!=5]
ms=[1.0,1.02,1.03,1.04,1.05,1.06]
res={}
for s,e in [('2025-10-01','2025-10-31'),('2025-09-15','2025-10-31'),('2025-02-01','2025-03-31')]:
    hist,fut=d[d.date<s],d[(d.date>=s)&(d.date<=e)]
    p=forecast(hist,fut,2,4,'wk4','median'); y=fut.boardings.values; b=y.sum()/p.sum()
    for B in [0.98,1.0,1.02,1.04,1.066,1.09]:
        yy=y*B/b; base=wape_score(yy,p)
        res.setdefault(B,[]).append([wape_score(yy,p*m)-base for m in ms])
print('rows: true bias Σy/Σŷ; cols: multiplier; mean Δscore over 3 folds')
print(pd.DataFrame({B:np.mean(v,0) for B,v in res.items()},index=ms).T.round(4))
