from datetime import UTC, datetime, timedelta

import jwt
import pytest
from jwt import InvalidTokenError

from app.core.config import Settings
from app.core.security import decode_access_token, verify_password
from app.services.auth import google_email_is_authoritative
from app.services.rate_limit import MemoryRateLimiter


def production_settings(**overrides) -> Settings:
    values = {
        "app_env": "production",
        "jwt_secret": "a-strong-production-secret-with-more-than-32-characters",
        "frontend_origins": "https://www.example.test",
        "frontend_app_url": "https://www.example.test",
        "storage_backend": "s3",
        "s3_bucket": "media",
        "s3_access_key": "access",
        "s3_secret_key": "secret",
        "smtp_host": "smtp.example.test",
        "redis_url": "redis://redis:6379/0",
        "auto_publish_listings": False,
    }
    values.update(overrides)
    return Settings(**values)


def test_production_configuration_rejects_local_media_and_http_frontend():
    with pytest.raises(RuntimeError):
        production_settings(storage_backend="local", frontend_app_url="http://example.test").validate_runtime()


def test_valid_production_configuration_passes():
    production_settings().validate_runtime()


def test_access_token_decoder_requires_access_type(monkeypatch):
    settings = Settings(jwt_secret="test-secret-with-at-least-32-characters")
    monkeypatch.setattr("app.core.security.get_settings", lambda: settings)
    token = jwt.encode(
        {
            "sub": "00000000-0000-4000-8000-000000000001",
            "type": "refresh",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_malformed_argon2_hash_is_invalid_credentials():
    assert verify_password("any-password", "not-an-argon2-hash") is False


async def test_memory_rate_limiter_has_bounded_key_count():
    limiter = MemoryRateLimiter(max_keys=2)
    assert (await limiter.consume("first", 10, 60)).allowed
    assert (await limiter.consume("second", 10, 60)).allowed
    assert (await limiter.consume("third", 10, 60)).allowed
    assert len(limiter._attempts) == 2
    assert "first" not in limiter._attempts


def test_google_account_linking_only_trusts_google_authoritative_emails():
    assert google_email_is_authoritative({}, "person@gmail.com") is True
    assert google_email_is_authoritative({"hd": "example.edu"}, "person@example.edu") is True
    assert google_email_is_authoritative({}, "person@example.edu") is False
