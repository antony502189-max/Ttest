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
    password_reset_minutes: int = 30
    email_verification_minutes: int = 60 * 24
    frontend_app_url: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@112233.es"
    smtp_starttls: bool = True
    google_client_id: str = ""
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:5175,http://127.0.0.1:5175,http://localhost:5176,http://127.0.0.1:5176,https://antony502189-max.github.io"
    # In production new listings wait for moderation unless explicitly enabled.
    auto_publish_listings: bool = False
    media_root: Path = Path("var/media")
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_dimension: int = 8_000

    @property
    def origins(self) -> list[str]:
        return [item.strip() for item in self.frontend_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
