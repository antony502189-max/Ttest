"""Offline security boundary regressions using synthetic data only."""
import base64
import hashlib
import hmac
import json
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError

from app.api.v1 import payments
from app.core import security
from app.core.config import Settings
from app.core.security import decode_access_token
from app.services import stripe_checkout, video_processing


@pytest.mark.parametrize("production,key,live,test,allowed", [
    (True, "sk_test_synthetic", False, False, False),
    (True, "sk_test_synthetic", False, True, True),
    (False, "sk_test_synthetic", False, False, True),
    (True, "sk_live_synthetic", False, False, False),
    (True, "sk_live_synthetic", True, False, True),
    (True, "", False, False, False),
])
async def test_checkout_policy_runs_before_order_or_provider_work(monkeypatch, production, key, live, test, allowed):
    settings = SimpleNamespace(is_production=production, stripe_secret_key=key,
                               stripe_webhook_secret="whsec_synthetic" if key else "",
                               stripe_live_payments_enabled=live, stripe_test_payments_enabled=test)
    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: settings)
    monkeypatch.setattr(payments, "get_settings", lambda: settings)
    session = SimpleNamespace(scalar=AsyncMock(), commit=AsyncMock())
    provider = AsyncMock()
    monkeypatch.setattr(payments, "finish_creation", provider)
    if allowed:
        stripe_checkout.require_checkout_enabled()
    else:
        with pytest.raises(HTTPException) as error:
            await payments.checkout(session, SimpleNamespace(id=uuid4()), "listing_top", uuid4(),
                                    10, 1000, "TOP", "/mis-anuncios")
        assert error.value.status_code == 503
        session.scalar.assert_not_awaited()
        session.commit.assert_not_awaited()
        provider.assert_not_awaited()


def test_public_test_checkout_is_disabled_by_default():
    assert not Settings(_env_file=None).stripe_test_payments_enabled


def test_invalid_non_ascii_webhook_signature_returns_400(monkeypatch):
    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: SimpleNamespace(stripe_webhook_secret="whsec_synthetic"))
    timestamp = int(time.time())
    with pytest.raises(HTTPException) as error:
        stripe_checkout.verified_stripe_event(b'{}', f't={timestamp},v1=\N{LATIN SMALL LETTER E WITH ACUTE}')
    assert error.value.status_code == 400


def test_signature_rotation_accepts_valid_digest_after_invalid_candidate(monkeypatch):
    monkeypatch.setattr(stripe_checkout, "get_settings", lambda: SimpleNamespace(stripe_webhook_secret="whsec_synthetic"))
    body = json.dumps({"type": "test"}).encode()
    timestamp = int(time.time())
    digest = hmac.new(b"whsec_synthetic", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    assert stripe_checkout.verified_stripe_event(body, f"t={timestamp},v1=invalid,v1={digest}")["type"] == "test"


def test_deeply_nested_jwt_is_an_authentication_failure():
    header = base64.urlsafe_b64encode(b'[' * 2000).rstrip(b'=')
    token = (header + b'.e30.eA').decode()
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_wrong_jwt_algorithm_is_rejected():
    token = jwt.encode({"sub": str(uuid4()), "sid": str(uuid4()), "type": "access", "exp": int(time.time()) + 60},
                       "synthetic-test-secret-at-least-48-characters-for-HS384", algorithm="HS384")
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.parametrize('changes', [
    {'exp': 1}, {'nbf': int(time.time()) + 3600}, {'type': 'refresh'}, {'exp': None},
])
def test_token_time_and_purpose_are_enforced(monkeypatch, changes):
    secret = 'synthetic-token-regression-key-at-least-32-characters'
    monkeypatch.setattr(security, 'get_settings', lambda: SimpleNamespace(jwt_secret=secret))
    claims = {'sub': str(uuid4()), 'sid': str(uuid4()), 'type': 'access', 'exp': int(time.time()) + 60, **changes}
    token = jwt.encode(claims, secret, algorithm='HS256')
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


@pytest.mark.skipif(not shutil.which("ffprobe") or not shutil.which("ffmpeg"), reason="requires actual FFmpeg binaries")
def test_disguised_playlist_cannot_contact_a_local_service(tmp_path):
    contacted = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            contacted.append(self.path)
            self.send_response(404)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        playlist = ("#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXTINF:1,\n"
                    f"http://127.0.0.1:{server.server_port}/synthetic-segment.ts\n#EXT-X-ENDLIST\n").encode()
        with pytest.raises(HTTPException) as error:
            video_processing.prepare_video(playlist, "video/mp4", "camera.mp4")
        assert error.value.status_code == 415
        source = tmp_path / "disguised.mp4"
        source.write_bytes(playlist)
        result = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *video_processing.SAFE_INPUT_OPTIONS,
                                 "-i", str(source), "-f", "null", "-"], capture_output=True, timeout=10, check=False)
        assert result.returncode != 0
        assert contacted == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="requires actual FFmpeg binaries")
@pytest.mark.parametrize("extension,codec", [("mp4", "mpeg4"), ("webm", "libvpx"), ("mov", "mpeg4")])
def test_real_phone_video_containers_still_normalize(tmp_path, extension, codec):
    source = tmp_path / f"synthetic.{extension}"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i", "color=size=64x64:rate=5",
                    "-t", "0.4", "-c:v", codec, str(source)], check=True, capture_output=True, timeout=20)
    prepared = video_processing.prepare_video(source.read_bytes(), "", source.name)
    assert prepared.width == prepared.height == 64
    assert 0 < prepared.duration_seconds <= 1
    assert prepared.content[4:8] == b'ftyp'


def test_production_services_have_bounded_log_rotation():
    import yaml
    compose = yaml.safe_load((Path(__file__).resolve().parents[2] / 'docker-compose.production.yml').read_text())
    for name, service in compose['services'].items():
        assert service['logging'] == {'driver': 'json-file', 'options': {'max-size': '10m', 'max-file': '3'}}, name
