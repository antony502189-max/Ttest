from functools import lru_cache
from hmac import compare_digest
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_EXTERNAL_IMPORT_SOURCES = {
    "idealista",
    "fotocasa",
    "milanuncios",
    "pisocompartido",
    "pisos",
    "thinkspain",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = "112233-api"
    database_url: str = "postgresql+asyncpg://ttest:ttest@localhost:5432/ttest"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: int = 30
    database_pool_recycle_seconds: int = 1_800
    jwt_secret: str = "unsafe-development-secret-change-me-32"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    password_reset_minutes: int = 30
    email_verification_minutes: int = 10
    password_work_concurrency: int = 2
    # Development and tests may fall back to JWT_SECRET. Production must use
    # an independent secret so access-token and low-entropy OTP domains remain
    # cryptographically separated.
    email_verification_hmac_secret: str = ""
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
    smtp_from_name: str = ""
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
    s3_connect_timeout_seconds: int = 3
    s3_read_timeout_seconds: int = 10
    s3_max_attempts: int = 3
    s3_max_pool_connections: int = 32
    max_upload_bytes: int = 8 * 1024 * 1024
    max_image_dimension: int = 8_000
    max_image_pixels: int = 25_000_000
    image_processing_concurrency: int = 2

    redis_url: str = ""
    metrics_enabled: bool = True
    structured_logs: bool = True
    log_level: str = "INFO"
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.05
    external_import_enabled: bool = True
    external_import_interval_seconds: int = 7200
    external_import_run_on_start: bool = True
    external_import_sources: str = "idealista,fotocasa,milanuncios,pisocompartido,pisos,thinkspain"
    external_import_request_timeout_seconds: int = 25
    external_import_max_concurrency_per_source: int = 3
    external_import_download_images: bool = True
    external_import_user_agent: str = "112233.es room aggregator"
    external_import_playwright_enabled: bool = False
    external_removal_check_enabled: bool = True
    external_removal_check_interval_seconds: int = 900
    external_worker_stale_after_seconds: int = 300

    @property
    def origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.frontend_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def verification_hmac_secret(self) -> str:
        return self.email_verification_hmac_secret or self.jwt_secret

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
        if self.password_work_concurrency < 1:
            problems.append("PASSWORD_WORK_CONCURRENCY must be positive")
        if self.mail_worker_interval_seconds < 1 or self.mail_worker_batch_size < 1 or self.mail_max_attempts < 1:
            problems.append("Mail worker limits must be positive")
        if (
            self.database_pool_size < 1
            or self.database_max_overflow < 0
            or self.database_pool_timeout_seconds < 1
            or self.database_pool_recycle_seconds < 1
        ):
            problems.append("Database pool settings must be positive and overflow cannot be negative")
        if (
            self.max_upload_bytes < 1
            or self.max_image_dimension < 1
            or self.max_image_pixels < 1
            or self.image_processing_concurrency < 1
        ):
            problems.append("Media upload and processing limits must be positive")
        if (
            self.s3_connect_timeout_seconds < 1
            or self.s3_read_timeout_seconds < 1
            or self.s3_max_attempts < 1
            or self.s3_max_pool_connections < 1
        ):
            problems.append("S3 timeout, retry and pool settings must be positive")
        if (
            self.external_import_interval_seconds < 1
            or self.external_import_request_timeout_seconds < 1
            or self.external_import_max_concurrency_per_source < 1
            or self.external_worker_stale_after_seconds < 120
        ):
            problems.append("External import limits are invalid")
        if not 0 <= self.sentry_traces_sample_rate <= 1:
            problems.append("SENTRY_TRACES_SAMPLE_RATE must be between 0 and 1")

        if self.is_production:
            if len(self.jwt_secret) < 32 or "unsafe" in self.jwt_secret or "development" in self.jwt_secret:
                problems.append("JWT_SECRET must be a strong production secret")
            if len(self.email_verification_hmac_secret) < 32:
                problems.append("EMAIL_VERIFICATION_HMAC_SECRET must contain at least 32 characters in production")
            elif compare_digest(
                self.email_verification_hmac_secret.encode(),
                self.jwt_secret.encode(),
            ):
                problems.append("EMAIL_VERIFICATION_HMAC_SECRET must be independent from JWT_SECRET")
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
            if not self.google_client_id:
                problems.append("GOOGLE_CLIENT_ID is required in production")
            if not self.redis_url:
                problems.append("REDIS_URL is required for distributed production rate limiting")
            if self.auto_publish_listings:
                problems.append("AUTO_PUBLISH_LISTINGS must be false in production")
            if self.external_import_enabled:
                configured_sources = {
                    item.strip().casefold()
                    for item in self.external_import_sources.split(",")
                    if item.strip()
                }
                if not configured_sources:
                    problems.append("EXTERNAL_IMPORT_SOURCES must enable at least one source in production")
                unknown_sources = configured_sources - SUPPORTED_EXTERNAL_IMPORT_SOURCES
                if unknown_sources:
                    problems.append("EXTERNAL_IMPORT_SOURCES contains unsupported sources")

        if problems:
            raise RuntimeError("Invalid runtime configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
