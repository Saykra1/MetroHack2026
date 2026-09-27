import pandas as pd, numpy as np, sys
sys.path.insert(0,'src')
from common import load_labels, wape_score
from model_ls import forecast
d=load_labels()
print('--- implied Sigma_y from LB 0.8948 using backtest error structure (score vs total ratio) ---')
for s,e in [('2025-02-01','2025-03-31'),('2025-03-01','2025-04-30'),('2025-09-15','2025-10-31'),('2025-10-01','2025-10-31')]:
    hist,fut=d[d.date<s],d[(d.date>=s)&(d.date<=e)]
    p=forecast(hist,fut,2,4,'wk4','median','sum'); y=fut.boardings.values; b0=p.sum()/y.sum()
    rows=[]
    for c in np.arange(0.85,1.15,0.0025):
        q=p*c; r=q.sum()/y.sum(); sc=wape_score(y,q); O=np.clip(q-y,0,None).sum()/y.sum(); rows.append((r,sc,O))
    R=pd.DataFrame(rows,columns=['ratio','score','O'])
    best=R.loc[R.score.idxmax()]
    under=R[R.ratio<best.ratio]; i=(under.score-0.8948).abs().idxmin()
    at917=R.iloc[(R.ratio-0.917).abs().idxmin()]
    print(f"{s}: best score {best.score:.4f} at ratio {best.ratio:.3f}; score=0.8948 at ratio {R.ratio[i]:.3f} -> Sy={12.47/R.ratio[i]:.2f}M; at ratio .917: score {at917.score:.4f}, overpred share O={at917.O:.3f}")
print('LB implied: if Sy=13.6M, O=(E-bias)/2/Sy =', ((1-0.8948)*13.6-(13.6-12.47))/2/13.6)
v=pd.read_csv('submissions/v06_best_r50_r7.csv',sep=';',parse_dates=['date'])
T=v.prediction.sum(); print('v06 total',T)
def seg(name,m): s=v[m].prediction.sum(); print(f'{name:40s} {s:>10,.0f} ({s/T:.1%})')
dt=v.date; dw=dt.dt.dayofweek
seg('route5',v.route==5)
seg('Nov1-4',(dt>='2025-11-01')&(dt<='2025-11-04'))
seg('Dec26 (snowstorm Fri)',dt=='2025-12-26')
seg('Dec27-28 weekend',(dt>='2025-12-27')&(dt<='2025-12-28'))
seg('Dec29-30',(dt>='2025-12-29')&(dt<='2025-12-30'))
seg('Dec31',dt=='2025-12-31')
seg('Dec31 16-19h',(dt=='2025-12-31')&v.hour.between(16,19))
seg('r7+r50 weekdays Nov13-Dec31',v.route.isin([7,50])&(dt>='2025-11-13')&(dw<5))
seg('r7+r50 Dec weekends',v.route.isin([7,50])&(dt>='2025-12-01')&(dw>=5))
seg('r7,11,12 Dec20-31',v.route.isin([7,11,12])&(dt>='2025-12-20'))
seg('Dec22-26 weekdays',(dt>='2025-12-22')&(dt<='2025-12-26'))
seg('regular Nov5-Dec21 all',(dt>='2025-11-05')&(dt<='2025-12-21')&(v.route!=5))
# daily totals by month/daytype predicted vs Oct actual
D=d.groupby('date').boardings.sum()
print('Oct actual workday median',D['2025-10-01':][D['2025-10-01':].index.dayofweek<5].median(), 'Sat',D['2025-10-01':][D['2025-10-01':].index.dayofweek==5].median(),'Sun',D['2025-10-01':][D['2025-10-01':].index.dayofweek==6].median())
P=v[v.route!=5].groupby('date').prediction.sum()
print('v06 Nov workday median',P['2025-11-05':'2025-11-30'][P['2025-11-05':'2025-11-30'].index.dayofweek<5].median())
W=pd.read_csv('research/weather_moscow_2025.csv'); W['ts']=pd.to_datetime(W.datetime)
w=W[W.ts.dt.hour.between(6,21)].groupby(W.ts.dt.normalize()).agg(pr=('precipitation','sum'),sn=('snowfall','sum'),t=('temperature_2m','mean'))
print(w['2025-11-01':].query('pr>4 or t<-10').round(1))
print('Oct18-31 mean pr',w['2025-10-18':'2025-10-31'].pr.mean().round(2))
