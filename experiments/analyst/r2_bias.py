"""Rolling-origin bias of base level: forecast each week (Mon) from history before it; horizons 1w and 5-8w."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
rows=[]
for s in pd.date_range('2025-02-03','2025-10-27',freq='W-MON'):
    hist=D[D.date<s]
    for h in [0,4]:
        a=s+pd.Timedelta(weeks=h); fut=D[(D.date>=a)&(D.date<a+pd.Timedelta(days=7))]
        if fut.date.max()<a+pd.Timedelta(days=6): continue
        p=forecast(hist,fut)
        rows.append({'origin':s,'h':h,'ratio':p.sum()/fut.boardings.sum()})
r=pd.DataFrame(rows).pivot(index='origin',columns='h',values='ratio')
print(r.round(3).to_string())
print('median ratio', r.median().round(4).to_dict(), 'mean', r.mean().round(4).to_dict())
