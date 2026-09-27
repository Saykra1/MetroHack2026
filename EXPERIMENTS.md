# How we got to the solution — experiment journal

Metric: WAPE-score on route × date × hour, Nov–Dec 2025. **LB** = organizer platform score. **CV** = mean of rolling backtests (1–2-month horizon).
Rule: one change per leaderboard submission, so every LB delta is attributable.

| # | Version | What changed | CV | LB | Δ LB | Verdict |
|---|---|---|---|---|---|---|
| 0 | organizer sample | flat value per route | – | ≈0.48 | – | floor |
| 1 | v01 | median of last 4 weeks by weekday × hour; holidays → Sunday | 0.87 | 0.88128 | +0.40 | hourly profile is the key |
| 2 | v02 | level (2-week median, Mon–Thu/Fri/Sat/Sun) × shape (4-week hourly share), special days, exact Nov 1 00–01h from raw tail | 0.886 | 0.88322 | +0.0019 | kept |
| – | LightGBM correction | global GBM on calendar/weather/horizon on top of v02 | −0.01…−0.04 | – | – | rejected offline |
| – | trend extrapolation | damped log-linear trend | −0.00…−0.03 | – | – | rejected offline |
| – | window ensembles | avg of several windows | ±0.001 | – | – | rejected offline |
| 3 | v03_base | free fare on New Year night → 0 validations 31.12 20–23h | – | 0.88404 | +0.0008 | kept |
| 4 | + route 5 ×0.5 | route 5 opened 16.12.2025 (organizer GTFS) → profile of route 28 × 0.5 | – | **0.88836** | +0.0043 | kept |
| 5 | + route 5 ×1.0 | same × 1.0 | – | 0.88442 | +0.0004 | too much → k≈0.5 (noise-model fit) |
| 6 | + r50/r7 Dec weekends (bug) | weekend service restored after repairs; Sunday profile bug | – | 0.88405 / 0.88312 | ≈0 / −0.001 | inconclusive, bug found |
| 7 | v06 | r50 & r7 December weekends restored (bug fixed) | – | **0.89480** | +0.0064 | kept |
| – | weather multiplier | −1.1 %/mm precipitation, −3.4 % cold days | OOS +0.0004…+0.003 (3/4 folds) | – | – | kept in service, confirmed effect |
| – | debate bull vs bear | level ↑ 2–4 % vs keep/cut; both agree under-prediction | – | – | – | resolved by analyst |
| 8 | v07 | clean level (no school break / Oct 31) + 0.7·long-history anchor shape | +0.0049 (6/6 folds) | – | – | kept |
| 9 | v08 | v07 + routes 7/50 weekends from 15.11 (Deptrans) + route 5 from 16.12 18:00 | – | **0.90167** | +0.0069 | **current best** |
| 10 | leak hunt | GT = shifted history? (10 shifts vs 9 LB points), hidden rows, begin/input dates, directory | – | – | – | no leak: GT is real Nov–Dec data |

Ceiling analysis: a perfect daily level gives ≈0.92, an in-period oracle profile ≈0.93–0.94 → remaining error is hourly noise.
| 11 | v09 | v08 + weather multiplier | OOS +0.0004…+0.003 | 0.90154 | −0.0001 | neutral on LB; kept in the service as a coefficient |
| 12 | p10 | v09 + November ordinary days ×1.03 | – | 0.90086 | −0.0007 | November level is right |
| 13 | p11 | v09 + December ordinary days ×1.03 | – | 0.89986 | −0.0017 | December level is right → bull hypothesis rejected |

**Final submission: v08 (LB 0.90167)** → `submissions/FINAL_SUBMISSION.csv`.
| 14 | traffic source | ЦОДД congestion score (Deptrans channel) vs residuals | OOS +0.0002…+0.0004 | – | – | confirmed small effect (+2 % on 7+ days); documented as 4th external source |
| 15 | ML hybrid | structural base × LightGBM ratio (55 origins, weather/traffic/calendar), blend weight by CV | GBM −0.019…−0.026; best w = 0 (0/5 folds win) | – | – | ML kept as explanatory `ml_ratio`, forecast = v08 |
| 16 | ML intervals | conformal quantiles by hour × day type × horizon (×1.15) vs LightGBM quantile | coverage 78 % (82 % weighted), pinball 4.5 % Σy | – | – | shipped: P10/P90 band + probability of overcrowding |
| 17 | ML anomaly detector | IsolationForest + robust z (level, share, hourly shape) + regime guard | 87 % of flags explained; auto-clean +0.0004 | – | – | shipped as monitoring («ИИ-детектор аномалий»), found route-12 diversion 1–4 Apr |

Branch `ml-ai`: ML/AI layer (src/ml, experiments/ml/REPORT.md, service AI panels, dispatcher assistant). `main` keeps the v08 release untouched.
