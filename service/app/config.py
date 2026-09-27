"""Runtime configuration (env vars)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
HISTORY_PATH = Path(os.getenv("HISTORY_PATH", DATA_DIR / "history.csv"))
FORECAST_PATH = Path(os.getenv("FORECAST_PATH", DATA_DIR / "forecast.csv"))
EXPLAIN_PATH = Path(os.getenv("EXPLAIN_PATH", DATA_DIR / "explain.csv"))
STOPS_PATH = Path(os.getenv("STOPS_PATH", DATA_DIR / "stops.json"))
ROUTE_NAMES_PATH = Path(os.getenv("ROUTE_NAMES_PATH", DATA_DIR / "routes.json"))
PIPELINE_REPORT_PATH = Path(os.getenv("PIPELINE_REPORT_PATH", DATA_DIR / "pipeline_report.json"))
# Optional ML layer (experiments/ml, copied by scripts/prepare_data.py)
INTERVALS_PATH = Path(os.getenv("INTERVALS_PATH", DATA_DIR / "intervals.csv"))
ANOMALIES_PATH = Path(os.getenv("ANOMALIES_PATH", DATA_DIR / "anomalies.csv"))
HYBRID_PATH = Path(os.getenv("HYBRID_PATH", DATA_DIR / "hybrid_nov_dec.csv"))
HYBRID_FOLDS_PATH = Path(os.getenv("HYBRID_FOLDS_PATH", DATA_DIR / "hybrid_folds.csv"))
MODEL_REPORT_PATH = Path(os.getenv("MODEL_REPORT_PATH", DATA_DIR / "model_report.md"))
STATIC_DIR = BASE_DIR / "static"

# Routes shown in the service (the hackathon's 10 tram routes; route 5 has geometry but no counts).
TRACKED_ROUTES = [r.strip() for r in os.getenv("TRACKED_ROUTES", "1,5,7,11,12,17,25,26,28,50").split(",") if r.strip()]
CACHE_SIZE = int(os.getenv("CACHE_SIZE", "4096"))
