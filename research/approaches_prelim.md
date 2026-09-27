# Preliminary approaches (before seeing data)

## ML (ranked by expected value / cost)
A. **Seasonal profile baseline** — level(route) × shape(route, daytype, hour); daytype = weekday/Sat/Sun/holiday. Minutes to build, fully explainable. First submission.
B. **Profile × multipliers** — A + trend (monthly level extrapolation, Sep–Oct anchor) + holiday/pre-holiday + weather (temp, precip, snow) multipliers fit on history. Still explainable.
C. **LightGBM global model** on calendar + route/stop + weather + level features, NO short lags (direct multi-horizon). Target = log1p or ratio to profile. SHAP for explainability.
D. Blend B + C (weights tuned on Sep–Oct holdout). Likely winner on metric.
E. Optional: reconcile stop-level ↔ route-level sums (hierarchical consistency), year horizon via scenario (profile × seasonal index from Jan–Oct + trend).

Validation: train Jan–Aug → predict Sep–Oct (same 61-day shape as Nov–Dec). Then refit on Jan–Oct for final.
Caveat: Nov–Dec seasonality is unseen in data → external prior (Moscow transport seasonal ratios from open data / news) or weather-driven.

## Product (minimum that scores)
- Python FastAPI serving precomputed forecasts from Parquet/DuckDB in memory → easily hundreds of RPS, p95 << 100 ms on 2 vCPU.
- Frontend: single-page (React or lightweight) + MapLibre/Leaflet: stops on map, colored by load, time slider, route/stop/interval filters, CSV/XLSX export.
- docker-compose, README with load-test results (locust/k6: RPS, p95, CPU, RAM).
- "Explain" panel: forecast decomposition per hour (base × daytype × weather × trend) — business-friendly.
