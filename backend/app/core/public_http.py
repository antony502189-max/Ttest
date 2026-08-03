from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator, Awaitable, Callable
from ipaddress import ip_address

import httpx

MAX_PUBLIC_RESPONSE_BYTES = 16 * 1024 * 1024
_ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient


async def resolve_host(host: str, port: int) -> set[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return {record[4][0] for record in records}


async def validate_public_url(url: httpx.URL) -> None:
    """Reject non-HTTP and non-public destinations before outbound requests."""
    if url.scheme not in {"http", "https"} or not url.host:
        raise httpx.InvalidURL("Only public HTTP(S) URLs are allowed")
    port = url.port or (443 if url.scheme == "https" else 80)
    try:
        addresses = {url.host} if _is_ip_literal(url.host) else await resolve_host(url.host, port)
    except OSError as exc:
        raise httpx.ConnectError("Unable to resolve outbound host") from exc
    if not addresses:
        raise httpx.ConnectError("Outbound host has no addresses")
    for value in addresses:
        try:
            address = ip_address(value)
        except ValueError as exc:
            raise httpx.ConnectError("Outbound host resolved to an invalid address") from exc
        if not address.is_global:
            raise httpx.ConnectError("Outbound request to a non-public address is blocked")


def _is_ip_literal(host: str) -> bool:
    try:
        ip_address(host)
        return True
    except ValueError:
        return False


class LimitedAsyncStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpx.AsyncByteStream, limit: int):
        self.stream = stream
        self.limit = limit

    async def __aiter__(self) -> AsyncIterator[bytes]:
        total = 0
        async for chunk in self.stream:
            total += len(chunk)
            if total > self.limit:
                await self.stream.aclose()
                raise httpx.StreamError("Outbound response exceeded the configured size limit")
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


async def validate_public_request(request: httpx.Request) -> None:
    # HTTPX invokes request hooks again for redirects, so every redirect target
    # is checked rather than trusting only the initial source URL.
    await validate_public_url(request.url)


async def limit_public_response(response: httpx.Response) -> None:
    content_length = response.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_PUBLIC_RESPONSE_BYTES:
                await response.aclose()
                raise httpx.StreamError("Outbound response exceeded the configured size limit")
        except ValueError:
            pass
    response.stream = LimitedAsyncStream(response.stream, MAX_PUBLIC_RESPONSE_BYTES)


def _append_hook(
    hooks: dict[str, list[Callable[..., Awaitable[None]]]],
    name: str,
    hook: Callable[..., Awaitable[None]],
) -> None:
    hooks.setdefault(name, []).append(hook)


class PublicNetworkAsyncClient(_ORIGINAL_ASYNC_CLIENT):
    """HTTPX client with public-network and response-size guards.

    Explicit transports are left untouched so ASGI/MockTransport test clients
    and other in-process callers continue to work. Production source adapters
    use the default network transport and therefore receive these guards.
    """

    def __init__(self, *args, **kwargs):
        if kwargs.get("transport") is None:
            configured = kwargs.get("event_hooks") or {}
            hooks = {name: list(values) for name, values in configured.items()}
            _append_hook(hooks, "request", validate_public_request)
            _append_hook(hooks, "response", limit_public_response)
            kwargs["event_hooks"] = hooks
        super().__init__(*args, **kwargs)


def install_public_http_guard() -> None:
    if httpx.AsyncClient is not PublicNetworkAsyncClient:
        httpx.AsyncClient = PublicNetworkAsyncClient  # type: ignore[misc]
