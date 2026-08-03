from __future__ import annotations

from pathlib import Path


AUTH = Path("backend/app/services/auth.py")
LISTINGS = Path("backend/app/schemas/listings.py")
AUDIT = Path("scripts/final-audit-local.sh")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new, 1)


def patch_auth() -> None:
    text = AUTH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from .mail import enqueue_email_verification, enqueue_password_reset\n\n\n@dataclass(frozen=True)\n",
        "from .mail import enqueue_email_verification, enqueue_password_reset\n\n"
        "PASSWORD_RESET_COOLDOWN = timedelta(seconds=60)\n"
        "PASSWORD_RESET_WINDOW = timedelta(hours=1)\n"
        "MAX_PASSWORD_RESETS_PER_HOUR = 3\n\n\n"
        "@dataclass(frozen=True)\n",
        label="password reset constants",
    )
    old = '''async def request_password_reset(email: str, session: AsyncSession) -> dict[str, str]:
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    response = {"message": "If the account exists, password reset instructions have been sent."}
    if not user or user.blocked or user.deleted_at:
        return response
    now = datetime.now(UTC)
    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    raw_token = new_refresh_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=get_settings().password_reset_minutes),
        )
    )
    enqueue_password_reset(session, user.email, raw_token)
    await session.commit()
    if get_settings().app_env in {"development", "test"}:
        response["resetToken"] = raw_token
    return response
'''
    new = '''async def request_password_reset(email: str, session: AsyncSession) -> dict[str, str]:
    response = {"message": "If the account exists, password reset instructions have been sent."}
    user = await session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if not user or user.blocked or user.deleted_at:
        return response

    now = datetime.now(UTC)
    settings = get_settings()
    # Serialize by account so distributed callers cannot race the cooldown and
    # create multiple valid tokens or outbox rows. Suppression remains silent:
    # callers receive the same generic response as for an unknown account.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
        {"lock_key": f"password-reset:{user.id}"},
    )
    issued_at = list(
        (
            await session.scalars(
                select(PasswordResetToken.created_at)
                .where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.created_at > now - PASSWORD_RESET_WINDOW,
                )
                .order_by(PasswordResetToken.created_at.desc())
                .limit(MAX_PASSWORD_RESETS_PER_HOUR)
            )
        ).all()
    )
    quota_reached = len(issued_at) >= MAX_PASSWORD_RESETS_PER_HOUR
    cooling_down = bool(issued_at and issued_at[0] > now - PASSWORD_RESET_COOLDOWN)
    if quota_reached or cooling_down:
        # End the advisory-lock transaction even though no state changed.
        await session.commit()
        return response

    await session.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    raw_token = new_refresh_token()
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    enqueue_password_reset(session, user.email, raw_token)
    await session.commit()
    if settings.app_env in {"development", "test"}:
        response["resetToken"] = raw_token
    return response
'''
    text = replace_once(text, old, new, label="request_password_reset")
    AUTH.write_text(text, encoding="utf-8")


def patch_listing_search() -> None:
    text = LISTINGS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "    offset: int = Field(default=0, ge=0)\n",
        "    offset: int = Field(default=0, ge=0, le=10_000)\n",
        label="listing offset",
    )
    LISTINGS.write_text(text, encoding="utf-8")


def patch_full_audit() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    old = '''echo '[3/9] Installing local backend audit environment'
python3 -m venv "$AUDIT_VENV"
"$AUDIT_VENV/bin/python" -m pip install --upgrade pip
"$AUDIT_VENV/bin/python" -m pip install -e "$ROOT/backend[dev]"
'''
    new = '''echo '[3/9] Installing local backend audit environment'
case "$AUDIT_VENV" in
  "$ROOT"/*) ;;
  *) echo 'AUDIT_VENV must be inside the repository root' >&2; exit 64 ;;
esac
rm -rf "$AUDIT_VENV"
python3 -m venv "$AUDIT_VENV"
"$AUDIT_VENV/bin/python" -m pip install --upgrade pip
"$AUDIT_VENV/bin/python" -m pip install --constraint "$ROOT/backend/constraints.txt" -e "$ROOT/backend[dev]"
"$AUDIT_VENV/bin/python" -m pip check
'''
    text = replace_once(text, old, new, label="full audit backend environment")
    AUDIT.write_text(text, encoding="utf-8")


def main() -> None:
    patch_auth()
    patch_listing_search()
    patch_full_audit()


if __name__ == "__main__":
    main()
