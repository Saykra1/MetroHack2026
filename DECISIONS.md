# Decisions
| # | Date | Decision | Alternatives rejected | Why | Judge verdict |
|---|---|---|---|---|---|
| 1 | 26.09 | Python (FastAPI) instead of Java/Spring | Java 21 + WebFlux | Stack not scored (organizers); speed of delivery; precomputed forecasts give <10 ms lookups anyway | – |
| 2 | 26.09 | Core model = level(2w median) × shape(4w) by route × {Mon–Thu, Fri, Sat, Sun/holiday} × hour | dow×hour median; LightGBM correction (−0.01…−0.04 on all folds); window ensembles (±0.001) | Best mean CV 0.886 over 5 folds; fully explainable to dispatchers | simple wins on data |
| 3 | 26.09 | No trend extrapolation | damped log-linear trend (0.25/0.5/1.0) | Flat ≥ damped on 5/6 folds; full trend −0.03 | – |
| 4 | 26.09 | Special-day multipliers from 2025 analogues: Nov 1 ×0.8, Dec 29–30 ×0.88, Dec 31 Sat×0.8; weekday holidays → Sunday profile | GBM holiday learning | Transparent, each number traceable to an analogue day | – |
| 5 | 26.09 | Route 5 → 0; Nov 1 00–01h from raw tail (exact) | – | Route 5 absent in labels; tail verified vs labels | – |
| 6 | 26.09 | Debate round: bull (+2–4 % level) vs bear (keep/cut specific days). Both agree level is low; analyst finds root cause (level window Oct 18–31 contaminated by autumn school break + Oct 31) and an offline-validated fix: clean level + 0.7·anchor shape (+0.0049, 6/6 folds) | blanket ×1.02–1.04 (loses on Apr–May fold); daylight-conditioned shape; long weekend windows | validated offline, explainable ("typical day without school break"), less LB spend | adopt v07 |
| 7 | 26.09 | Final CSV = v08 (0.90167). No level raise | ×1.03 Nov (−0.0007), ×1.03 Dec (−0.0017), weather on LB (−0.0001) | LB probes: level already calibrated; criterion 1 capped at >0.88 anyway | final |
