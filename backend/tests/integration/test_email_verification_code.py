from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import EmailVerificationToken, MailOutbox, User
from app.services.auth import request_verification

pytestmark = pytest.mark.integration


def listing_payload(title: str) -> dict:
    return {
        "title": title,
        "city": "Santa Cruz de Tenerife",
        "area": "Centro",
        "approximateAddress": "Centro",
        "rentalMode": "long",
        "monthlyPrice": 650,
        "roomType": "Habitación individual",
        "latitude": 28.12,
        "longitude": -16.72,
    }


async def test_host_must_confirm_six_digit_email_code_before_creating_listing(client):
    registration = await client.post(
        "/api/v1/auth/register",
        json={"name": "Code Host", "email": "code-host@example.com", "password": "Correct-Horse-1234", "role": "host"},
    )
    assert registration.status_code == 201, registration.text
    access_token = registration.json()["accessToken"]
    headers = {"Authorization": f"Bearer {access_token}"}

    async with SessionLocal() as session:
        assert await session.scalar(select(MailOutbox).where(MailOutbox.recipient == "code-host@example.com")) is None

    blocked = await client.post(
        "/api/v1/listings",
        headers=headers,
        json=listing_payload("Needs verified email"),
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "EMAIL_VERIFICATION_REQUIRED"

    verification_status = await client.get("/api/v1/auth/email-verification/status", headers=headers)
    assert verification_status.status_code == 200
    assert verification_status.json() == {"verified": False, "email": "c********@example.com"}

    requested = await client.post("/api/v1/auth/email-verification/request", headers=headers)
    assert requested.status_code == 202, requested.text
    assert requested.json()["email"].startswith("c*")

    async with SessionLocal() as session:
        message = await session.scalar(
            select(MailOutbox).where(MailOutbox.recipient == "code-host@example.com").order_by(MailOutbox.created_at.desc())
        )
        assert message is not None
        assert "token=" not in message.body
        code = re.search(r"\b(\d{6})\b", message.body)
        assert code

    invalid_code = "000000" if code.group(1) != "000000" else "000001"
    invalid = await client.post("/api/v1/auth/email-verification/confirm", headers=headers, json={"code": invalid_code})
    assert invalid.status_code == 400
    verified = await client.post("/api/v1/auth/email-verification/confirm", headers=headers, json={"code": code.group(1)})
    assert verified.status_code == 204, verified.text
    created = await client.post(
        "/api/v1/listings",
        headers=headers,
        json=listing_payload("Verified host"),
    )
    assert created.status_code == 201, created.text


async def test_verification_code_is_consumed_after_five_failed_attempts(client):
    registration = await client.post(
        "/api/v1/auth/register",
        json={"name": "Attempt Host", "email": "attempt-host@example.com", "password": "Correct-Horse-1234", "role": "host"},
    )
    headers = {"Authorization": f"Bearer {registration.json()['accessToken']}"}
    assert (await client.post("/api/v1/auth/email-verification/request", headers=headers)).status_code == 202
    async with SessionLocal() as session:
        message = await session.scalar(select(MailOutbox).order_by(MailOutbox.created_at.desc()))
        assert message is not None
        code = re.search(r"\b(\d{6})\b", message.body)
        assert code
    invalid_code = "000000" if code.group(1) != "000000" else "000001"

    for _ in range(5):
        response = await client.post("/api/v1/auth/email-verification/confirm", headers=headers, json={"code": invalid_code})
        assert response.status_code == 400

    async with SessionLocal() as session:
        token = await session.scalar(select(EmailVerificationToken).order_by(EmailVerificationToken.created_at.desc()))
        assert token is not None and token.attempts == 5 and token.consumed_at is not None


async def test_resend_invalidates_old_code_and_enforces_hourly_limit(client):
    registration = await client.post(
        "/api/v1/auth/register",
        json={"name": "Resend Host", "email": "resend-host@example.com", "password": "Correct-Horse-1234", "role": "host"},
    )
    user_id = registration.json()["user"]["id"]
    async with SessionLocal() as session:
        user = await session.get(User, user_id)
        assert user is not None
        await request_verification(user, session)
        first = await session.scalar(select(EmailVerificationToken).order_by(EmailVerificationToken.created_at.desc()))
        assert first is not None
        first.created_at = datetime.now(UTC) - timedelta(seconds=61)
        await session.commit()

        await request_verification(user, session)
        await session.refresh(first)
        assert first.consumed_at is not None

        for _ in range(3):
            latest = await session.scalar(select(EmailVerificationToken).order_by(EmailVerificationToken.created_at.desc()))
            assert latest is not None
            latest.created_at = datetime.now(UTC) - timedelta(seconds=61)
            await session.commit()
            await request_verification(user, session)

        latest = await session.scalar(select(EmailVerificationToken).order_by(EmailVerificationToken.created_at.desc()))
        assert latest is not None
        latest.created_at = datetime.now(UTC) - timedelta(seconds=61)
        await session.commit()
        with pytest.raises(HTTPException, match="Too many verification codes") as error:
            await request_verification(user, session)
        assert error.value.status_code == 429
