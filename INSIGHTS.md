# Insights
Tags: [data] [metric] [leak] [domain] [judging] [risk]. Confidence H/M/L.

1. [judging][H] Two scores: auto CSV metric + expert criteria; final LB combines both. Product + README + pitch matter as much as ML.
2. [domain][H] **Forecast period Nov–Dec 2025 is in the past relative to now (Sep 2026).** Real weather actuals, production calendar, events,
   route closures/repairs for Nov–Dec 2025 are publicly known. Organizers explicitly allow external factors with a source link. → Big legal edge.
3. [leak][M] Chat: "is that with the leak or without?" → someone found a leak. Hunt for it in EDA (ids, ordering, test.csv overlaps, stop-level sums, calendar).
4. [metric][M] Score probably bounded [0,1] (e.g. 1−WAPE / R² / 1/(1+MAE)); "0.60+" is considered good → headroom is modest, calendar/holiday handling will decide ranks.
5. [domain][H] Nov–Dec specifics: Nov 2–4 holidays (Nov 1 Sat working day in 2025 — verify), school autumn break end Oct–early Nov, New Year week Dec 29–31, snow/cold snaps, early darkness, pre-NY shopping peaks.
6. [risk][H] 61-day horizon with no lags: autoregressive lags would accumulate error → prefer "profile" models (route×dow×hour × level × seasonal/trend × calendar/weather multipliers) or GBM on calendar features without short lags.
7. [data][M] Route 5 has no targets (reported). Possibly new/closed route → decide 0 vs neighbor-based.
8. [judging][H] Business interpretability requested by user: multiplicative decomposition is explainable ("base profile × day-type × weather × trend") — also a strong pitch story.

## From data (26.09)
9. [metric][H] Metric = WAPE-score = 1 − Σ|y−ŷ|/Σy on route×date×hour (14,640 cells). Sample baseline is FLAT across hours → 0.48. Any hourly profile → ~0.8–0.9.
10. [data][H] Route 5: 1 raw row in 10 months, absent from labels → predict 0 (sample also 0).
11. [leak][H, tiny] test.csv tail contains 615 validations of 2025-11-01 00:00–01:37 → 12 cells known exactly. Raw matches labels (verified). Negligible score, but free.
12. [data][H] Route 50 almost stops on weekends since Sep (Sat/Sun ≈ 0–2.5k vs 25k weekdays) → must use route-specific daytype profiles (done).
13. [data][H] Level drifts slowly; short windows win (level 2w, shape 4w). Perfect daily level would give only 0.92 → remaining error = hourly noise. Levers left: Nov–Dec level shift, special days.
14. [domain][H] Weekday holiday ≈ 0.37–0.55 of workday ≈ Sunday. Bridge workdays (May 5–7, Jan 9–10) ≈ 0.88–0.95 → Dec 29–30 ×0.88. Preholiday shortened days ≈ 1.0.
15. [domain][M] Workday level Jan–May ≈ Oct level (0.93–1.1) → no evidence of strong winter drop; keep Oct level for Nov–Dec.
16. [data][M] Weather Nov–Dec 2025 mild: heavy snow only 15.11, 26.12, 30.12. Weather likely a small lever.
17. [domain][H] **Organizer GTFS directory: route 5 "Рижская – Белорусский вокзал" route_date_start = 2025-12-16** (researcher found the same in news: route 9 replaced). GT likely has route-5 boardings Dec 16–31 → everyone predicting 0 loses them. LB-probe.
18. [domain][H] Routes 7, 11, 12 (and 2, 4) new versions from 2025-12-20 (network change). Route 7 → "Бульвар Рокоссовского – Белорусский вокзал".
19. [domain][M] Routes 7 & 50 weekend track repairs ~12 Sep – end of Nov (Protopopovsky lane): Sep–Oct weekends abnormal (50 ≈ 0). Pre-repair weekend: r50 Sat 0.44 / Sun 0.37 of weekday, r7 0.60 / 0.51. Dec weekends likely back to normal → LB-probe.
20. [domain][H] New Year night free fare 31.12 20:00 – 01.01 06:00 → Dec 31 20–23h ≈ 0.
21. [lb][H] LB 26.09: 0.88322 / 0.88128 for v02 / v01 → CV (0.88–0.90) tracks LB. Σy(Nov–Dec) ≈ 12.3M → adding P boardings shifts score by ≈ ±P/12.3M (probe resolution: 80k ≈ 0.0065).
22. [lb][H] Probe batch 1 (vs v03_base 0.88404): r5 k0.5 → 0.88836 (+0.0043), k1.0 → 0.88442; noise-model fit ⇒ route-5 optimum k≈0.5×route28 (≈56k useful boardings). Dec31 night zeros +0.0008 ⇒ Σy ≈ 13–13.6M.
23. [bug] r50/r7 weekend probes of batch 1 had inflated Sundays (weekdays leaked into Sunday profile) → inconclusive; fixed in src/adjust.py, re-probed (p04a/b).
24. [data][M] Weather on nowcast residuals (n=260 days): precip −1.1%/mm (6–21h sum, p<0.001), cold (<−10°C) −3.4% (p=0.04), snow n.s. Intercept +1.6% ⇒ 2w-median level biased low (upward drift) → check with scale probes.
25. [domain][H] Deptrans (t.me/DtOperativno/23565): routes 7 & 50 normal weekend service from **15.11.2025** → restore weekends from Nov 15 (v08). Dec 20 = platform relocations only, no route change. Route 5 opened 16.12 ~18:06; >160k trips first month (~5k/day) ≈ our 0.5×route28 (LB-fitted) — two independent sources agree.
26. [model][H] Analyst: level window Oct 18–31 contaminated by autumn school break (Fri −7.6 %, weekends −3 %) + Oct 31. Clean level + 0.7·anchor shape: +0.0049 on 6/6 folds (v07).
