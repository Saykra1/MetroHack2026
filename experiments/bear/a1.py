import pandas as pd, numpy as np, sys
sys.path.insert(0,'src')
from common import load_labels
S=lambda f: pd.read_csv(f'submissions/{f}.csv',sep=';',parse_dates=['date'])
v02,v03,v04,v06=S('v02_ls_special'),S('v03_base'),S('v04_best'),S('v06_best_r50_r7')
for n,d in [('v02',v02),('v03',v03),('v04',v04),('v06',v06)]: print(n,d.prediction.sum())
P=(v02.prediction-v03.prediction).sum(); print('Dec31 night zeroed P=',P,' Sy_upper=',P/0.00082, 'range',P/0.000825,P/0.000815)
d=(v06.prediction-v04.prediction); print('v06-v04 add',d.sum(),' Sy_upper',d.sum()/0.00644)
D=load_labels()
print(D.date.min(),D.date.max(),len(D))
j=D[D.date=='2025-01-01'].groupby('hour').boardings.sum(); print('Jan1 by hour',j.head(8).to_dict())
j2=D[D.date=='2025-01-02'].groupby('hour').boardings.sum(); print('Jan2 by hour',j2.head(8).to_dict())
# typical Sat night hours share
DD=D.groupby('date').boardings.sum()
cal=pd.read_csv('research/calendar_2025.csv',parse_dates=['date']).set_index('date')
m=DD.to_frame('t').join(cal)
m['month']=m.index.month
wd=m[(m.is_dayoff==0)]
print('workday median total by month (all routes, excl 5):'); print(wd.groupby('month').t.median().round(0))
print('weekly workday median Sep-Oct'); w=wd['2025-09-01':]; print(w.groupby(w.index.to_period('W')).t.median())
print('school hol Oct-Dec', cal.loc['2025-10-01':'2025-12-31'].query('is_school_holiday==1').index.strftime('%m-%d').tolist())
print(cal.loc['2025-10-30':'2025-11-05']); print(cal.loc['2025-12-26':'2025-12-31'])
