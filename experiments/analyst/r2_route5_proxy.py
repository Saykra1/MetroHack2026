"""Idea 6: route-5 proxy. Features per route (Sep 8 - Oct 24, clean days; r7/r50 weekends from pre-repair Mar-May):
AM/PM/midday/evening shares, Sat/Sun to Mon-Thu ratios, and hourly-shape L1 distance to route 7 (which shares the
Гиляровского–Белорусский segment with route 5)."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
x = D[(D.date>='2025-09-08')&(D.date<='2025-10-24')&(D.route!=5)]
pre = D[(D.date>='2025-03-03')&(D.date<='2025-05-20')&(D.route.isin([7,50]))&~D.date.between('2025-03-24','2025-03-31')]
rows=[]
for r in sorted(x.route.unique()):
    xr = x[x.route==r]; 
    wk = xr[xr.dt==0].groupby('hour').boardings.sum(); wk=wk/wk.sum()
    dl = xr.groupby(['date','dt']).boardings.sum().reset_index().groupby('dt').boardings.median()
    src = pre[pre.route==r] if r in (7,50) else xr
    dl2 = src.groupby(['date','dt']).boardings.sum().reset_index().groupby('dt').boardings.median()
    rows.append({'route':r,'MonThu_daily':dl[0],'AM7-9':wk.loc[7:9].sum(),'mid10-15':wk.loc[10:15].sum(),'PM16-19':wk.loc[16:19].sum(),'eve20-23':wk.loc[20:23].sum(),
                 'AM/PM':wk.loc[7:9].sum()/wk.loc[16:19].sum(),'Sat/wk':dl2[5]/dl2[0],'Sun/wk':dl2[6]/dl2[0],'Fri/wk':dl[4]/dl[0]})
f = pd.DataFrame(rows).set_index('route')
S = x[x.dt==0].groupby(['route','hour']).boardings.sum().unstack(); S=S.div(S.sum(1),axis=0)
f['L1_to_r7'] = (S.sub(S.loc[7]).abs().sum(1)/2)
f['L1_to_r28'] = (S.sub(S.loc[28]).abs().sum(1)/2)
pd.set_option('display.width',200); print(f.round(3).to_string())
