"""Private AI cursor envelope; manual-search cursor format stays unchanged."""
import base64
import binascii
import hashlib
import hmac
import json


class InvalidAICursor(ValueError):
    pass


class AICardCursors:
    def __init__(self, key: bytes):
        if type(key) is not bytes or len(key) < 32:
            raise ValueError("explicit server signing key of at least32bytes required")
        self.key = key

    def encode(self, raw: str | None, context: str) -> str | None:
        if raw is None:
            return None
        body = json.dumps({"v": 1, "q": context, "c": raw}, sort_keys=True, separators=(",", ":")).encode()
        token = base64.urlsafe_b64encode(body).decode().rstrip("=")
        return token + "." + hmac.new(self.key, body, hashlib.sha256).hexdigest()

    def decode(self, token: str | None, context: str) -> str | None:
        if token is None:
            return None
        try:
            if type(token) is not str or len(token) > 1024:
                raise ValueError("cursor bound")
            encoded, signature = token.split(".")
            body = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
            expected = hmac.new(self.key, body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError("cursor signature")
            data = json.loads(body)
            if type(data) is not dict or set(data) != {"v", "q", "c"} or type(data["v"]) is not int or data["v"] != 1:
                raise ValueError("cursor version")
            if data["q"] != context or type(data["c"]) is not str or len(data["c"]) > 1024:
                raise ValueError("cursor context")
            return data["c"]
        except (ValueError, TypeError, KeyError, binascii.Error, UnicodeError) as error:
            raise InvalidAICursor("AI_CURSOR_INVALID_OR_REQUERY_REQUIRED") from error
