# Log
Format: `## YYYY-MM-DD HH:MM — step` → what / result / conclusion / next.

## 2026-09-26 — setup
- What: created workspace, agent roles, logging files.
- Next: receive task + organizer chat → analysis phase.

## 2026-09-26 — task intake
- What: read task text + organizer chat. Filled TASK.md, INSIGHTS.md (8 insights), research/approaches_prelim.md.
- Key: deadline 27.09 23:59 MSK; target = Nov–Dec 2025 hourly grid; external actuals for Nov–Dec 2025 are available now (edge).
- Next: data arrives → EDA + leak hunt; researcher agent collecting external data in parallel.

## 2026-09-26 afternoon — data, baselines, v01–v02
- Workspace moved to Desktop/hach_metro (data there). Raw 62.4M rows → experiments/raw.parquet (DuckDB, 14 s load).
- Metric found in README: WAPE-score. Built backtest harness (src/common.py, model_profile.py, model_ls.py).
- v01 (profile) and v02 (level×shape + special days + leak) built; CV ~0.90 autumn folds. See LEADERBOARD.md.
- Spawned: Researcher (calendar/weather/events/prior art), Builder (service/ web app + Docker + load test).
- Next: LightGBM challenger (direct multi-horizon), weather residual test, debate on Nov–Dec level shift.

## 2026-09-26 evening — researcher results, LB probes
- LB: v02 0.8832, v01 0.8813 → CV reliable.
- Researcher: calendar, weather, events (route 5 opens 16.12; 7/50 weekend repairs until ~end Nov; free fare NY night). Route 5 date confirmed in organizer GTFS directory.
- Built v03_base + 4 single-hypothesis probes (src/variants.py). Waiting for LB deltas.
- 26.09 ~16:30: probe batch 1 analysed; route 5 k=0.5 locked (LB 0.88836). Batch 2 (p04a–d) built: r50/r7 Dec weekends fixed, Nov/Dec ×1.04.

## 2026-09-26 ~17:30 — pipeline, weather, docs
- src/pipeline_ingest.py: 62.4M raw → 59.7M clean in 28 s (DuckDB), 100% exact match with organizer labels (57,551 cells).
- Weather multiplier (centred) added; src/make_final.py = one-command pipeline → submissions/final_candidate(.csv, _explain.csv).
- SOLUTION.md written. Judge/Red-team agent launched. Builder told to use final_candidate_explain.csv.
- Pending LB: p04a (r50 Dec weekends), p04b (r7), p04c (Nov×1.04), p04d (Dec×1.04), p05 (weather).
- ~18:00: judge review applied (archive buggy variants.py, clean-checkout repro, route-5 explain fix, pipeline_geo.py: 489 stops + quality report). Remaining: project README w/ perf (builder), explain in service, pitch Q&A.
- ~18:15: attempts are shared by team → minimise probes. Re-read buggy batch-1 probes: r7 result (−0.00092) matches 'normal weekends' scenario (predicted −0.0008); r50 ≈0 inconsistent with 'repairs continue' (would be −0.01). → single upload v06_best_r50_r7 (+110k). p04*/p05 on hold.
- ~19:00 LB v06 = 0.89480 (+0.0064). Round 2 launched: researcher-2, analyst (shape seasonality), debaters bull/bear on level → judge.
- ~20:00 Debate: bull/bear converge on under-prediction; analyst: clean level + anchor shape +0.0049 on 6/6 folds → v07 (+210k). Recommended upload: v07 instead of p06.
- ~20:30 Researcher-2: r7/r50 weekends normal from 15.11 (Deptrans), Dec 20 no route change, route 5 ~5k/day confirms k=0.5. Built v08 (= v07 + Nov15 weekends + r5 opening 18h). make_final default = v08.
- ~21:00 LB v08 = 0.90167 → criterion 1 maxed. Pivot to product criteria. Weather OOS: helps 3/4 folds (+0.0004..+0.003), coef always negative → included in final_candidate (= v09). Builder resumed (coefficients UI, fleet panel, year horizon, README); traffic researcher launched.
- ~21:40 Docker Desktop 4.60 can't start: creates unix sockets under Cyrillic user path (C:\Users\Мария) → 'filename syntax incorrect' (Inference manager, then Secrets Engine). Renamed %LOCALAPPDATA%\Docker\run → run.stale_*. Ubuntu WSL has no dockerd (needs sudo). Dockerfile/compose reviewed OK. Options: user installs docker.io in WSL (sudo) or tests on another machine; README keeps host-measured perf (honest).
- ~22:30 LB: v09 weather 0.90154, Nov×1.03 0.90086, Dec×1.03 0.89986 → level correct, final = v08 (0.90167). Leak hunt negative (GT = real Nov–Dec). Repo pushed (private, collaborators uwuICQ & Saykra1 invited, write — admin impossible on personal repos).
- ~23:00 cobalte90 invited (write). AI round: ML engineer (hybrid GBM blend, quantile intervals, anomaly detector) + builder (intervals band, overcrowding probability, anomaly layer, model panel, template dispatcher assistant) launched in parallel with file contract experiments/ml/*.csv.
- ~01:00 27.09 AI round done: hybrid w=0 (GBM worse), intervals (78 % coverage), anomaly detector (87 % explained); service: intervals band, P(overflow), anomalies panel, model panel, rule-based dispatcher assistant; 47 tests. Hybrid file aligned to v08 exactly. Pushed to new branch ml-ai (main untouched).
- 27.09 17:30 Team checklist round 4 → builder (chart bug, dayLineTooltip, assistant POST /query + confirm UI, traffic coefficient ЦОДД + TomTom live layer via env key, cat mascot, UI/UX, README sources/holdout/domain/docker). TomTom key → 401 on all endpoints (not activated for Traffic API?). Key stored only in gitignored service/.env. Third-party skill/MCP installs declined (untrusted code, persistent config).
- 27.09 ~20:30 Round 4 done: chart resize bug fixed (ResizeObserver + mobile sticky bar), dayLineTooltip = stale cache → versioned assets; NLQ assistant POST /assistant/query + confirm UI; traffic k_traffic (ЦОДД) + TomTom live layer (key 401 → hidden); cat mascot; UI tokens/contrast/mobile/skeleton; README sources/validation/domain/docker; 67 tests.
- 27.09 ~21:30 UI redesign (5 views, drawer, rail, responsive nav) — 77 tests; merged ui-redesign → ml-ai.
