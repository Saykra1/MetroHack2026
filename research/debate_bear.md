# Debate — BEAR: do not blanket-raise the Nov–Dec level
Scripts: `experiments/bear/a1.py` (Σy, calendar, monthly levels), `a2.py`/`a3.py` (backtest bias and error structure), `a4.py` (scenario simulation of LB Δ).

## 1. Is "Σy ≈ 13–13.6M" sound? Partly. It is an upper bound, and it rests on one data point.
- The v02→v03 diff is 11,160 boardings, all on Dec 31 20–23h (4678/3445/1893/1144). LB Δ = +0.00082 ⇒ Σy = 11,160/0.00082 = **13.61M**. The LB rounds to 5 decimals, so Σy ∈ [13.45, 13.78]M.
- This is an **upper bound**. If y>0 in those cells, Σy = (P − 2·y_night)/Δ, which is smaller. The support for y≈0 is real: in 2025, Jan 1 hours 0–3 have exactly 0 validations in the labels (free fare means no taps). So the bound is probably close to tight. **I cannot break this.**
- The r50/r7 probe (+110k ⇒ +0.00644) only gives Σy ≤ 17.2M, so it does not add information.
- **Independent check.** I took the error structure from the backtests (score vs Σŷ/Σy, 4 folds) and asked which Σy makes LB = 0.8948. The answers are 13.46 / 12.35 / 12.79 / 13.32M, **median ≈ 13.05M**. That means the gap is **~0.6M (+5%)**, not 1.1M (+9%). The spread is ±0.5M, so ×1.09 is at the edge of what the data support.
- **In-sample seasonality does not show a winter uplift.** Workday median totals: Jan 237k, Feb 244k, Mar 254k, Oct 243k. v06 already predicts 244k for November workdays. Across backtest folds the median bias is Σŷ/Σy ≈ 0.98, so the evidence supports about **+2%**, not +9%.

## 2. Even if a gap exists, it is not uniform: these segments should stay flat or go lower
| Segment | v06 vol | Proposed mult | Evidence | Conf. |
|---|---|---|---|---|
| Dec 26 (Fri), record snowfall, "intervals doubled" (DepTrans) | 242k | **×0.90** | 5.1 mm (ERA5, which underestimates); weather fit −1.1%/mm; tram-specific service loss | M |
| Dec 27–28 weekend (snow cover, NY-week onset) | 286k | **×0.95** | post-storm; leisure trips are the most weather-elastic (Arana 2014) | L |
| Dec 31 16–19h | 32k | **×0.80** | people are home before the NY evening; the 20h+ zeros are confirmed | L–M |
| Route 7 weekdays from Nov 13 (T1 overlap: Preobrazhenskaya–Rusakova–Sokolniki–Krasnoselskaya–Komsomolskaya, ~10 of 45 stops) | ~0.9M | **×0.96** | T1 at 6-min headways took 77k/day, 1.5× its forecast; the riders come from somewhere | L–M |
| Route 7 from Dec 16 (route 5 overlaps Palikha–Lesnaya–Belorussky, 6 stops) | ~0.3M | **×0.97** | new parallel service on a shared segment | L |
| Nov 1–4, Dec 29–30, route 5, r50/r7 Dec weekends | 1.1M | **×1.00 (exclude from any raise)** | already calibrated by analogues or the LB | H |
Total cut ≈ 91k (0.7% of volume).

## 3. Expected LB effect (a4.py, 5 synthetic truths per scenario, noise tuned so the base is ≈0.89–0.91)
| Candidate | null (Σy 12.5M) | bear (12.7M) | mid (12.95M) | bull, gap only on regular days (13.7M) | bull uniform (13.55M) |
|---|---|---|---|---|---|
| ×1.04 all | −0.007 | −0.003 | +0.003 | +0.016 | +0.014 |
| **bear cuts + ×1.03 regular only** | −0.005 | **+0.005** | +0.003 | +0.010 | +0.006 |
| ×1.08 regular | −0.021 | −0.010 | +0.001 | +0.025 | +0.016 |
The hedge is positive in 4 of 5 scenarios. A blind ×1.08 loses 0.01–0.02 if Σy ≤ 12.7M.

## 4. Recommendation
Do not raise special segments. Put any raise on regular days only (Nov 5 – Dec 25, excluding route 5 and r50/r7 Dec weekends), at **≤ ×1.03–1.04**. Apply the cuts in section 2. Let the queued probe p04c (Nov ×1.04) measure the size of the raise. If it gains more than about +0.010, the bull scenario is real and we step up.

## 5. The strongest counter-argument I cannot refute
Two estimates that do not depend on each other both point to under-prediction of **~6–9%**:
- the Dec 31 night arithmetic, where the Jan 1 2025 zeros make y≈0 credible;
- LB 0.8948, which sits ~0.013 below the unbiased backtest optimum (0.908–0.910). That gap is exactly what a 6–8% level miss costs (Oct fold: ratio 0.917 ⇒ 0.885).

Add the domain story: scooter season ends, it gets dark and cold, and the pre-New-Year peak arrives. Under that reading, if the gap sits on regular days, my hedge leaves **~0.006–0.015** on the table.
