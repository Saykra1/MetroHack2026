# BULL: the Nov–Dec level is too low. Raise it by about 2–3%, mostly on Fri, Sun and holidays
Scripts: experiments/bull/a1–a7.py (these are offline only; src/ and submissions/ were not touched).

## Evidence
1. **The level window is contaminated (a1, a3, a6).** The 2-week window (Oct 18–31) includes the Moscow autumn school break (Oct 25 – Nov 2) and Fri Oct 31. Oct 31 is the Friday before the Nov 1–4 long weekend: 176.0k against 187.9–194.2k on the other October Fridays. On a 2-point median this pulls the Friday level down.
   To measure the bias I compared a clean October (Oct 1–24) with the v06 level (Nov 10–23), on the 7 untouched routes:
   **Mon–Thu 0.997, Fri 1.028, Sat 1.014, Sun 1.042.** The Sun/holiday level also feeds Nov 2–4.
   The rolling backtest (a4) shows the break week itself running −2.7% (cutoff Oct 24, wk1 = 0.973). That is a temporary dip, not a new level.
2. **The model has an upward bias problem in every non-summer backtest (a5).** Plain level×shape under-predicted the fold total in all three non-summer folds:
   - Σy/Σŷ = 1.039 (Oct), 1.020 (Sep15–Oct), 1.049 (Feb–Mar).
   - A uniform ×1.03 scored +0.0036, +0.0020 and +0.0051 on those folds.
   - The rolling 8-week ratios for autumn cutoffs (Sep 12 – Oct 10) come out at 1.00–1.03.
   - Late-winter cutoffs (Jan 24 – Feb 28) come out at 1.02–1.08 for weeks 1–6.

   This matches the +1.6% intercept in the weather regression. The median level carries a structural downward bias in the cold season.
3. **The network trend is still rising.** Weekly Mon–Thu totals on the untouched routes were 184k in September and 187.5k → 191.0k through October (about +0.5% per week). By freezing the level we assume the trend stops dead on Nov 1.
4. **The leaderboard suggests we are well below the truth.**
   - Σy from the Dec-31 probe is 11,160/0.00082 ≈ 13.4–13.8M, against our total of 12.47M. That is a gap of 7–10%.
   - If Σy ≈ 13.3M, then at LB 0.8948 the error splits into U − O = 0.83M and U + O = 1.40M. Under-prediction is then about 80% of all absolute error; an unbiased level would give roughly 50/50.
   - The v06 weekend restoration added 110k and gained +0.0064. That is about 86k net useful, so roughly 89% of the added volume landed under the truth: those cells were far too low.
5. **Domain.** Several things push Nov–Dec up:
   - Micromobility (scooter and bike share) ends in November, and trips move to transit.
   - Nov 5 – Dec 26 is full school and work term, with no holidays other than Nov 3–4.
   - Pre-New-Year shopping and fairs lift weekends and evenings from mid-December.
   - Early December was record-dry, so the precipitation penalty is small.

## Payoff (a7: Δscore by true bias × multiplier, mean of 3 folds)
| true Σy/Σŷ | ×1.02 | ×1.03 | ×1.05 |
|---|---|---|---|
| 1.00 | −0.0023 | −0.0045 | −0.0108 |
| 1.02 | +0.0008 | 0.0000 | −0.0035 |
| 1.04 | +0.0035 | +0.0042 | +0.0035 |
| 1.066 (LB-implied) | +0.0066 | +0.0090 | +0.0118 |

The break-even for ×1.02 is a bias of about 1.012. The backtests (1.02–1.05) and the leaderboard (≥1.07) both sit above that.

## Proposal (Nov 1 – Dec 31)
Applies to all routes except route 5, and except the r50/r7 December weekends, which are already rebuilt from the Oct weekday level.
- **Tier A (high confidence, window de-bias):**
  - Fri ×1.03, Sat ×1.015, Sun and holidays (incl. Nov 2–4) ×1.04.
  - Adds about +125k. Expected +0.003..+0.006; downside about −0.002 only if Nov falls below clean October.
- **Tier B (medium confidence, seasonal and trend):**
  - Mon–Thu ×1.02 across Nov–Dec. Adds about +155k.
  - Optionally Dec 1–26 ×1.03 instead of 1.02, for the pre-New-Year uplift.
  - Leave Dec 29–31 unchanged.
- **Combined:** about +2.3% (≈ +285k → 12.76M), still below the implied Σy.
  - Expected LB: about +0.004 (at bias 1.04) to about +0.009 (at 1.066).
  - Loss is about −0.003 if the true bias is 1.00.
- **If one probe is available:** upload Tier A + B together. If Δ > +0.003, a further uniform ×1.02 is justified (bias ≥ 1.05). If Δ < 0, revert.

## The counter-argument I can't refute
The Σy ≈ 13.3M figure rests on a single probe (Δ 0.00082, with ±1.2% rounding). It is also an **upper bound**, because it assumes zero validations on Dec 31 from 20:00 to 23:00. If about 12 taps per cell remained, the same probe gives Σy ≈ 12.5M and the leaderboard gap disappears.

The data has no Nov–Dec analogue. January working days (182k) sat about 4% *below* October (189k), so winter may run level or lower. Cold snaps (Dec 13–15, Dec 23–24), the Dec 26 snowfall and T1 diverting riders from 7/50/11/12 after Nov 13 all point down.

On that view, only Tier A (window contamination) is solidly supported. Tier B is a bet on the backtest bias carrying over.
