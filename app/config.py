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

    # Art-Net configuration
    ARTNET_ENABLED: bool = os.getenv("ARTNET_ENABLED", "false").lower() == "true"
    ARTNET_PORT: int = int(os.getenv("ARTNET_PORT", "6454"))
    ARTNET_UNIVERSE: int = int(os.getenv("ARTNET_UNIVERSE", "0"))
    ARTNET_CHANNEL_HIGH: int = int(os.getenv("ARTNET_CHANNEL_HIGH", "1"))
    ARTNET_CHANNEL_LOW: int = int(os.getenv("ARTNET_CHANNEL_LOW", "2"))


settings = Settings()
