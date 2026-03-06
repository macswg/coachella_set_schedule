import os

# Force the in-memory mock store for all tests, regardless of .env settings.
# This must be set before any app module is imported so that config.py reads it
# before load_dotenv() runs (load_dotenv skips vars already in os.environ).
os.environ["USE_GOOGLE_SHEETS"] = "false"
