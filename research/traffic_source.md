# External source: road congestion in Moscow (ЦОДД score, 2025)

## Source
- **What:** official posts of the Moscow Transport Department / ЦОДД in the public Telegram channel **«Дептранс. Оперативно»**: https://t.me/DtOperativno (web preview without login: https://t.me/s/DtOperativno?before=<id>).
  Typical post: «По данным ЦОДД, загруженность дорог составляет 7 баллов… Средняя скорость движения — 22 км/ч». The score is a 0–10 road-load score (same scale as Яндекс Пробки).
- **How to get it:** `python experiments/traffic/scrape_dtoperativno.py` (about 35 s; pages ?before=19800…24520 cover 2024-12-23…2026-01-09, 4,550 posts), then `python experiments/traffic/build_traffic.py`.
  Every row has a permalink (`https://t.me/DtOperativno/<id>`) so each value can be checked.
- **Files:** `research/traffic_moscow_2025.csv` has one row per post (date, hour MSK, score, speed_kmh, source_url; 341 rows). `research/traffic_moscow_2025_daily.csv` has one row per day (max_score, min_speed, n_posts, reported, first_hour).
- **Sources that did not work:** TomTom Traffic Index shows 404 for Moscow (Russian cities were removed). trafficindex.org (Google-based) needs a paid subscription. data.mos.ru / apidata.mos.ru cannot be reached from this machine (connection timeout). Yandex has no public history (smotra.ru is archive-only since 2021, and the Wayback Machine has only about 20 days). mskagency/РБК news covers only extreme days.

## Coverage and caveats
- 2025: 152 days have a post and 150 have a score. Posts come almost only on **working days** (Fri 85%, Mon–Thu about 55%, Sat 6%, Sun 0%). Posts are sparse in Jan–Feb (2 and 6 days) and dense in Nov–Dec (18 and 22 days).
- Posts are **event-driven**: ЦОДД posts when traffic is heavy, and also posts routine Friday "short day" notes at about 4 points. A day with no post is treated as a "normal day (≈4)".
- Score distribution for the daily max: 3–4 points on 47 days, 5–6 on 34, 7 on 60, 8–9 on 8.
- It is a nowcast, not a forecast. For the test period (Nov–Dec 2025) the real posts already exist: 35 working days had a score of 7 or more (list in `traffic_oos.py` output).

## Method (`experiments/traffic/traffic_effect.py`)
- Nowcast residuals: for each weekly origin o = 2025-02-03…2025-10-27 we ran `model_ls.forecast(hist, fut, 2, 4, 'wk4', 'median', 'sum')` for the next 7 days (route 5 excluded). We summed the forecast to daily totals and took lr = log(actual/pred).
- Sample: working days only (no day-offs, no pre-holiday days, |lr| < 0.4), n = 185.
- OLS with HC1 standard errors. Controls: precipitation 6–21h (mm), cold day (T < −10 °C), Friday.

## Effect table (daily)
| spec | n | coef | p | meaning |
|---|---|---|---|---|
| A heavy day (score ≥ 7) flag + controls | 185 | **+0.0198** | **0.039** | +2.0% tram boardings on heavy-traffic days |
| A0 same, no controls | 185 | +0.0173 | 0.10 | |
| B score anomaly vs weekday mean (per point) | 185 | +0.0048 | 0.089 | |
| C score − rolling 3-week mean (per point) | 181 | **+0.0070** | **0.025** | +0.7% per point above recent norm |
| D score, reported days only (per point) | 103 | +0.0058 | 0.060 | |
| E any ЦОДД post that day | 185 | +0.0130 | 0.11 | |
| F heavy flag, Mon–Thu only | 151 | **+0.0236** | **0.034** | |
| G min avg speed, km/h | 56 | +0.0004 | 0.64 | n.s. (few days) |

Precipitation stays significant in every spec (≈ −0.75%/mm, p < 0.001). Heavy days are somewhat wetter (1.9 vs 1.5 mm), so the traffic effect remains **net of weather**.

## Hourly
| spec | n | coef | p |
|---|---|---|---|
| H1 evening (17–20h) residual minus day residual ~ heavy | 185 | **−0.0158** | **0.003** |
| H2 evening residual ~ heavy | 185 | +0.0040 | 0.69 |
| H3 morning (7–10h) residual ~ heavy | 185 | **+0.0264** | **0.019** |
| H4 hour of a ≥ 7 post (+1h) vs the same hour on other days, 15–21h, hour fixed effects | 1295 | **−0.0259** | **<0.001** |

**Interpretation.** Heavy-congestion working days are high-demand days overall. Tram use rises by about 2% for the day and about 2.6% in the morning peak, which fits people switching from cars and general high city activity. However, **in the jam hours themselves** tram boardings are about 2.6% below the model. Trams share the road and signals with cars, so service slows (fewer runs, bunching) and some trips move to the metro. The two effects roughly cancel in the evening peak. Direction: congestion → more tram use over the day, but lower tram throughput during the jam.

## Out-of-sample (`experiments/traffic/traffic_oos.py`, hourly WAPE, coefficient fitted before the fold)
| fold | heavy days | base | + day multiplier | + day & alert-hour −2.6% |
|---|---|---|---|---|
| Jul–Aug | 2 | 0.87745 | 0.87774 | 0.87763 |
| Sep–Oct | 18 | 0.90297 | 0.90306 | **0.90340** |
| Oct | 10 | 0.91544 | 0.91529 | **0.91550** |
The gain is small (+0.0001…+0.0004) but has the right sign in 2 of 3 folds for the full rule.

## How it would be used
- **Model:** multiplier on a heavy working day = exp(+0.02) on the day level, then ×exp(−0.026) in the post hour and the next hour (usually 17–20h). A softer variant uses +0.7% per point of score above the 3-week norm.
- **Caveat for Nov–Dec:** almost every weekday in Nov–Dec is "heavy" (35 days), so a fixed ≥ 7 flag becomes seasonal rather than an anomaly. Use the relative form (spec C) or only the alert-hour dip. Expected LB effect is about +0.0003 at most. It is a **confirmed external factor, not a big lever**.
- **UI:** a "road congestion" scenario slider (score 0–10). It shifts the day level by +0.7%/point above normal and applies a dip in the jam hours. Show the ЦОДД post link as evidence.

## Limitations
The data is sparse and event-driven (not a continuous series). No weekends are covered. Hourly timing is the post time, not a measured congestion curve. Selection bias remains possible (ЦОДД posts on unusual days that are also unusual for other reasons, such as the start of the school season or events). Effects are 1–3%, similar in size to the noise. A continuous Yandex/ЦОДД hourly series (data.mos.ru, ЦОДД) would be better but could not be reached.
