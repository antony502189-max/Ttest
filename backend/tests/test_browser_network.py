from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx

from app.core import browser_network
from app.external_sources import IdealistaSource


@dataclass
class FakeRequest:
    url: str
    resource_type: str = "document"


class FakeRoute:
    def __init__(self, url: str, resource_type: str = "document") -> None:
        self.request = FakeRequest(url, resource_type)
        self.continued = False
        self.aborted_with: str | None = None

    async def continue_(self) -> None:
        self.continued = True

    async def abort(self, error_code: str) -> None:
        self.aborted_with = error_code


class FakeWebSocketRoute:
    url = "wss://example.test/socket"

    def __init__(self) -> None:
        self.closed_with: tuple[int, str] | None = None

    async def close(self, *, code: int, reason: str) -> None:
        self.closed_with = (code, reason)


class FakeBrowserContext:
    def __init__(self) -> None:
        self.http_route: tuple[str, object] | None = None
        self.websocket_route: tuple[str, object] | None = None

    async def route(self, pattern: str, handler) -> None:
        self.http_route = (pattern, handler)

    async def route_web_socket(self, pattern: str, handler) -> None:
        self.websocket_route = (pattern, handler)


def test_browser_route_allows_validated_public_http(monkeypatch) -> None:
    checked: list[str] = []

    async def allow(url: httpx.URL) -> None:
        checked.append(str(url))

    monkeypatch.setattr(browser_network, "validate_public_url", allow)
    route = FakeRoute("https://cdn.example.test/room.jpg", "image")
    asyncio.run(browser_network.route_public_browser_request(route))

    assert checked == ["https://cdn.example.test/room.jpg"]
    assert route.continued
    assert route.aborted_with is None


def test_browser_route_blocks_private_or_unresolvable_http(monkeypatch) -> None:
    async def reject(url: httpx.URL) -> None:
        raise httpx.ConnectError("non-public target", request=httpx.Request("GET", url))

    monkeypatch.setattr(browser_network, "validate_public_url", reject)
    route = FakeRoute("http://minio:9000/private-object", "image")
    asyncio.run(browser_network.route_public_browser_request(route))

    assert not route.continued
    assert route.aborted_with == "blockedbyclient"


def test_browser_route_allows_local_data_without_network_resolution(monkeypatch) -> None:
    async def unexpected(_: httpx.URL) -> None:
        raise AssertionError("data URLs must not use DNS validation")

    monkeypatch.setattr(browser_network, "validate_public_url", unexpected)
    route = FakeRoute("data:text/plain,public", "image")
    asyncio.run(browser_network.route_public_browser_request(route))

    assert route.continued
    assert route.aborted_with is None


def test_browser_context_installs_http_and_websocket_guards_before_pages() -> None:
    context = FakeBrowserContext()
    asyncio.run(browser_network.configure_public_browser_context(context))

    assert context.http_route == ("**/*", browser_network.route_public_browser_request)
    assert context.websocket_route == ("**/*", browser_network.block_public_browser_websocket)

    socket = FakeWebSocketRoute()
    asyncio.run(browser_network.block_public_browser_websocket(socket))
    assert socket.closed_with == (1008, "Blocked by public network policy")


def test_source_domain_boundary_rejects_suffix_confusion_and_non_http() -> None:
    source = IdealistaSource()

    assert source.is_listing_url("https://www.idealista.com/inmueble/123456/")
    assert source.is_listing_url("https://subdomain.idealista.com/inmueble/123456/")
    assert not source.is_listing_url("https://evilidealista.com/inmueble/123456/")
    assert not source.is_listing_url("https://idealista.com.evil.test/inmueble/123456/")
    assert not source.is_listing_url("https://idealista.com@evil.test/inmueble/123456/")
    assert not source.is_listing_url("ftp://www.idealista.com/inmueble/123456/")

    assert source.is_pagination_url("https://www.idealista.com/alquiler-habitacion/?page=2")
    assert not source.is_pagination_url("https://evilidealista.com/alquiler-habitacion/?page=2")
