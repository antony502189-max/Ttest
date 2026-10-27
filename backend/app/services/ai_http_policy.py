"""Required engineering policies; no production budgets or proxy trust defaults."""
import math
from contextvars import ContextVar
from dataclasses import dataclass
from ipaddress import ip_address, ip_network

from fastapi import Request

from ..core.http import client_ip, normalized_ip

HTTP_DEADLINE: ContextVar[float | None] = ContextVar("ai_http_deadline", default=None)


@dataclass(frozen=True)
class AIHTTPPolicy:
    request_seconds: float
    max_active_sessions: int
    trusted_proxy_networks: tuple[str, ...]

    def __post_init__(self):
        if type(self.request_seconds) not in {float, int} or not math.isfinite(self.request_seconds) or self.request_seconds <= 0:
            raise ValueError("explicit finite positive HTTP deadline required")
        if type(self.max_active_sessions) is not int or self.max_active_sessions < 1:
            raise ValueError("explicit positive active session bound required")
        if type(self.trusted_proxy_networks) is not tuple:
            raise ValueError("explicit immutable proxy network allowlist required")
        for value in self.trusted_proxy_networks:
            network = ip_network(value)
            if network.prefixlen == 0:
                raise ValueError("universal proxy trust is forbidden")

    def address(self, request: Request) -> str:
        direct = normalized_ip(request.client.host) if request.client else None
        if direct and any(ip_address(direct) in ip_network(net) for net in self.trusted_proxy_networks):
            return client_ip(request)
        return direct or "unknown"
