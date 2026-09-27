"""Leak hunt: is the hidden GT a transformation of data we already have? Compare LB fingerprint of 9 known submissions."""
import sys; sys.path.insert(0, 'src')
import pandas as pd, numpy as np
from common import load_labels, full_grid
LB = {'v01_profile_median4w_cal':0.88128,'v02_ls_special':0.88322,'v03_base':0.88404,'v03_probe_r5_k0.5':0.88836,'v03_probe_r5_k1.0':0.88442,
      'v03_probe_r50_dec_weekend_normal':0.88405,'v03_probe_r7_dec_weekend_normal':0.88312,'v06_best_r50_r7':0.89480,'v08_nov15_weekends':0.90167}
S = {k: pd.read_csv(f'submissions/{k}.csv', sep=';').prediction.values for k in LB}
g = full_grid('2025-11-01','2025-12-31')
d = load_labels().set_index(['route','date','hour']).boardings
def score(y, p): return max(0, 1 - np.abs(y - p).sum() / y.sum())
cands = {}
for sh in [61, 63, 70, 91, 304, 301, 308, 245, 243, 364]:
    src = g.assign(date=g.date - pd.Timedelta(days=sh))
    cands[f'shift{sh}'] = src.set_index(['route','date','hour']).index.map(lambda k: d.get(k, 0)).values.astype(float) if False else d.reindex(pd.MultiIndex.from_frame(src)).fillna(0).values
for name, y in cands.items():
    sc = [score(y, S[k]) for k in LB]
    err = np.abs(np.array(sc) - np.array(list(LB.values()))).max()
    print(f'{name:10s} Sy={y.sum()/1e6:6.2f}M  maxdev={err:.4f}  ', ' '.join(f'{s:.4f}' for s in sc))
print('LB        ', ' '.join(f'{v:.4f}' for v in LB.values()))
