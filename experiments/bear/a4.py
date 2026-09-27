# Scenario simulation: synthetic truths around v06, evaluate candidate multipliers. Noise: per-cell lognormal calibrated so v06 scores ~0.895.
import pandas as pd, numpy as np
v=pd.read_csv('submissions/v06_best_r50_r7.csv',sep=';',parse_dates=['date']); p=v.prediction.values.astype(float)
dt=v.date; dw=dt.dt.dayofweek; h=v.hour; r=v.route
special=((dt<='2025-11-04')|(dt>='2025-12-26'))|(r==5)|(r.isin([7,50])&(dt>='2025-12-01')&(dw>=5))
regular=~special
def bear_mult():
    m=np.ones(len(v))
    m[(dt=='2025-12-26')]*=0.90
    m[(dt>='2025-12-27')&(dt<='2025-12-28')]*=0.95
    m[((dt=='2025-12-31')&h.between(16,19))]*=0.80
    m[(r==7)&(dt>='2025-11-13')&(dw<5)]*=0.96
    m[(r==7)&(dt>='2025-12-16')]*=0.97
    return m
print('r7 total',p[r==7].sum(), 'bear cut volume',(p*(1-bear_mult())).sum())
rng=np.random.default_rng(0)
def truth(scn,sig):
    f=np.ones(len(v))
    if scn=='bull_uniform':  f*=13.55/12.47          # everything +8.7%
    if scn=='bull_regular':  f[regular]*=1.11          # gap only in regular days
    if scn=='mid':           f[regular]*=1.05; f[special&(r!=5)]*=0.97
    if scn=='bear':          f[regular]*=1.03; f*=bear_mult()**1.5   # special cuts real and stronger
    if scn=='null':          pass
    return p*f*np.exp(rng.normal(0,sig,len(v))-sig**2/2)
def sc(y,q): return 1-np.abs(y-q).sum()/y.sum()
cands={'v06':np.ones(len(v)),'x1.04 all':np.where(r!=5,1.04,1),'x1.04 regular':np.where(regular,1.04,1),
       'bear cuts':bear_mult(),'bear cuts+x1.03 reg':bear_mult()*np.where(regular,1.03,1),'x1.08 regular':np.where(regular,1.08,1)}
for scn in ['null','bear','mid','bull_regular','bull_uniform']:
    for sig in [0.11]:
        res=[];
        for k in range(5):
            y=truth(scn,sig); base=sc(y,p)
            res.append({n:sc(y,p*m)-base for n,m in cands.items()}|{'base':base,'Sy':y.sum()/1e6})
        R=pd.DataFrame(res).mean()
        print(f"{scn:13s} Sy={R.Sy:.2f}M base={R.base:.4f} | "+' '.join(f"{n}:{R[n]:+.4f}" for n in cands if n!='v06'))
