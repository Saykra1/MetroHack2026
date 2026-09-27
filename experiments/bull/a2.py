import sys; sys.path.insert(0,'src')
from common import *
rd=lambda f: pd.read_csv('submissions/'+f, sep=';', parse_dates=['date'])
v02=rd('v02_ls_special.csv'); v03=rd('v03_base.csv'); v04=rd('v04_best.csv'); v06=rd('v06_best_r50_r7.csv')
for n,x in [('v02',v02),('v03',v03),('v04',v04),('v06',v06)]: print(n, x.prediction.sum())
m=v02.merge(v03,on=['route','date','hour'],suffixes=('_2','_3'))
Z=(m.prediction_2-m.prediction_3).sum(); print('Z dec31 night',Z, 'Sigma_y upper = Z/0.00082 =',Z/0.00082, 'range', Z/0.00083, Z/0.00081)
v06['m']=v06.date.dt.month
print(v06.groupby(['m','route']).prediction.sum().unstack(0))
print(v06.groupby('m').prediction.sum())
