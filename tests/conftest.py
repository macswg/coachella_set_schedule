import os

# Force the in-memory mock store for all tests, regardless of .env settings.
# These must be set before any app module is imported so that config.py reads them
# before load_dotenv() runs (load_dotenv skips vars already in os.environ).
os.environ["USE_GOOGLE_SHEETS"] = "false"
os.environ.setdefault("DATA_BACKEND", "memory")
