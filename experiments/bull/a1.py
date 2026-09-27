import sys; sys.path.insert(0,'src')
from common import *
d = load_labels()
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])
d = d.merge(cal[['date','dow','is_dayoff','is_school_holiday']], on='date')
day = d.groupby(['route','date','dow','is_dayoff','is_school_holiday']).boardings.sum().reset_index()
day['m']=day.date.dt.month
wd = day[(day.is_dayoff==0)&(day.dow<=4)]
pd.set_option('display.width',250)
print("Mon-Thu working-day mean daily total by month x route")
t = wd.groupby(['m','route']).boardings.mean().unstack().round(0)
t['ALL_ex5_50_7']=t.drop(columns=[5,50,7],errors='ignore').sum(1)
print(t)
print("weekend (Sat/Sun dayoff) mean daily total by month")
we = day[(day.is_dayoff==1)&(day.dow>=5)]
t2=we.groupby(['m','route']).boardings.mean().unstack().round(0); t2['ALL_ex5_50_7']=t2.drop(columns=[5,50,7]).sum(1); print(t2)
# weekly network (ex 5,50,7) Mon-Thu working
wd2=wd[~wd.route.isin([5,50,7])].groupby('date').boardings.sum()
w=wd2.resample('W').mean()
print(w['2025-08-01':].round(0))
