"""Exercise the actual HTTPX pool with a synthetic socket; never send network traffic."""
import asyncio

import httpcore
import httpx
import pytest

from app.core import public_http


class SyntheticStream(httpcore.AsyncNetworkStream):
    def __init__(self):
        self.writes = []
        self.sni = None
        self.body = b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok'

    async def read(self, max_bytes, timeout=None):
        body, self.body = self.body, b''
        return body

    async def write(self, buffer, timeout=None):
        self.writes.append(buffer)

    async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
        self.sni = server_hostname
        return self

    async def aclose(self):
        pass

    def get_extra_info(self, info):
        return ('8.8.8.8', 443) if info == 'server_addr' else None


async def test_rebinding_is_rejected_before_socket_open_or_http_write(monkeypatch):
    resolutions = iter([{'8.8.8.8'}, {'127.0.0.1'}])

    async def resolve(*_):
        return next(resolutions)

    async def connect(*_, **__):
        pytest.fail('A private socket must never be opened')

    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    monkeypatch.setattr(public_http.AutoBackend, 'connect_tcp', connect)
    async with public_http.PublicNetworkAsyncClient() as client:
        with pytest.raises(httpx.ConnectError, match='non-public'):
            await client.get('http://rebind.example.test/synthetic')


async def test_validated_literal_keeps_original_tls_sni_and_host(monkeypatch):
    stream = SyntheticStream()
    connected = []

    async def resolve(*_):
        return {'8.8.8.8'}

    async def connect(_self, host, port, **kwargs):
        connected.append((host, port))
        return stream

    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    monkeypatch.setattr(public_http.AutoBackend, 'connect_tcp', connect)
    async with public_http.PublicNetworkAsyncClient() as client:
        result = await client.get('https://images.example.test/synthetic')
    assert result.text == 'ok'
    assert connected == [('8.8.8.8', 443)]
    assert stream.sni == 'images.example.test'
    assert b'Host: images.example.test\r\n' in b''.join(stream.writes)


@pytest.mark.parametrize('addresses', [{'8.8.8.8', '10.0.0.1'}, {'::ffff:127.0.0.1'}, {'169.254.169.254'}, {'::1'}])
async def test_all_answers_must_be_public_before_connecting(monkeypatch, addresses):
    async def resolve(*_):
        return addresses

    async def connect(*_, **__):
        pytest.fail('Mixed/private DNS results must not open any socket')

    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    monkeypatch.setattr(public_http.AutoBackend, 'connect_tcp', connect)
    with pytest.raises(httpx.ConnectError):
        await public_http.PublicNetworkBackend().connect_tcp('synthetic.example.test', 443, timeout=1)


async def test_dns_resolution_is_bounded_by_connect_timeout(monkeypatch):
    async def resolve(*_):
        await asyncio.sleep(1)
        return {'8.8.8.8'}

    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    with pytest.raises(httpcore.ConnectTimeout):
        await public_http.PublicNetworkBackend().connect_tcp('synthetic.example.test', 443, timeout=0.01)


async def test_explicit_proxy_cannot_bypass_guard():
    with pytest.raises(ValueError, match='guarded connection policy'):
        public_http.PublicNetworkAsyncClient(proxy='http://127.0.0.1:8080')


async def test_request_preflight_dns_is_also_bounded(monkeypatch):
    async def resolve(*_):
        await asyncio.sleep(1)
        return {'8.8.8.8'}

    monkeypatch.setattr(public_http, 'resolve_host', resolve)
    monkeypatch.setattr(public_http, 'PUBLIC_DNS_TIMEOUT_SECONDS', 0.01)
    async with public_http.PublicNetworkAsyncClient() as client:
        with pytest.raises(httpx.ConnectError, match='resolve'):
            await client.get('https://synthetic.example.test/no-network')
