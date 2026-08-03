import asyncio

import httpx
import pytest

from app.core import public_http


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, *chunks: bytes):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class PeerStream:
    def __init__(self, host: str):
        self.host = host

    def get_extra_info(self, name: str):
        return (self.host, 443) if name == "server_addr" else None


def test_private_literal_address_is_blocked():
    async def verify() -> None:
        with pytest.raises(httpx.ConnectError, match="non-public"):
            await public_http.validate_public_url(httpx.URL("http://127.0.0.1:9000/private"))

    asyncio.run(verify())


def test_service_name_resolving_to_private_network_is_blocked(monkeypatch):
    async def private_resolution(_host: str, _port: int) -> set[str]:
        return {"172.18.0.5"}

    async def verify() -> None:
        monkeypatch.setattr(public_http, "resolve_host", private_resolution)
        with pytest.raises(httpx.ConnectError, match="non-public"):
            await public_http.validate_public_url(httpx.URL("http://minio:9000/object"))

    asyncio.run(verify())


def test_public_resolution_is_allowed(monkeypatch):
    async def public_resolution(_host: str, _port: int) -> set[str]:
        return {"8.8.8.8", "2001:4860:4860::8888"}

    async def verify() -> None:
        monkeypatch.setattr(public_http, "resolve_host", public_resolution)
        await public_http.validate_public_url(httpx.URL("https://images.example.test/photo.webp"))

    asyncio.run(verify())


def test_stream_stops_after_response_budget():
    async def verify() -> None:
        source = ChunkStream(b"1234", b"5678")
        limited = public_http.LimitedAsyncStream(source, 6)
        with pytest.raises(httpx.StreamError, match="size limit"):
            async for _ in limited:
                pass
        assert source.closed

    asyncio.run(verify())


def test_content_length_above_budget_is_rejected(monkeypatch):
    async def verify() -> None:
        monkeypatch.setattr(public_http, "MAX_PUBLIC_RESPONSE_BYTES", 4)
        response = httpx.Response(
            200,
            headers={"content-length": "5"},
            stream=ChunkStream(b"12345"),
        )
        with pytest.raises(httpx.StreamError, match="size limit"):
            await public_http.limit_public_response(response)

    asyncio.run(verify())


def test_compressed_response_is_rejected_before_decompression():
    async def verify() -> None:
        response = httpx.Response(
            200,
            headers={"content-encoding": "gzip"},
            stream=ChunkStream(b"compressed"),
        )
        with pytest.raises(httpx.StreamError, match="Compressed"):
            await public_http.limit_public_response(response)

    asyncio.run(verify())


def test_private_connected_peer_is_blocked_after_dns_validation():
    async def verify() -> None:
        response = httpx.Response(
            200,
            stream=ChunkStream(b"body"),
            extensions={"network_stream": PeerStream("172.18.0.5")},
        )
        with pytest.raises(httpx.ConnectError, match="non-public"):
            await public_http.limit_public_response(response)

    asyncio.run(verify())


def test_guarded_client_forces_identity_encoding_and_ignores_env_proxy():
    async def verify() -> None:
        client = public_http.PublicNetworkAsyncClient(headers={"User-Agent": "test"})
        try:
            assert client.headers["accept-encoding"] == "identity"
            assert client._trust_env is False
        finally:
            await client.aclose()

    asyncio.run(verify())
