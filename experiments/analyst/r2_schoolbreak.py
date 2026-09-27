"""School-break effect on daily totals: spring break Mar 24-31 and autumn break Oct 25-31 vs neighbouring weeks."""
import sys; sys.path.insert(0,'experiments/analyst')
from r2_harness import *
dd = DAILY.copy(); dd['dow']=dd.date.dt.dayofweek
def per(a,b): return dd[(dd.date>=a)&(dd.date<=b)].groupby(['route','dt']).tot.mean()
spring_break = per('2025-03-24','2025-03-30'); spring_ref = (per('2025-03-10','2025-03-23'))
spring_after = per('2025-04-07','2025-04-13')
aut_break = per('2025-10-25','2025-10-31'); aut_ref = per('2025-10-11','2025-10-24')
t = pd.DataFrame({'spring_vs_before':spring_break/spring_ref,'spring_vs_after':spring_break/spring_after,'autumn_vs_before':aut_break/aut_ref}).unstack('dt')
print(t.round(3).to_string())
tot=lambda s: s.groupby(level=1).sum()
print('network', pd.DataFrame({'spring_vs_before':tot(spring_break)/tot(spring_ref),'spring_vs_after':tot(spring_break)/tot(spring_after),'autumn_vs_before':tot(aut_break)/tot(aut_ref)}).round(3))
# daily network totals in Oct
x=dd[dd.date>='2025-10-01'].groupby('date').tot.sum()
print((x/1000).round(1).to_frame().assign(dow=x.index.dayofweek).T.to_string())
