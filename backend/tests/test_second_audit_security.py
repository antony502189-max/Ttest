from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError

from app.core.config import Settings
from app.core.security import decode_access_token, verify_password
from app.schemas.auth import GoogleLoginRequest
from app.services.auth import google_email_is_authoritative, google_login_user
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
        "google_client_id": "example-client.apps.googleusercontent.com",
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


def test_production_configuration_requires_google_client_id():
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        production_settings(google_client_id="").validate_runtime()


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


class _UnusedSession:
    async def scalar(self, *_args, **_kwargs):  # pragma: no cover - invalid tokens must not query storage
        raise AssertionError("invalid Google credential must not query storage")


async def test_google_login_rejects_invalid_signature_before_querying_users(monkeypatch):
    monkeypatch.setattr("app.services.auth.get_settings", lambda: Settings(google_client_id="test-client"))
    monkeypatch.setattr(
        "app.services.auth.google_id_token.verify_oauth2_token",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad signature")),
    )

    with pytest.raises(HTTPException, match="Invalid Google credential") as error:
        await google_login_user(GoogleLoginRequest(credential="x" * 20), _UnusedSession(), user_agent="test", client_ip="127.0.0.1")
    assert error.value.status_code == 401


@pytest.mark.parametrize(
    "claims, message",
    [
        ({"iss": "evil.example", "sub": "subject", "email": "person@gmail.com", "email_verified": True}, "Invalid Google credential"),
        ({"iss": "accounts.google.com", "email": "person@gmail.com", "email_verified": True}, "Google account email is not verified"),
        ({"iss": "accounts.google.com", "sub": "subject", "email": "person@gmail.com", "email_verified": False}, "Google account email is not verified"),
    ],
)
async def test_google_login_rejects_invalid_claims_before_querying_users(monkeypatch, claims, message):
    monkeypatch.setattr("app.services.auth.get_settings", lambda: Settings(google_client_id="test-client"))
    monkeypatch.setattr("app.services.auth.google_id_token.verify_oauth2_token", lambda *_args, **_kwargs: claims)

    with pytest.raises(HTTPException, match=message) as error:
        await google_login_user(GoogleLoginRequest(credential="x" * 20), _UnusedSession(), user_agent="test", client_ip="127.0.0.1")
    assert error.value.status_code == 401
