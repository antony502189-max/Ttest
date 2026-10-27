"""Explicit signed guest identity; no production TTL/key or transfer default."""
import base64
import binascii
import hashlib
import hmac
import json
import time
from uuid import uuid4

from pydantic import Field

from ..schemas.ai_search_quota import QuotaSubject, StrictContract


class InvalidGuestToken(ValueError):
    pass


class GuestPolicy(StrictContract):
    ttl_seconds: int = Field(ge=60, le=31_536_000)


class GuestTokens:
    def __init__(self, *, key: bytes, policy: GuestPolicy):
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("explicit independent guest signing key required")
        self.key, self.policy = key, GuestPolicy.model_validate(policy.model_dump())

    def issue(self, *, now: int | None = None) -> tuple[str, QuotaSubject]:
        instant = int(time.time()) if now is None else now
        subject = QuotaSubject(kind="guest", id=uuid4())
        body = json.dumps({"v": 1, "id": str(subject.id), "iat": instant,
                           "exp": instant + self.policy.ttl_seconds}, sort_keys=True, separators=(",", ":")).encode()
        encoded = base64.urlsafe_b64encode(body).decode().rstrip("=")
        return encoded + "." + hmac.new(self.key, body, hashlib.sha256).hexdigest(), subject

    def read(self, token: str, *, now: int | None = None) -> QuotaSubject:
        try:
            if type(token) is not str or len(token) > 1024:
                raise ValueError("bound")
            encoded, signature = token.split(".")
            body = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            if not hmac.compare_digest(signature, hmac.new(self.key, body, hashlib.sha256).hexdigest()):
                raise ValueError("signature")
            data = json.loads(body)
            if type(data) is not dict or set(data) != {"v", "id", "iat", "exp"} or type(data["v"]) is not int or data["v"] != 1:
                raise ValueError("version")
            instant = int(time.time()) if now is None else now
            if type(data["iat"]) is not int or type(data["exp"]) is not int or not data["iat"] <= instant < data["exp"]:
                raise ValueError("expired")
            if data["exp"] - data["iat"] != self.policy.ttl_seconds:
                raise ValueError("policy changed")
            return QuotaSubject.model_validate_json(json.dumps({"kind": "guest", "id": data["id"]}))
        except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
            raise InvalidGuestToken("AI_GUEST_IDENTITY_INVALID_OR_EXPIRED") from None

    def ip_key(self, address: str, *, purpose: str) -> str:
        return purpose + ":" + hmac.new(self.key, address.encode(), hashlib.sha256).hexdigest()
