import re
from ipaddress import ip_address
from uuid import uuid4

from fastapi import Request

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def normalized_ip(value: str) -> str | None:
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return ip_address(candidate).compressed
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """Return the client address sanitized by the trusted reverse proxy chain."""
    real_ip = normalized_ip(request.headers.get("x-real-ip", ""))
    if real_ip:
        return real_ip
    forwarded = [part for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    for part in reversed(forwarded):
        candidate = normalized_ip(part)
        if candidate:
            return candidate
    if request.client:
        direct = normalized_ip(request.client.host)
        if direct:
            return direct
    return "unknown"


def request_id_for(request: Request) -> str:
    """Accept only bounded log-safe caller IDs; generate a UUID otherwise."""
    candidate = request.headers.get("X-Request-ID", "")
    return candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else str(uuid4())
