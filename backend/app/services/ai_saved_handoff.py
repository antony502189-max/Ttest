"""Authenticated, short-lived copy of an owned committed search for registration.

This is not an identity/session/quota transfer or listing-evidence token. The
authenticated account must explicitly save it. Keep tokens only in request/UI
memory; base64 is not encryption. No network, persistence or default key here.
"""
import base64
import binascii
import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from ..repositories.ai_saved_searches import SavedIntent
from ..repositories.ai_search_sessions import CommittedIntent
from ..schemas.ai_search_quota import StrictContract


class SavedHandoffError(ValueError):
    pass


class SavedHandoff(StrictContract):
    schema_version: Literal["ai-saved-handoff.v1"]
    issuer: Literal["112233.es-ai"]
    purpose: Literal["registered_save_only"]
    result_ref: UUID
    intent: SavedIntent = Field(repr=False)
    issued_at: int = Field(ge=0)
    expires_at: int = Field(ge=1)

    @model_validator(mode="after")
    def bounded_lifetime(self):
        if self.expires_at - self.issued_at != 300:
            raise ValueError("bounded handoff lifetime required")
        return self


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class SavedHandoffSigner:
    _domain = b"112233/save-ai-search/v1\0"

    def __init__(self, key: bytes):
        if type(key) is not bytes or len(key) != 32:
            raise SavedHandoffError("AI_HANDOFF_KEY_REQUIRED")
        self._key = key

    def uses_key(self, key: bytes) -> bool:
        return hmac.compare_digest(self._key, key)

    def issue(self, committed: CommittedIntent, *, now: int | None = None) -> str:
        # The route obtains this snapshot from owned sessions.result, not a
        # mutable conversation or a client-provided Criteria object.
        committed = CommittedIntent.model_validate_json(committed.model_dump_json(exclude_none=True))
        instant = int(datetime.now(UTC).timestamp()) if now is None else now
        body = SavedHandoff(schema_version="ai-saved-handoff.v1", issuer="112233.es-ai",
            purpose="registered_save_only", result_ref=committed.result_ref,
            intent=SavedIntent(schema_version=committed.intent.schema_version,
                taxonomy_version=committed.intent.taxonomy_version, criteria=committed.intent.criteria),
            issued_at=instant, expires_at=instant + 300)
        raw = json.dumps(body.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":")).encode()
        token = _encode(raw) + "." + _encode(hmac.digest(self._key, self._domain + raw, hashlib.sha256))
        if len(token) > 32768:
            raise SavedHandoffError("AI_HANDOFF_TOO_LARGE")
        return token

    def verify(self, token: str, *, now: int | None = None) -> SavedHandoff:
        try:
            if type(token) is not str or not 1 <= len(token) <= 32768 or not token.isascii():
                raise ValueError
            encoded, signature = token.split(".")
            raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            mac = base64.b64decode(signature + "=" * (-len(signature) % 4), altchars=b"-_", validate=True)
            if _encode(raw) != encoded or _encode(mac) != signature or not hmac.compare_digest(
                    mac, hmac.digest(self._key, self._domain + raw, hashlib.sha256)):
                raise ValueError
            body = SavedHandoff.model_validate_json(raw)
        except (ValueError, TypeError, binascii.Error, UnicodeError):
            raise SavedHandoffError("AI_HANDOFF_INVALID") from None
        instant = int(datetime.now(UTC).timestamp()) if now is None else now
        if body.issued_at > instant + 30:
            raise SavedHandoffError("AI_HANDOFF_CLOCK_INVALID")
        if body.expires_at <= instant:
            raise SavedHandoffError("AI_HANDOFF_EXPIRED")
        return body
