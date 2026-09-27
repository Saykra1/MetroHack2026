"""Hourly-share drift by month (Mon-Thu working days and Sat/Sun), network and per route; daylight link."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
x = D[(D.route!=5)].copy(); x['m']=x.date.dt.month
cal2 = cal.set_index('date')
x = x[~x.date.isin(cal2.index[(cal2.is_school_holiday==1)|(cal2.is_holiday==1)&(cal2.dow<5)])]  # drop school breaks/holidays
for dt,name in [(0,'Mon-Thu'),(5,'Sat'),(6,'Sun')]:
    g = x[x.dt==dt].groupby(['m','hour']).boardings.sum().unstack()
    sh = g.div(g.sum(1),axis=0)*100
    print(name, 'share % by hour (rows=month)'); print(sh.loc[:, 5:23].round(1).to_string())
# peak timing: centroid of evening (14-23) and morning (5-11)
g = x[x.dt==0].groupby(['m','hour']).boardings.sum().unstack()
ev = g.loc[:,14:23]; mo=g.loc[:,5:11]
print('evening centroid', (ev*ev.columns).sum(1)/ev.sum(1)); print('morning centroid',(mo*mo.columns).sum(1)/mo.sum(1))
print('share 17-19', (g.loc[:,17:19].sum(1)/g.sum(1)).round(4).to_dict())
print('share 20-23', (g.loc[:,20:23].sum(1)/g.sum(1)).round(4).to_dict())
