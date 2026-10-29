"""Mock-only synthetic ASR wire contract: no real host, provider or microphone."""
import asyncio
import gzip
import json
import time

import httpx
import pytest

from app.services.ai_offline_asr import ASRResponse, OfflineASR
from app.services.ai_voice_execution import VoicePolicy


class Gate:
    async def approve(self, audio, media):
        assert audio == b"synthetic-audio" and media == "audio/wav"


class RawStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks, self.reads = chunks, 0

    async def __aiter__(self):
        for chunk in self.chunks:
            self.reads += 1
            yield chunk


def adapter(handler, **changes):
    policy = VoicePolicy(media_types=("audio/wav",), max_audio_bytes=1024, max_transcript_bytes=1024,
                         asr_budget_seconds=1.0, intent_budget_seconds=1.0, total_budget_seconds=3.0)
    return OfflineASR(httpx.MockTransport(handler), policy.model_copy(update=changes), Gate(), max_response_bytes=2048)


async def test_media_headers_final_bytes_and_private_response_repr():
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url == "https://offline-asr.invalid/transcribe"
        assert request.headers["content-type"] == "audio/wav"
        assert request.headers["accept-encoding"] == "identity"
        assert request.content == b"synthetic-audio"
        return httpx.Response(200, json={"transcript": "PRIVATE_SYNTHETIC_TRANSCRIPT"})
    assert await adapter(handler).transcribe(b"synthetic-audio", "audio/wav") == "PRIVATE_SYNTHETIC_TRANSCRIPT"
    assert len(calls) == 1
    assert "PRIVATE" not in repr(ASRResponse(transcript="PRIVATE_SYNTHETIC_TRANSCRIPT"))
    with pytest.raises(TypeError, match="LIVE_ASR_TRANSPORT_DISABLED"):
        OfflineASR(httpx.AsyncHTTPTransport(), adapter(handler).policy, Gate(), max_response_bytes=2048)


@pytest.mark.parametrize("body", [b"not JSON", b'{}', b'{"transcript":""}', b'{"transcript":false}',
    b'{"transcript":"one","transcript":"two"}', b'{"transcript":"ok","future":"PRIVATE"}',
    json.dumps({"transcript": "x" * 1025}).encode(), json.dumps({"transcript": "é" * 513}).encode()])
async def test_malformed_transcript_fixed_error_no_retry(body):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})
    with pytest.raises(ValueError, match="^ASR_UNAVAILABLE$"):
        await adapter(handler).transcribe(b"synthetic-audio", "audio/wav")
    assert len(calls) == 1


@pytest.mark.parametrize("headers,status", [({"content-encoding": "gzip"}, 200), ({"content-type": "text/plain"}, 200),
    ({"content-length": "99999999"}, 200), ({"content-length": "-1"}, 200), ({"content-length": "+32"}, 200),
    ({"location": "https://remote.invalid/private"}, 307), ({}, 500)])
async def test_untrusted_headers_compression_and_status_reject_before_body_read(headers, status):
    stream = RawStream([gzip.compress(b"PRIVATE" * 100000)])
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, stream=stream, headers={"content-type": "application/json", **headers})
    with pytest.raises(ValueError, match="^ASR_UNAVAILABLE$"):
        await adapter(handler).transcribe(b"synthetic-audio", "audio/wav")
    assert stream.reads == 0 and len(calls) == 1


async def test_chunked_raw_body_budget_stops_read_and_sync_late_response_is_rejected():
    stream = RawStream([b"x" * 1024] * 5)
    with pytest.raises(ValueError, match="^ASR_UNAVAILABLE$"):
        await adapter(lambda request: httpx.Response(200, stream=stream, headers={"content-type": "application/json"})).transcribe(b"synthetic-audio", "audio/wav")
    assert stream.reads == 3
    def late(request):
        time.sleep(0.03)
        return httpx.Response(200, json={"transcript": "synthetic"})
    with pytest.raises(ValueError, match="^ASR_UNAVAILABLE$"):
        await adapter(late, asr_budget_seconds=0.01).transcribe(b"synthetic-audio", "audio/wav")


async def test_cancel_propagates_without_fixed_error_replacement():
    started = asyncio.Event()
    async def handler(request):
        started.set()
        await asyncio.Event().wait()
    task = asyncio.create_task(adapter(handler).transcribe(b"synthetic-audio", "audio/wav"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
