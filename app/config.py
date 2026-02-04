import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Google Sheets configuration (for future integration)
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        str(Path.home() / ".config" / "gcloud" / "service-account.json")
    )

    # App configuration
    STAGE_NAME: str = os.getenv("STAGE_NAME", "Main Stage")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Los_Angeles")

    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()
