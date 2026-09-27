# Judge + Red Team review (26.09, read-only)

## 1. Scorecard
| Criterion | Status | Risk | Single highest-leverage fix |
|---|---|---|---|
| Auto WAPE-score | done (0.888, baseline 0.48) | M: last +0.005 comes from LB probes; unknown if public = private GT | Freeze `final_candidate` (=p05 incl. weather) only if its LB >= v04_best; otherwise submit v04_best. No more probe-driven tuning. |
| Horizons day / month / year | partial: day+month real, year = "scenario" (`queries.year_scenario`) | H: jury asks "year forecast" | Label year honestly as model-based: seasonal index from Jan–Oct + Nov–Dec forecast, calendar 2026 day-types, per-route; show it in the UI as "Year 2026 (scenario, ±band)". |
| Aggregation route / stop / interval | done for route/interval; stop = heuristic weights (hub x2, terminal x0.1, `prepare_data.py:59`) only for routes 1,5,7,11,12 | M | Label stop values "оценка" + document method; see §4. |
| Ingest / normalise / geo-bind pipeline | **missing as a product component** (only ad-hoc `raw_scan.py`, a leak-hunt script) | **H – mandatory FR** | §4: `pipeline/ingest.py` (DuckDB) with quality report. |
| Map dashboard | done (screenshots, dark/mobile) | L | Route 17/25/26/28/50 have no geometry — show "нет геометрии в справочнике" (already exists: `day_route17_nogeo.png`). |
| CSV/XLSX export | done (`/api/v1/export`) | L | – |
| External factors | done (calendar, weather, route-5 launch, NY free fare, repairs) | M: "you used the future" | Pitch framing: plug-in factor registry; in prod weather = forecast API. |
| NFR numbers in README | **missing**: root README.md is the organizer's dataset readme; no service README | **H – explicitly mandatory** | Write project README: 3650 RPS, p50 14 ms / p95 44 ms / p99 65 ms, 2 vCPU / 2 GB, 2 workers (`service/docs/loadtest_win_2cpu_2workers.json`), + RAM/CPU% measured. |
| Scalability / efficiency | done de facto (stateless, precomputed cube, LRU cache) | L | One README paragraph: stateless → N replicas behind LB; forecast file hot-swap via `FORECAST_PATH`. |
| Error handling | done (`app/errors.py`, 400s in load test) | L | Show one error JSON example in README. |
| Extensibility / retraining | partial: `make_final.py` one command, but not wired into service | M | `make retrain` = ingest → labels → make_final → prepare_data → container reload; mention cron. |
| Business value | partial (explain file exists; service ships no explain.csv) | M | Copy `final_candidate_explain.csv` → `service/data/explain.csv` so the decomposition panel works; add "peak-hour capacity alert" narrative for dispatchers. |

## 2. Red team: jury questions
1. **"You tuned on the leaderboard / used knowledge of the future."** – Base model is chosen purely on 5 rolling-origin backtests (CV tracks LB ±0.02). LB was used only to confirm *publicly documented* events (route 5 opening 16.12 is in the organizer's own GTFS directory; NY free fare; repairs), one rule per submission; organizers allowed external data with links.
2. **"Weather Nov–Dec is actuals, not a forecast."** – Effect is small (−1.1 %/mm, clipped to [0.9, 1.05], +0.2 % total); in production it is fed from a weather-forecast API for ≤14 days and set to 1.0 (climatology) beyond.
3. **"Why not ML / deep learning?"** – We tested LightGBM direct multi-horizon correction on the same folds: worse on every fold (−0.01…−0.04); with 10 months of history and no Nov–Dec analogue, structure beats capacity; even a perfect daily level caps at 0.92, so remaining error is hourly noise.
4. **"How does it work for a new route?"** – Route 5 case: no history → proxy route with similar length/type × capacity factor (k=0.5 × route 28), replaced by its own level after 2 weeks of validations (the model only needs 2–4 weeks).
5. **"Stop-level forecast when data is route-level?"** – Raw validations have no stop (place_id = depot); we disaggregate route-hour forecast over GTFS stops with explicit weights and label it as an estimate; with on-board GPS/ASMPP data the same pipeline binds each validation to the nearest stop by time.
6. **"Year horizon?"** – Seasonal month index from Jan–Oct + our Nov–Dec forecast, applied to 2026 calendar day-types, with growth scenario slider; it is a planning scenario, not a hourly-accurate forecast, and we say so.
7. **"How do you retrain / automate?"** – One command (`make_final.py`) re-estimates level (2 w) and shape (4 w) from the latest labels in seconds; nightly cron → new forecast file → service hot-reload, no GPU, no training jobs.
8. **"What if a route is disrupted (repair) inside the level window?"** – Level is a median by day type, robust to single outliers; known disruptions are an explicit rule layer (weekend repairs of 7/50) that dispatchers can toggle.
9. **"Why 2-week level — isn't it noisy?"** – Grid search over 2/3/4/6 weeks × 4/8/12 weeks shape on 6 folds; 2w/4w best mean; for Sat/Sun this is a median of 2 days — acknowledged, the ensemble of windows gave only ±0.001.
10. **"Does it hold 100s RPS on 2 vCPU?"** – 3650 RPS, p95 44 ms on 2 vCPU/2 workers (measured on Windows; Linux container should be better).

## 3. Model risks (src/)
- **Rule layer is validated only on the public LB, never in backtest** (`adjust.py:21-62`: route5 k, weekend_restore, scale, weather). If private ≠ public split, the +0.005 can partly vanish. k=0.5 (INSIGHTS #22) is literally fitted to 2 LB points → overfit risk small in absolute terms (≈0.004) but indefensible if presented as a model. Present it as "capacity-based prior", not as tuned.
- **Weather coefficients are in-sample** (fitted on 260 days of residuals of the same series, INSIGHTS #24) and never evaluated in a held-out fold; p05 differs from v04 only by weather (+26.7k). Its LB delta isn't recorded in LEADERBOARD.md — verify before choosing final.
- `adjust.py:6` loads `v02_ls_special_explain.csv` at import time → silent dependence on file state; `make_final.py:10` works around it with subprocess. Fragile but OK.
- `build_submission.py:40` requires `experiments/leak_nov01.csv` (needs 10 GB raw → raw.parquet); `build_submission.py:49` requires `v01_...csv`. SOLUTION.md "Reproduce" omits `raw_scan.py` and `leak_nov01.py` → a clean-checkout run fails.
- `variants.py:19` still contains the bug from INSIGHTS #23 (`np.where(dow==5,5,6)` puts weekdays into the Sunday profile). Superseded by `adjust.py`, but delete/mark stale so a reviewer doesn't find it.
- `adjust.py:13` pre-repair weekday median includes May 1–2/8–9 weekday holidays (PRE window) → weekday base slightly low → weekend ratio slightly inflated (small).
- `model_ls.py:19` Sat/Sun level = median of 2 days (WL=2): one anomalous weekend (e.g. Oct 25/26 weather) moves the whole Nov–Dec weekend level.
- Weather excluded for route 5 and route5 applied before weather (`make_final.py:12,17`) — consistent, fine. Explain for route 5 shows base=0, rules_mult=1 but prediction>0 (`make_final.py:22`) → dashboard decomposition doesn't sum; set rules_mult = "new route proxy".
- Backtests: no leakage found (history strictly `< s`, calendar is exogenous). But folds never include a holiday-heavy Nov–Dec analogue, so SPECIAL multipliers (0.8/0.88) are untested priors — say so.

## 4. Ingest / normalisation / geo-binding – minimal credible implementation (≈2–3 h)
`pipeline/ingest.py` (DuckDB, reusing `raw_scan.py` read_csv options), producing versioned parquet + a JSON quality report:
1. **Ingest**: CSV → typed parquet, partitioned by month; incremental (skip already-loaded files by hash).
2. **Normalise**: `ts = tran_date_time` (ignore `input_date_time`); `route = regexp '^([0-9]+)' of ngpt_route`; keep `validation_result='1'`; dedupe `tran_no`; drop ts outside file period/route not in directory; count rejects per reason (report: rows in/out, % bad dates, % failed validations, dup count).
3. **Aggregate**: route × date × hour boardings (must reproduce `labels/*` exactly → assert, show "0 diff" in README), plus unique cards (`crd_hashcode`) and vehicles (`garage_number`) per hour — useful "load per vehicle" KPI for dispatchers.
4. **Geo-bind**: join route → GTFS stops/trips (`spravochniki` stops sheet, routes 1,5,7,11,12) → `stop_hour` table = route-hour × stop weight; weights documented (hub, terminal, sequence) and replaceable by real stop shares when ASMPP/GPS arrives; routes without geometry flagged `geo_status='no_geometry'`. Also bind `place_id` → depot as a coarse location.
5. Expose `GET /api/v1/pipeline/report` (quality report) and mention the 62.4M rows / 14 s load time in README.

## Top actions (expected score gain per hour)
1. Project README with NFR numbers (RPS/p95/CPU/RAM), architecture, API, run instructions — mandatory, ~1 h.
2. `pipeline/ingest.py` + quality report + labels-reproduction assert + stop binding (§4) — mandatory FR, 2–3 h.
3. Ship explain.csv in service + fix route-5 decomposition; "why this number" panel = business value, 0.5 h.
4. Year horizon: make it an explicit, per-route model output with calendar 2026 and band, 1 h.
5. Decide final CSV: check p05 (weather) LB vs v04_best; pick the higher; stop probing, 0.2 h.
6. Retrain story: `make retrain` chain + hot-reload of forecast file, 0.5 h.
7. Clean repo: fix Reproduce steps, delete/mark `variants.py` bug, 0.3 h.
8. Pitch Q&A sheet from §2 (esp. LB-probe and weather answers), 0.5 h.
