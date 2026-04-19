import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

_version_file = Path(__file__).parent.parent / "VERSION"
APP_VERSION = _version_file.read_text().strip() if _version_file.exists() else "unknown"


class Settings:
    """Application settings loaded from environment variables."""

    # Data backend selection: "sheets" | "sqlite" | "memory"
    # Falls back to interpreting legacy USE_GOOGLE_SHEETS when DATA_BACKEND is unset.
    DATA_BACKEND: str = (
        os.getenv("DATA_BACKEND")
        or ("sheets" if os.getenv("USE_GOOGLE_SHEETS", "false").lower() == "true" else "memory")
    ).lower()

    # SQLite database file path (used when DATA_BACKEND=sqlite)
    SQLITE_PATH: str = os.getenv("SQLITE_PATH", "./data/schedule.db")

    # Retention: how many archived shows to keep before the oldest are purged.
    ARCHIVE_RETENTION_COUNT: int = int(os.getenv("ARCHIVE_RETENTION_COUNT", "20"))

    # Google Sheets configuration
    USE_GOOGLE_SHEETS: bool = os.getenv("USE_GOOGLE_SHEETS", "false").lower() == "true"
    GOOGLE_SHEETS_ID: str = os.getenv("GOOGLE_SHEETS_ID", "")
    GOOGLE_SHEET_TAB: str = os.getenv("GOOGLE_SHEET_TAB", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE",
        str(Path.home() / ".config" / "gcloud" / "service-account.json")
    )

    # App configuration
    STAGE_NAME: str = os.getenv("STAGE_NAME", "Main Stage")
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Los_Angeles")

    # Multi-show tab list (comma-separated). Leave empty for single-show mode.
    SHOW_TABS: list[str] = [t.strip() for t in os.getenv("SHOW_TABS", "").split(",") if t.strip()]

    # Server configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Recording trigger configuration
    RECORDING_ENABLED: bool = os.getenv("RECORDING_ENABLED", "false").lower() == "true"
    RECORDING_PRE_START_MINUTES: int = int(os.getenv("RECORDING_PRE_START_MINUTES", "5"))
    RECORDING_ACT_PREFIX: str = os.getenv("RECORDING_ACT_PREFIX", "")

    # Ki Pro recorder configuration
    KIPRO_IP: str = os.getenv("KIPRO_IP", "")

    # ntfy.sh push notifications
    NTFY_URL: str = os.getenv("NTFY_URL", "")

    # Bitfocus Companion HTTP API
    COMPANION_URL: str = os.getenv("COMPANION_URL", "").rstrip("/")

    # WeatherLink weather data (optional)
    WEATHER_URL: str = os.getenv("WEATHER_URL", "")

    # Edit page password (HTTP Basic Auth). Leave empty to disable auth.
    EDIT_PASSWORD: str = os.getenv("EDIT_PASSWORD", "")

    # Public URL used for QR code (e.g. Cloudflare tunnel domain). Falls back to window.location.origin if empty.
    PUBLIC_URL: str = os.getenv("PUBLIC_URL", "")

    # Startup hard-reload (opt-in; suppresses in dev by setting to false)
    AUTO_RELOAD_ON_STARTUP: bool = os.getenv("AUTO_RELOAD_ON_STARTUP", "false").lower() == "true"
    STARTUP_RELOAD_DELAY: int = int(os.getenv("STARTUP_RELOAD_DELAY", "15"))

    # Art-Net configuration
    ARTNET_ENABLED: bool = os.getenv("ARTNET_ENABLED", "false").lower() == "true"
    ARTNET_PORT: int = int(os.getenv("ARTNET_PORT", "6454"))
    ARTNET_UNIVERSE: int = int(os.getenv("ARTNET_UNIVERSE", "0"))
    ARTNET_MAX_NITS: int = int(os.getenv("ARTNET_MAX_NITS", "11000"))
    ARTNET_BIT_DEPTH: int = int(os.getenv("ARTNET_BIT_DEPTH", "16"))
    ARTNET_CHANNEL: int = int(os.getenv("ARTNET_CHANNEL", "1"))
    ARTNET_CHANNEL_HIGH: int = int(os.getenv("ARTNET_CHANNEL_HIGH", "1"))
    ARTNET_CHANNEL_LOW: int = int(os.getenv("ARTNET_CHANNEL_LOW", "2"))
    ARTNET_MAX_VALUE: int = int(os.getenv("ARTNET_MAX_VALUE", "65535"))


settings = Settings()
