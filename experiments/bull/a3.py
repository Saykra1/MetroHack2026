import sys; sys.path.insert(0,'src')
from common import *
d = load_labels()
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])
day = d.groupby(['route','date']).boardings.sum().reset_index().merge(cal,on='date')
core=[1,11,12,17,25,26,28]  # untouched routes
net = day[day.route.isin(core)].groupby(['date','dow','is_dayoff','is_school_holiday']).boardings.sum().reset_index()
pd.set_option('display.width',250)
print(net[(net.date>='2025-10-01')].to_string(index=False))
print(net[(net.date>='2025-03-10')&(net.date<='2025-04-13')].to_string(index=False))
# v06 implied daily totals, core routes
v=pd.read_csv('submissions/v06_best_r50_r7.csv',sep=';',parse_dates=['date'])
vd=v[v.route.isin(core)].groupby('date').prediction.sum().reset_index().merge(cal,on='date')
print(vd[['date','dow','prediction']].head(21).to_string(index=False))
