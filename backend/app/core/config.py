from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "112233-api"
    database_url: str = "postgresql+asyncpg://ttest:ttest@localhost:5432/ttest"
    jwt_secret: str = "unsafe-development-secret-change-me-32"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    password_reset_minutes: int = 30
    email_verification_minutes: int = 60 * 24
    frontend_app_url: str = "http://localhost:5173"
    frontend_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175,"
        "http://localhost:5176,http://127.0.0.1:5176,"
        "https://antony502189-max.github.io"
    )

    google_client_id: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@112233.es"
    smtp_starttls: bool = True
    mail_worker_interval_seconds: int = 10
    mail_worker_batch_size: int = 50
    mail_max_attempts: int = 8

    # In production new listings wait for moderation unless explicitly enabled.
    auto_publish_listings: bool = False

    media_root: Path = Path("var/media")
    storage_backend: str = "local"
    s3_bucket: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_force_path_style: bool = True
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_dimension: int = 8_000

    redis_url: str = ""
    metrics_enabled: bool = True
    structured_logs: bool = True
    log_level: str = "INFO"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05

    @property
    def origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.frontend_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_runtime(self) -> None:
        """Fail fast instead of silently starting with unsafe or contradictory configuration."""
        problems: list[str] = []
        environment = self.app_env.lower()
        if environment not in {"development", "test", "production"}:
            problems.append("APP_ENV must be development, test, or production")
        if self.storage_backend not in {"local", "s3"}:
            problems.append("STORAGE_BACKEND must be local or s3")
        if self.access_token_minutes < 1:
            problems.append("ACCESS_TOKEN_MINUTES must be positive")
        if self.refresh_token_days < 1:
            problems.append("REFRESH_TOKEN_DAYS must be positive")
        if self.password_reset_minutes < 1 or self.email_verification_minutes < 1:
            problems.append("Password reset and email verification lifetimes must be positive")
        if self.mail_worker_interval_seconds < 1 or self.mail_worker_batch_size < 1 or self.mail_max_attempts < 1:
            problems.append("Mail worker limits must be positive")
        if self.max_upload_bytes < 1 or self.max_image_dimension < 1:
            problems.append("Media upload limits must be positive")
        if not 0 <= self.sentry_traces_sample_rate <= 1:
            problems.append("SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1")

        if self.is_production:
            if len(self.jwt_secret) < 32 or "unsafe" in self.jwt_secret or "development" in self.jwt_secret:
                problems.append("JWT_SECRET must be a strong production secret")
            if not self.origins or any(origin.startswith("http://") for origin in self.origins):
                problems.append("FRONTEND_ORIGINS must contain explicit HTTPS origins")
            if not self.frontend_app_url.startswith("https://"):
                problems.append("FRONTEND_APP_URL must use HTTPS in production")
            if self.storage_backend != "s3":
                problems.append("Production media storage must use STORAGE_BACKEND=s3")
            if self.storage_backend == "s3" and not all([self.s3_bucket, self.s3_access_key, self.s3_secret_key]):
                problems.append("S3 storage requires bucket and credentials")
            if not self.smtp_host:
                problems.append("SMTP_HOST is required in production")
            if not self.redis_url:
                problems.append("REDIS_URL is required for distributed production rate limiting")
            if self.auto_publish_listings:
                problems.append("AUTO_PUBLISH_LISTINGS must be false in production")

        if problems:
            raise RuntimeError("Invalid runtime configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
