import sys; sys.path.insert(0,'src')
from common import *
from model_ls import forecast
d = load_labels(); d=d[d.route!=5]
folds=[('2025-10-01','2025-10-31'),('2025-09-15','2025-10-31'),('2025-02-01','2025-03-31')]
ms=[0.97,1.0,1.02,1.03,1.04,1.05,1.06,1.08]
for s,e in folds:
    hist,fut=d[d.date<s],d[(d.date>=s)&(d.date<=e)]
    p=forecast(hist,fut,2,4,'wk4','median'); y=fut.boardings.values
    print(s,e,'bias sum y/sum p=%.3f'%(y.sum()/p.sum()))
    for k in [1.0,1.03,1.066]:
        print('  truth x%.3f:'%k,' '.join('m%.2f=%.4f'%(m,wape_score(y*k,p*m)) for m in ms))
