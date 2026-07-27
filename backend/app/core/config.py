from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://ttest:ttest@localhost:5432/ttest"
    jwt_secret: str = "unsafe-development-secret-change-me-32"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,https://antony502189-max.github.io"
    auto_publish_listings: bool = True
    media_root: Path = Path("var/media")
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_dimension: int = 8_000

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
