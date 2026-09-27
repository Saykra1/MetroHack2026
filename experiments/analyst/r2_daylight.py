"""Idea 1: daylight/temperature-conditioned hourly-shape adjustment. Fit per (dt,hour) slope of log-share on
daylight (or temperature) from history weeks (school breaks/holidays dropped), apply exp(b*(x_target - x_window))
to the base shape and renormalise so the daily total is unchanged."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *

def daylight(dates, lat=55.75):
    doy = pd.DatetimeIndex(dates).dayofyear.values
    decl = 23.44*np.pi/180*np.sin(2*np.pi*(284+doy)/365)
    la = lat*np.pi/180
    return 24/np.pi*np.arccos(np.clip(-np.tan(la)*np.tan(decl), -1, 1))
W = pd.read_csv('research/weather_moscow_2025.csv', parse_dates=['datetime'])
TEMP = W.groupby(W.datetime.dt.normalize()).temperature_2m.mean()
calx = cal.set_index('date')
BAD = set(calx.index[(calx.is_school_holiday==1)|((calx.is_holiday==1)&(calx.dow<5))])

def covar(dates, kind):
    return daylight(dates) if kind=='day' else TEMP.reindex(pd.DatetimeIndex(dates)).values

def make_adj(kind='day', lam=1.0, WS=4, dts=(0,4,5,6)):
    def adj(t, p, hist):
        end = hist.date.max()
        h = hist[(hist.route!=5) & ~hist.date.isin(BAD)].copy()
        h['wk'] = h.date.dt.to_period('W')
        g = h.groupby(['dt','wk','hour']).boardings.sum()
        sh = np.log((g / g.groupby(level=[0,1]).transform('sum')).clip(lower=1e-4))
        wkx = h.groupby('wk').date.apply(lambda s: np.nanmean(covar(s.unique(), kind)))
        df = sh.rename('ls').reset_index(); df['x'] = df.wk.map(wkx)
        df['ls_c'] = df.ls - df.groupby(['dt','hour']).ls.transform('mean')
        df['x_c'] = df.x - df.groupby(['dt','hour']).x.transform('mean')
        b = (df.ls_c*df.x_c).groupby([df.dt,df.hour]).sum() / (df.x_c**2).groupby([df.dt,df.hour]).sum()
        win = hist[hist.date > end - pd.Timedelta(weeks=WS)].date.unique()
        xw = np.nanmean(covar(win, kind))
        tt = t[['route','date','hour','dt']].copy(); tt['p']=p
        tt['b'] = pd.MultiIndex.from_arrays([tt.dt, tt.hour]).map(b.to_dict()).fillna(0).values if False else [b.get((a,c),0.0) for a,c in zip(tt.dt,tt.hour)]
        tt.loc[~tt.dt.isin(dts),'b']=0
        tt['x'] = covar(tt.date, kind)
        tt['q'] = tt.p*np.exp(lam*tt.b*(tt.x - xw))
        s0 = tt.groupby(['route','date']).p.transform('sum'); s1 = tt.groupby(['route','date']).q.transform('sum')
        return np.where(s1>0, tt.q*s0/s1, tt.p)
    return adj

if __name__=='__main__':
    B = score(); rows=[]
    for kind in ['day','temp']:
        for lam in [0.5,1.0]:
            for dts in [(0,4,5,6),(0,4)]:
                s = score(shape_adj=make_adj(kind,lam,dts=dts)) - B
                rows.append({'idea':f'{kind} lam{lam} dts{dts}', **{k[5:]:v*1e3 for k,v in s.items()}, 'mean':s.mean()*1e3,'wins':(s>0).sum()})
                print(rows[-1], flush=True)
    print(pd.DataFrame(rows).round(2).to_string())
    # implication for Nov-Dec: fit on all history, window Oct 4-31
    hist=D; fut=full = D[D.date>='2025-10-01'].copy()
    from common import full_grid
    t = full_grid('2025-11-01','2025-12-31'); t['dt']=dtmap(daytype(t.date),'wk4')
    p0 = forecast(D, t)
    for kind in ['day','temp']:
        p1 = forecast(D, t, shape_adj=make_adj(kind,1.0))
        print(kind, 'Nov-Dec: sum|p1-p0| =', round(np.abs(p1-p0).sum()), 'of', round(p0.sum()), f'({np.abs(p1-p0).sum()/p0.sum()*100:.2f}%)')
        tt=t.assign(p0=p0,p1=p1); g=tt.groupby('hour')[['p0','p1']].sum(); print(((g.p1/g.p0-1)*100).round(2).loc[5:23].to_dict())
