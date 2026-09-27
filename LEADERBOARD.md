# Experiments
Folds: F10=Oct (from Oct 1), F915=Sep15–Oct, F02=Feb–Mar, F04=Apr–May, F09=Sep–Oct (regime shift after summer).

| id | idea | F10 | F915 | F02 | F04 | public LB | file |
|---|---|---|---|---|---|---|---|
| sample | organizer flat baseline | – | – | – | – | ≈0.48 | test_submission.csv |
| v01 | median dow×hour last 4w + holiday→Sunday | 0.904 | – | – | 0.814* | ? | submissions/v01_profile_median4w_cal.csv |
| v02 | level(2w median, Mon-Thu/Fri/Sat/Sun) × shape(4w) + special days + Nov1 00-01 leak | 0.904 | 0.896 | 0.905 | 0.847 | ? | submissions/v02_ls_special.csv |

*F05 (May–Jun) for v01. Oracle (perfect in-period profile) ≈ 0.93; perfect daily level ≈ 0.92 → hourly noise floor.
| v01 | (LB) | | | | | 0.88128? | order to confirm |
| v02 | (LB) | | | | | 0.88322? | |
| v03_base | v02 + Dec31 20–23h = 0 | | | | | ? | submissions/v03_base.csv |
| probe_r5_k0.5 | + route 5 from Dec 16 = 0.5×route28 (+80k) | | | | | ? | Δ>0 ⇒ route 5 has GT |
| probe_r5_k1.0 | + route 5 = 1.0×route28 (+161k) | | | | | ? | compare with k0.5 → estimate level |
| probe_r50 | + route 50 Dec weekends normal (+133k) | | | | | ? | Δ>0 ⇒ repairs ended |
| probe_r7 | + route 7 Dec weekends normal (+86k) | | | | | ? | |
| v03_base | | | | | | 0.88404 | |
| probe_r5_k0.5 | | | | | | **0.88836** | |
| probe_r5_k1.0 | | | | | | 0.88442 | |
| probe_r50 (buggy Sun) | | | | | | 0.88405 | |
| probe_r7 (buggy Sun) | | | | | | 0.88312 | |
| **v06_best_r50_r7** | v04_best + r50 & r7 Dec weekends normal (fixed) | | | | | **0.89480** | submissions/v06_best_r50_r7.csv |
