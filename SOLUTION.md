# Tram Load Forecast — Solution Overview

**Task:** hourly boardings (successful validations) for 10 Moscow tram routes, 2025-11-01 … 2025-12-31 (14,640 cells). Metric: WAPE-score = 1 − Σ|y−ŷ|/Σy.
**Result:** leaderboard **0.90167** (organizer baseline 0.48). Offline rolling backtests 0.85–0.91 track the leaderboard.

## 1. Model — explainable decomposition
```
prediction(route, date, hour) = Level(route, day type) × Shape(route, day type, hour)
                                × SpecialDay × Weather × Events
```
| Factor | Estimation | Business meaning |
|---|---|---|
| Level | median daily boardings of recent *clean* days (last 8 Mon–Thu, 2 Fri, 2 Sat, 2 Sun within 6 weeks; school breaks, holidays and Oct 31 excluded) per route and day type (Mon–Thu / Fri / Sat / Sun & holidays) | "how many people ride this route on a typical day now" |
| Shape | 0.3 × last-4-week hourly shares + 0.7 × long-history "anchor" shares (clean days, capped ±50 %) | "when they ride": morning/evening peaks per route |
| SpecialDay | production calendar 2025: holidays → Sunday profile; 1 Nov working Saturday = Friday ×0.8; 29–30 Dec ×0.88; 31 Dec Saturday-type ×0.8 | multipliers measured on 2025 analogue days |
| Weather | −1.1 % per mm of daytime precipitation (centred on the level window), −3.4 % on days < −10 °C | fitted on 260 days of residuals |
| Events | route 5 launched 16.12.2025 18:00 (profile of comparable route ×0.5 ≈ 5.5k/weekday); weekend track repairs on routes 7/50 until 14.11 (normal weekend profile from 15.11); free fare on New Year night 31.12 20:00–06:00 → 0 validations | Deptrans / organizer GTFS directory |

Every forecast cell is decomposed into these factors (`submissions/final_candidate_explain.csv`), shown in the dashboard and editable there (correction coefficients).

**Why not a black box.** A global LightGBM correction model was worse on every fold (−0.01…−0.04), trend extrapolation worse (up to −0.03), window ensembles ±0.001. With 10 months of history and no Nov–Dec analogue, a structural model generalises better and is auditable.
Error anatomy: even a perfect daily level gives ≈0.92 → the rest is hourly noise; the levers are level, calendar and events.

## 2. External sources (each: link → how used → confirmed effect)
| Source | Link / how to obtain | Used as | Confirmed effect |
|---|---|---|---|
| Weather (hourly temperature, precipitation, snowfall) | Open-Meteo archive API: `https://archive-api.open-meteo.com/v1/archive?latitude=55.7558&longitude=37.6173&start_date=2025-01-01&end_date=2025-12-31&hourly=temperature_2m,precipitation,snowfall&timezone=Europe/Moscow` → `research/weather_moscow_2025.csv` | Weather multiplier | In-sample: −1.1 %/mm (p<0.001), cold −3.4 % (p=0.04). **Out-of-sample** (coefficients fitted only on data before the fold): better on 3/4 folds (+0.0004…+0.003), coefficient negative in every fold (`experiments/weather_oos.py`) |
| Calendar & season | Production calendar 2025 — Government Decree №1335 of 04.10.2024 (consultant.ru / publication.pravo.gov.ru); Moscow school holidays (mos.ru) → `research/calendar_2025.csv` | Day types, holiday → Sunday profile, bridge days, school-break-free level | Calendar on/off: +0.047 on the May–June fold; removing school-break days from the level window: +0.0049 mean on 6/6 folds |
| Events, repairs, network changes | Deptrans operational channel `https://t.me/s/DtOperativno` (post 23565, 15.11.2025: routes 7/50 weekend service restored); organizer GTFS directory `spravochniki/` (route 5 `route_date_start = 2025-12-16`); transport.mos.ru (free New Year night) | Event rules | Leaderboard, one rule per submission: route 5 launch +0.0043, routes 7/50 weekends +0.0064, NY night +0.0008, Nov 15 weekends + clean level +0.0069 |
| Road traffic (ЦОДД 0–10 congestion score) | Deptrans channel `https://t.me/s/DtOperativno` (scraper `experiments/traffic/scrape_dtoperativno.py` → `research/traffic_moscow_2025.csv`, each row with post link) | Correction coefficient (congestion scenario) | Days with 7+ points: **+2.0 % tram boardings** (p=0.039, controlled for weather); +0.7 %/point above 3-week norm (p=0.025). Out-of-sample: Sep–Oct +0.0004, Oct +0.0004, Jul–Aug +0.0002. Limits: event-driven posts, working days only (`research/traffic_source.md`) |

## 3. Domain of validity and adaptation
**Valid for:** the 10 routes present in the validation data (1, 7, 11, 12, 17, 25, 26, 28, 50 + new route 5 via proxy), hourly to monthly horizons up to ~2 months ahead, regimes similar to the last clean weeks (school term). Backtest accuracy: 0.90–0.91 for 1-month, 0.85–0.90 for 2-month horizons; weakest after regime breaks (summer → September: 0.81).
**Not valid / needs input:**
- regime breaks not in history (network reform, long closures, new lines) → must be entered as event multipliers (UI) or re-estimated after 2 weeks of new data;
- new routes → proxy profile of a similar route (shared stops, length) × expected volume, corrected as soon as 2 weeks of validations exist;
- year horizon → scenario only (seasonal index from 10 months of 2025, no full-year history); needs ≥ 1 full year for a statistical seasonal component;
- stop-level values → estimate (route forecast × stop weight): validations carry no stop id; real stop weights need APC/door counters or tap-on location.
**Adaptation:** re-run `pipeline_ingest.py` → `make_final.py` on new data (≈1 min); level/shape auto-update from the latest clean weeks; weather multiplier needs only a forecast feed (Open-Meteo forecast API); events are declarative rules.

## 4. Data pipeline (ingest → normalise → geo-bind)
| Step | Script | Result |
|---|---|---|
| Ingest + normalise raw CSV (10 GB, 62.4M rows) | `src/pipeline_ingest.py` (DuckDB) | 59.7M successful validations in **28 s**; hourly route aggregates **match organizer labels 100 %** (57,551 cells, diff 0) |
| Quality report | `src/pipeline_geo.py` → `experiments/pipeline_report.json` | 2.78M failed validations dropped; 21k rows with future `input_date_time` flagged (`tran_date_time` used) |
| Geo-binding | `src/pipeline_geo.py` → `experiments/route_stops.csv` | stops with coordinates for routes 1, 5, 7, 11, 12 (GTFS directory); stop load = route forecast × documented stop weight |

## 5. Validation
Rolling-origin backtests (1–2-month horizon): Oct, Sep 15–Oct, Feb–Mar, Mar–Apr, Apr–May, Sep–Oct (`LEADERBOARD.md`). External-fact rules (events) cannot be backtested — they were confirmed with single-rule leaderboard submissions and independent sources (e.g. route 5: leaderboard-fitted ≈5.5k/weekday vs Deptrans "160k trips in the first month").

## 6. Reproduce
```
pip install pandas numpy duckdb openpyxl statsmodels
python src/pipeline_ingest.py              # raw CSV → hourly aggregates + check vs labels
python src/pipeline_geo.py                 # stops + quality report
python src/make_final.py --name final      # → submissions/final.csv + final_explain.csv
cd service && python scripts/prepare_data.py && docker compose up --build   # web service
```
Code map: `src/common.py` (data, metric) · `model_ls.py` (level×shape) · `build_submission.py` (calendar, special days) · `adjust.py` (clean level/anchor shape, events, weather) · `make_final.py` (pipeline) · `service/` (API + dashboard).
