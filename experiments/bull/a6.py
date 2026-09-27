import sys; sys.path.insert(0,'src')
from common import *
d = load_labels()
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])
def dt(df):
    return np.select([(df.is_dayoff==1)&(df.dow!=5), df.dow==5, df.dow==4],[3,2,1],0)
day=d.groupby(['route','date']).boardings.sum().reset_index().merge(cal,on='date'); day['dt']=dt(day)
oc=day[(day.date>='2025-10-01')&(day.date<='2025-10-24')].groupby(['route','dt']).boardings.mean().unstack()
v=pd.read_csv('submissions/v06_best_r50_r7.csv',sep=';',parse_dates=['date']).merge(cal,on='date'); v['dt']=dt(v)
vl=v[(v.date>='2025-11-10')&(v.date<='2025-11-23')].groupby(['route','date','dt']).prediction.sum().groupby(['route','dt']).mean().unstack()
r=(oc/vl).round(3); r.columns=['MonThu','Fri','Sat','Sun']
pd.set_option('display.width',200); print(r)
# volume-weighted
for c,i in zip(r.columns,range(4)):
    m=[x for x in oc.index if x not in (5,50,7)]
    print(c,'core ratio %.3f'%(oc.loc[m,i].sum()/vl.loc[m,i].sum()))
# Nov volume by dt in v06
v['m']=v.date.dt.month
print(v.groupby(['m','dt']).prediction.sum().unstack())
