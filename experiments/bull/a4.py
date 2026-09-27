import sys; sys.path.insert(0,'src')
from common import *
d = load_labels()
cal = pd.read_csv('research/calendar_2025.csv', parse_dates=['date'])
day = d.groupby(['route','date']).boardings.sum().reset_index().merge(cal,on='date')
def dt4(r):
    if r.is_dayoff==1 and r.dow!=5: return 3
    if r.dow==5: return 2
    if r.dow==4: return 1
    return 0
day['dt']=[3 if (o==1 and w!=5) else (2 if w==5 else (1 if w==4 else 0)) for o,w in zip(day.is_dayoff,day.dow)]
core=[1,11,12,17,25,26,28]
day=day[day.route.isin(core)]
normal = (day.is_official_holiday==0)&(day.is_transferred_dayoff==0)&(day.is_preholiday_shortened==0)
rows=[]
for cut in pd.date_range('2025-01-24','2025-10-31',freq='W-FRI'):
    h=day[(day.date<=cut)&(day.date>cut-pd.Timedelta(weeks=2))]
    L=h.groupby(['route','dt']).boardings.median().rename('L')
    f=day[(day.date>cut)&(day.date<=cut+pd.Timedelta(weeks=8))&normal].join(L,on=['route','dt'])
    f=f.dropna()
    for wk in range(8):
        g=f[(f.date>cut+pd.Timedelta(weeks=wk))&(f.date<=cut+pd.Timedelta(weeks=wk+1))]
        if len(g): rows.append((cut,wk+1,g.boardings.sum()/g.L.sum()))
r=pd.DataFrame(rows,columns=['cut','wk','ratio'])
p=r.pivot(index='cut',columns='wk',values='ratio').round(3)
pd.set_option('display.width',250); print(p)
print('overall mean ratio (8w):'); print(r.groupby('cut').ratio.mean().round(3).describe())
