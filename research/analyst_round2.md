# Analyst round 2: offline-validated improvements to the base model

Baseline is `model_ls.forecast(WL=2, WS=4, mode='wk4', lagg='median')`, reproduced exactly in `experiments/analyst/r2_harness.py`.
Fold scores: 10-01 0.9044 | 09-15 0.8955 | 02-01 0.9048 | 03-01 0.8767 | 04-01 0.8470 | 09-01 0.8090 | mean 0.8729.
All deltas are in units of 1e-3 WAPE-score versus that baseline, on `model_ls.FOLDS`. "wins" counts folds out of 6 where the change improved the score.
Fold 09-01 is inflated for any change that dilutes August (summer) data, so the report also gives the mean without it (`ex0901`).
No leaderboard submissions were used.

## Main result
**Recommended new base = clean level + clean-anchor shape (w = 0.7, cap ×1.5).**
- Mean +4.86, 6/6 wins, Oct fold +4.0 (0.9044 → 0.9084).
- Nov–Dec effect: total +210k (+1.69%), L1 change 475k.
- Plug-in file: `experiments/analyst/r2_nov_dec_ratio.csv`. It holds the per-cell ratio new/base; multiply it onto the current base before the rule layer.

## Idea → fold deltas → mean → recommendation

| # | Idea (exact settings) | 10-01 | 09-15 | 02-01 | 03-01 | 04-01 | 09-01 | mean | ex0901 | wins | Rec. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | **Clean-anchor shape**: S = 0.3·S_4w + 0.7·S_anchor, where S_anchor = hourly share over all history before the origin excluding school breaks (incl. summer), weekday holidays and Jan 1–12 | 3.96 | 10.56 | 0.11 | 0.01 | 0.73* | 12.13 | 4.6 | 3.1 | 6 | **YES** |
| B | **Clean level**: median of the last k non-excluded days per route×daytype, k = {Mon–Thu 8, Fri 2, Sat 2, Sun 2}, looking back ≤ 6 weeks. Excluded days are short school breaks (< 14 d: Mar 24–31, Oct 25–Nov 2), weekday holidays and Jan 1–12 | 0 | 0 | 0 | 0 | 1.57 | 0 | 0.26 | 0.31 | 1 (no loss) | **YES** (matters in production, see below) |
| A+B | Both, plus cap: blended share clipped to [S_4w/1.5, S_4w·1.5] and renormalised per route-day (`r2_anchor_refine.fc3(w=0.7, variant='ratio_cap')`) | 4.00 | 10.60 | 0.10 | 0.01 | 2.28 | 12.16 | **4.86** | **3.40** | **6** | **FINAL** |
| A' | Anchor-weight grid (weekday / weekend): 0.5/0.5 → 4.17, 0.7/0.7 → 4.84, 0.85/0.85 → 5.01 (only 4 wins), 1.0/1.0 → 4.87. Weekday-only 0.7 → 3.51; weekend-only 0.7 → 1.60 | | | | | | | plateau | | | Use 0.7 (the robust middle) |
| A'' | Control: anchor = spring only (Apr 1–May 20) gives Oct fold +1.5; winter (Jan 13–Feb 28) +4.0; Feb–Mar +4.2 | | | | | | | | | | Clean long anchor; the winter part helps most |
| 1 | Daylight-conditioned shape (per dt×hour log-share slope on daylight, λ = 0.5, all dt) | 1.07 | 2.51 | −17.7 | −1.1 | 0.44 | 3.08 | −1.95 | | 4 | NO |
| 1 | Temperature-conditioned, λ = 0.5, weekdays only | 0.69 | 1.33 | −0.30 | −1.54 | −1.23 | 1.32 | +0.04 | | 3 | NO |
| 2 | Level mean instead of median, WL = 2 | −3.5 | 0.4 | 2.3 | −1.3 | 2.3 | 3.6 | 0.64 | 0.04 | 4 | NO |
| 2 | Level trimmed mean, WL = 3 / 4 | | | | | | | −2.4 / −8.5 | | | NO |
| 2 | Level median, WL = 3 | | | | | | | −1.8 | | | NO |
| 2 | Level exponential weighting, half-life 7 d, WL = 3 | −0.7 | −3.2 | 1.4 | 0.4 | 3.2 | 6.6 | 1.28 | 0.22 | 4 | NO (noise) |
| 2 | Level outlier drop (< 0.8 × window median) | | | | | | | −0.07 | | | NO |
| 2 | Weekday ratios from a long window (4/6/8 w) × recent Mon–Thu level | | | | | | | −3.1 / −4.4 / −5.1 | | | NO |
| 2 | Constant multiplier ×1.01 on the base | 1.9 | 1.3 | 2.4 | 1.2 | −3.4 | 5.0 | 1.41 | 0.70 | 5 | see note |
| 2 | ×1.02 on the base | 3.1 | 2.0 | 4.1 | 1.8 | −7.4 | 9.7 | 2.21 | 0.72 | 5 | see note |
| 2 | ×1.01 / ×1.02 on top of FINAL | 6.1 / 7.5 | 12.0 / 12.6 | 2.5 / 4.2 | 1.2 / 1.7 | −0.9 / −4.9 | 18.0 / 23.5 | +1.6 / +2.6 over FINAL | | 5 | see note |
| 4 | Longer Sat/Sun level window, WL_we = 3 / 4 / 6 | | | | | | | −0.8 / −2.6 / −4.4 | | 1–2 | NO |
| 4 | Sat/Sun last-3 clean days (with B) | | | | | | | −0.3 | | | NO |
| 3 | James-Stein shrinkage toward the route's 12-week shape, k = 5 / 20 / 50 (k in thousands of boardings) | | | | | | | −0.03 / −0.19 / −0.57 | | | NO (the 12-week window is summer-contaminated) |
| 3 | Shrinkage toward the pooled all-route shape, k = 5 | 0.1 | 0.1 | 0.1 | 0.2 | 0.1 | 0.0 | +0.10 | 0.13 | 5 | negligible; superseded by A |
| 5 | Shape from the median / mean of daily shares instead of the sum ratio | | | | | | | −0.41 / −0.27 | | | NO |
| – | Shape window WS = 3 / 6 / 8 | | | | | | | +0.85 / −2.4 / −4.9 | | | NO (+0.85 is noise; A dominates) |

\* Row A's 04-01 value is with the old level; with B it becomes 2.28.

## Findings behind the recommendation
- **Weekday hourly shape barely moves with season.** Shares of 20–23h:
  - Jan 8.1%, Feb 8.3%, Mar 8.2%, Apr 8.8%, May 9.3%, Sep 8.5%, Oct 8.1%.
  - Evening centroid stays at 17.30–17.43h.
  - October already looks like January.
- **Daylight and temperature models over-extrapolate.**
  - They would push Nov–Dec 20–23h down by 2–5% and 5–6h down by about 3%.
  - The Jan–Feb data contradict that. Across the folds these models are net negative.
- **Idea 1 is better done as a shape anchor.** Blending in a clean long-term shape (which is dominated by Jan–May and Sep–Oct) captures the "darker season" effect and reduces 4-week sampling noise. Longer raw windows (WS = 8, or the 12-week prior) hurt because they include August.
- **The production level is contaminated.** The Oct 18–31 window includes the autumn school break (Oct 25–31) and an anomalous Friday Oct 31.
  - Oct 31 network total was 225.6k against about 243k on the other October Fridays (−7%).
  - Effect of the break on Oct 25–31 against the two preceding weeks: Mon–Thu −1%, Fri −7.6%, Sat/Sun −3%.
  - B changes the network level by dt as follows: Mon–Thu +0.9%, Fri +3.6%, Sat +1.1%, Sun/holiday +3.7%.
  - By route: 7 +4.9%, 25 +4.7%, 11 +2.6%, 1 and 17 +2.3%, 12 −0.9%, 50 −1.1%.
- **The "+1.6% intercept" is mostly this contamination, not a general bias.** A rolling 1-week-ahead nowcast of the base is unbiased: median predicted/actual is 0.998.
  - The ×1.01–1.03 gains in the folds come from seasonal growth periods (Jan→Mar, Aug/Sep→Oct).
  - The Apr–May fold, a declining period, loses.
  - Whether Nov–Dec grows over October cannot be validated offline. The +1.69% from B already covers the documented intercept.
  - **Recommendation:** no extra blanket multiplier, or at most ×1.01 as an LB probe.
- **Route 50 caveat.** Its October weekends are repair-affected: the clean level gives Sat ×1.34 and Sun ×0.72. December is overridden by the weekend-restore rule. For **November weekends of route 50**, decide explicitly: keep the base ratio, or apply the rule if the repairs ended.
- **Edge hours.** The anchor can move night and edge hours (4–5h, 23–1h) a lot on routes that recently changed their first or last trips. The ×1.5 cap guards against that at zero cost: 4.86 with the cap against 4.84 without.

## Idea 6: route 5 proxy
- Route 5 (Рижская → Белорусский вокзал, 16 stops, 4.4 km, about 3.6 km from the centre) shares 8 of its 16 stops with **route 7**. This is the whole segment from Гиляровского through Палиха and Лесная to Белорусская and Белорусский вокзал.
- Route 7 is therefore the natural proxy for the hourly shape. Its AM/PM share ratio is 0.70, more evening-heavy than route 28's 0.82, as expected near a rail terminal. Its weekend ratios are Sat 0.63 and Sun 0.50 (pre-repair) against route 28's 0.62 and 0.52.
- Weekday shapes of all routes differ by only 3–6% of mass (L1/2). Route 5 → route 7 shape versus → route 28 shape moves about 5% of route 5's roughly 90k boardings, which is under 5k and about 0.0003 of the score. **Not worth an LB probe.**
- Keep the k = 0.5 × route-28 level. If the team rebuilds the rule, using the route-7 shape with the route-28 level is equally defensible and makes the better story ("overlapping segment").
- Possible cannibalisation of route 7 after Dec 16, because the segment is shared: not testable offline.

## Scripts (experiments/analyst/)
- `r2_harness.py`: generalised level×shape model and fold scorer (reproduces model_ls exactly).
- `r2_diag.py`: per-fold bias and best multiplier.
- `r2_bias.py`: rolling weekly bias.
- `r2_level_shape.py`: ideas 2–5 grid (`r2_level_shape.csv`).
- `r2_schoolbreak.py`: school-break and Oct 31 effects.
- `r2_shape_season.py`, `r2_daylight.py`, `r2_winter_analog.py`, `r2_analog_control.py`: idea 1.
- `r2_clean_anchor.py`, `r2_clean_level.py`, `r2_anchor_grid.py`, `r2_anchor_refine.py`: A and B.
- `r2_final_mult.py`: multiplier on top of FINAL.
- `r2_route5_proxy.py`: idea 6.
- `r2_production_candidate.py`: writes `r2_nov_dec_ratio.csv` (route;date;hour;ratio; ratio range 0.56–2.09, median 1.003).

## Summary (≤ 12 lines)
1. The best offline change is **clean-anchor shape + clean level**: mean +4.86e-3, **6/6 folds improved**, Oct fold 0.9044 → 0.9084.
2. Shape: S = 0.3·S_4w + 0.7·S_anchor. The anchor is all history excluding school breaks and summer, weekday holidays and Jan 1–12. Clip to ×/÷1.5 of S_4w and renormalise per route-day.
3. Level: median of the last 8 Mon–Thu / 2 Fri / 2 Sat / 2 Sun days, skipping Oct 25–Nov 2 and Mar 24–31 style breaks and weekday holidays (look back ≤ 6 weeks).
4. Nov–Dec impact: +210k total (+1.69%; Fri +3.6%, Sun +3.7%). Apply it by multiplying `experiments/analyst/r2_nov_dec_ratio.csv` onto the current base.
5. The production level window is contaminated by the school break and by Oct 31 (−7% Friday). This, not a generic bias, explains the +1.6% intercept; the 1-week nowcast is unbiased (0.998).
6. Don't add a blanket ×1.02: its fold gains come from seasonal-growth periods and it loses in the declining fold. ×1.01 is at most an LB probe.
7. Hourly shape barely changes with season; Oct ≈ Jan. Daylight and temperature regressions over-extrapolate and are net negative, so they are rejected.
8. Longer Sat/Sun windows, trimmed or mean or EW levels, long-window weekday ratios, JS shrinkage and median shares are all ≤ 0: rejected.
9. Route 5: route 7 shares 8 of 16 stops, so it is the best shape proxy, but the effect is about 0.0003. Keep the 0.5 × route-28 level.
10. Open issue: November weekends of route 50 (the repair regime distorts both level and shape); needs an explicit rule decision.
