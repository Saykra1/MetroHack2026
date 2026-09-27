# Agent brief (read first)
Task: forecast hourly boardings for Moscow tram routes 1,5,7,11,12,17,25,26,28,50 for 2025-11-01..2025-12-31 (14,640 cells). Metric WAPE-score = 1 − Σ|y−ŷ|/Σy (higher better). Deadline 2026-09-27 23:59 MSK. Leaderboard (LB) attempts are shared by the whole team and scarce — every probe must be justified.
History: labels/labels_day_{train,test}.csv (route;date;hour;boardings, Jan–Oct 2025). Helpers: src/common.py (load_labels, full_grid, wape_score), src/model_ls.py (level×shape), src/build_submission.py, src/adjust.py (rules), src/make_final.py. Calendar/weather: research/calendar_2025.csv, research/weather_moscow_2025.csv. Events: research/external_events.md. Organizer GTFS directory: spravochniki/ (route_date_start: route 5 = 2025-12-16, routes 7/11/12/2/4 = 2025-12-20, routes 1/3/6/10 = 2025-10-11).

## Current best: LB 0.89480 = submissions/v06_best_r50_r7.csv
pred = Level(2-week median daily total, route × {Mon–Thu, Fri, Sat, Sun/holiday}) × Shape(4-week hourly share) × special days (Nov1 ×0.8 Fri-type; Nov 3–4 Sunday-type; Dec29–30 ×0.88; Dec31 Sat-type ×0.8, 20–23h = 0) + route 5 from Dec16 = 0.5 × route-28 profile + routes 50 & 7 December weekends restored to pre-repair normal (Sat/Sun ratios to weekday: r50 0.44/0.37, r7 0.60/0.51, scaled to Oct weekday level). Total predicted ≈ 12.47M; Σy ≈ 13–13.6M (estimated).

## LB history (each probe changed ONE thing)
v01 profile 0.88128 | v02 level×shape+calendar 0.88322 | v03_base (+NY night zeros) 0.88404 | +route5 k0.5 0.88836 | +route5 k1.0 0.88442 | +r50 Dec weekends (buggy, Sundays ~2.4× too high) 0.88405 | +r7 Dec weekends (buggy) 0.88312 | v06 = v04_best + r50 & r7 Dec weekends fixed (+110k) 0.89480.
Implication: adding P boardings to cells shifts score by ≈ (useful − harmful)/Σy; 100k ≈ 0.0075.

## Backtests (offline, 5 folds): level×shape ≈0.886 mean (Oct fold 0.904). LightGBM correction worse (−0.01..−0.04). Trend extrapolation worse. Perfect daily level → 0.92 ceiling (rest is hourly noise).
## Offline weather regression (nowcast residuals, 260 days): precip −1.1%/mm (p<0.001), cold<−10°C −3.4%, intercept +1.6% (level from 2-week median biased low).
## Untested hypotheses / open levers
- Nov/Dec overall level vs Oct (seasonality, intercept +1.6%, T1 line opened Nov 12–13 may cannibalise).
- Nov weekends for routes 50/7 (repairs "until end of autumn" — maybe ended earlier).
- Network change 2025-12-20 for routes 7, 11, 12 (route 7 → "Бульвар Рокоссовского – Белорусский вокзал").
- Route 5 profile/ramp-up; late-December (27–31) behaviour; seasonal change of hourly shape (dark evenings, winter).
