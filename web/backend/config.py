"""Application settings via pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent  # web/


class Settings(BaseSettings):
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'scraper.db'}"
    sessions_dir: str = str(BASE_DIR / "data" / "sessions")
    browser_headless: bool = False
    browser_slow_mo: int = 0
    cors_origins: list[str] = ["http://localhost:5173"]
    max_concurrent_sessions: int = 3
    use_tor: bool = True  # Auto-detect: routes through Tor if running on port 9050

    # Twenty CRM integration
    twenty_crm_url: str = ""
    twenty_crm_api_key: str = ""
    twenty_crm_auto_sync: bool = False

    model_config = {"env_prefix": "SCRAPER_", "env_file": ".env"}


settings = Settings()
