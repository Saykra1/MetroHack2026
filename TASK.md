# Task — Moscow Transport Hackathon: AI forecast of tram route load

## Statement
Forecast hourly passenger flow (validations) for Moscow tram routes. Plus a web service (backend+frontend, Docker)
with REST API, map dashboard (stops on Moscow map), filters (route / stop / time interval), CSV/XLSX export.
Horizons: day (hourly), month; year = optional.

## Data (per organizer chat 25.09)
- train.csv = Jan–Aug 2025, test.csv = Sep–Oct 2025 (labeled? → verify; likely our holdout/validation).
- Forecast target period = **Nov–Dec 2025, full grid route × date × hour, 61 days**, no actuals given.
- "Route 5 has no targets" (participant report) → check.
- Dataset: https://disk.yandex.ru/d/DiFwlfMOauxjBg (dataset.zip with field descriptions).

## Deliverables & deadline — **27.09.2026 23:59 MSK**
1. CSV upload in "Data Science" section (auto-scored, best score over all time counts).
   Limits per day (reset 00:00 MSK): 36 attempts total, 24 successful.
2. Form in "Загрузка решения": links/text (repo, service, README). Last version counts.
- README MUST contain performance numbers (RPS, p95, CPU, RAM) — mandatory.

## Judging
- Metric: _pending (user will send)_. Chat hint: people ask "0.60+?" → score is probably in [0,1], higher=better.
- Final leaderboard = combined score over ALL criteria (ML + product), published 29.09 evening.
- Stack is NOT scored. Reproducibility not a separate criterion, but resource efficiency IS.

## NFR (for README/pitch)
1 container 2–4 vCPU / 2–4 GB RAM, hundreds of RPS, p95 < 200–300 ms, CPU 60–80%, no swap.
Horizontal scaling compatible. Clear API error messages. Extensible with external data (weather, traffic, construction, new routes).

## Open questions to organizers
- Exact metric & weights of criteria.
- Is test.csv labeled? What does the submission grid look like (sample_submission)?
- Route 5 without targets — predict 0 / exclude?
- External data (weather actuals for Nov–Dec 2025) allowed with a link? (Chat: yes, "with link".)

## Judging criteria (received 26.09) — total 29
1. WAPE-score ×2 weight: >0.88 → 10/10 (**reached: LB 0.90167**). Further WAPE gains = 0 points → stop spending LB.
2. Data & external sources (8): a) +1 per external source used AND confirmed by effect, with working link: traffic, weather, calendar/season, other events (≤4); b) domain of validity & adaptation described (≤2); c) UI correction coefficients with instant recompute (+1), correct target aggregation + reproducible ingest pipeline (+1).
3. Architecture & performance (5): modules ingest→features/geo→ML/aggregation→API→frontend; REST API by route/stop/interval/horizon; perf in README (honest); runnable service required.
4. Functionality (4): horizons day/month/year (month/year qualitative ok), aggregation route/stop/interval, map dashboard, CSV/XLSX export.
5. Business value (2): fleet allocation, overcrowding, schedule, realistic limits.
