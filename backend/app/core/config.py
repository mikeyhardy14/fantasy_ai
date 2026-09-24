from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment / .env.

    Only server-side code reads these. Nothing here is ever shipped to the browser.
    """

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Fantasy AI"
    environment: str = Field(default="development")
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://fantasy:fantasy@localhost:5432/fantasy_ai"
    db_echo: bool = False

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7

    credentials_key: str | None = None  # Fernet key for the Sleeper token and future OAuth tokens

    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Free tool-calling models. Gemini is used when its key is set, then Groq, then OpenAI.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    ai_max_tool_rounds: int = 8

    sleeper_base_url: str = "https://api.sleeper.app/v1"
    sleeper_graphql_url: str = "https://sleeper.com/graphql"
    sleeper_timeout_seconds: float = 15.0
    sleeper_player_cache_path: Path = BACKEND_DIR / ".cache" / "sleeper_players.json"
    sleeper_player_cache_ttl_hours: int = 24
    default_season: int = 2026

    nfl_data_file: Path = BACKEND_DIR / "data" / "nfl_data.json"
    espn_schedule_cache_dir: Path = BACKEND_DIR / ".cache"
    espn_schedule_ttl_hours: int = 6

    demo_enabled: bool = True

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key or self.groq_api_key or self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
