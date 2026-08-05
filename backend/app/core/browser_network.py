from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from .public_http import validate_public_url

logger = logging.getLogger(__name__)
LOCAL_ONLY_SCHEMES = {"about", "blob", "data"}


def hostname_matches_domain(url: str, domain: str) -> bool:
    """Match an exact host or its subdomain, never a deceptive suffix."""
    try:
        hostname = (urlparse(url).hostname or "").casefold().rstrip(".")
    except ValueError:
        return False
    expected = domain.casefold().rstrip(".")
    return bool(hostname and expected and (hostname == expected or hostname.endswith(f".{expected}")))


async def validate_public_browser_url(url: str) -> None:
    """Reject non-HTTP schemes and hosts resolving outside the public Internet."""
    parsed = urlparse(url)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise httpx.InvalidURL("Browser navigation requires a public HTTP(S) URL")
    await validate_public_url(httpx.URL(url))


async def route_public_browser_request(route: Any) -> None:
    """Apply the public-network guard to every Chromium HTTP subrequest."""
    request = route.request
    try:
        parsed = urlparse(request.url)
        scheme = parsed.scheme.casefold()
        hostname = parsed.hostname or ""
    except ValueError:
        await route.abort("blockedbyclient")
        return

    if scheme in LOCAL_ONLY_SCHEMES:
        await route.continue_()
        return

    try:
        await validate_public_browser_url(request.url)
    except (httpx.HTTPError, httpx.InvalidURL, ValueError):
        logger.warning(
            "external_browser_request_blocked",
            extra={
                "scheme": scheme,
                "host": hostname,
                "resource_type": getattr(request, "resource_type", "unknown"),
            },
        )
        await route.abort("blockedbyclient")
        return
    await route.continue_()


async def block_public_browser_websocket(web_socket_route: Any) -> None:
    """The importer does not need WebSockets; never connect them to a server."""
    try:
        parsed = urlparse(web_socket_route.url)
        hostname = parsed.hostname or ""
    except ValueError:
        hostname = ""
    logger.warning("external_browser_websocket_blocked", extra={"host": hostname})
    await web_socket_route.close(code=1008, reason="Blocked by public network policy")


async def configure_public_browser_context(context: Any) -> None:
    """Install routing before any page is created in the context."""
    await context.route("**/*", route_public_browser_request)
    await context.route_web_socket("**/*", block_public_browser_websocket)
