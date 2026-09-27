"""Nov-Dec implications of the recommended base change: clean level (skip short school breaks/weekday holidays)
+ clean-anchor shape blend w=0.7 with per-cell cap x1.5 (fc3 variant='ratio_cap').
Writes experiments/analyst/r2_nov_dec_ratio.csv: per-cell ratio new/base, to multiply onto the existing base in the
rule pipeline (special days / route5 / weekend-restore / NY-night rules stay untouched)."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
from r2_anchor_refine import fc3
from common import full_grid
t = full_grid('2025-11-01','2025-12-31'); t['dt']=dtmap(daytype(t.date),'wk4')
p0 = forecast(D, t); p1 = fc3(D, t, 0.7, 'ratio_cap')
out = t.assign(base=p0, new=p1); out['ratio'] = np.where(out.base>0, out.new/out.base, 1.0)
print(f'total {p1.sum():,.0f} vs base {p0.sum():,.0f} ({(p1.sum()/p0.sum()-1)*100:+.2f}%), L1 moved {np.abs(p1-p0).sum():,.0f}')
print(out.groupby('route')[['base','new']].sum().assign(r=lambda x:(x.new/x.base).round(3)).to_string())
print(out.groupby('dt')[['base','new']].sum().assign(r=lambda x:(x.new/x.base).round(3)).to_string())
o = out[['route','date','hour','ratio']].copy(); o['date']=o.date.dt.strftime('%Y-%m-%d')
o.to_csv('experiments/analyst/r2_nov_dec_ratio.csv', sep=';', index=False); print('ratio quantiles', o.ratio.quantile([0,.01,.5,.99,1]).round(3).to_dict())
