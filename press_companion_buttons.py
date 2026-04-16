import os
import requests
from dotenv import load_dotenv

load_dotenv()

COMPANION = os.environ.get("COMPANION_URL", "").rstrip("/")

if not COMPANION:
    raise RuntimeError("COMPANION_URL is not set in the environment")

def press(page, row, col):
    requests.post(f"{COMPANION}/api/location/{page}/{row}/{col}/press")

def trigger_changeover_rec():
    press(15, 3, 2)

def trigger_wide_rec():
    press(15, 3, 4)
