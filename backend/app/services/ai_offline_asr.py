"""Synthetic ASR adapter for media/response contracts, not a vendor integration."""
import asyncio
import json
from typing import Protocol

import httpx
from pydantic import Field

from ..schemas.ai_search_quota import StrictContract
from .ai_voice_execution import AudioMedia, VoicePolicy, _bounded


class AudioOutboundGate(Protocol):
    # Explicit local test decision only; production privacy/consent approval
    # and a real transport have no implementation or permissive default here.
    async def approve(self, audio: bytes, media_type: AudioMedia) -> None: ...


class ASRResponse(StrictContract):
    transcript: str = Field(min_length=1, max_length=16_384, repr=False)


class OfflineASR:
    def __init__(self, transport: httpx.MockTransport, policy: VoicePolicy, gate: AudioOutboundGate,
                 *, max_response_bytes: int):
        if not isinstance(transport, httpx.MockTransport):
            raise TypeError("LIVE_ASR_TRANSPORT_DISABLED")
        if type(max_response_bytes) is not int or not 32 <= max_response_bytes <= 1_048_576:
            raise ValueError("explicit bounded ASR response policy required")
        self.transport, self.gate = transport, gate
        self.policy = VoicePolicy.model_validate(policy.model_dump())
        self.max_response_bytes = max_response_bytes

    async def transcribe(self, audio: bytes, media_type: AudioMedia) -> str:
        try:
            return await _bounded(lambda: self._transcribe(audio, media_type), self.policy.asr_budget_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - fixed private failure, no provider body or audio export
            raise ValueError("ASR_UNAVAILABLE") from None

    async def _transcribe(self, audio: bytes, media_type: AudioMedia) -> str:
        if type(audio) is not bytes or not 0 < len(audio) <= self.policy.max_audio_bytes or media_type not in self.policy.media_types:
            raise ValueError("ASR_INPUT_INVALID")
        await self.gate.approve(audio, media_type)
        async with (
            httpx.AsyncClient(transport=self.transport, follow_redirects=False,
                             timeout=self.policy.asr_budget_seconds, trust_env=False) as client,
            client.stream("POST", "https://offline-asr.invalid/transcribe", content=audio,
                          headers={"Content-Type": media_type, "Accept-Encoding": "identity"}) as response,
        ):
            if response.status_code != 200 or response.headers.get("content-encoding", "identity") != "identity":
                raise ValueError("ASR_RESPONSE_INVALID")
            if response.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
                raise ValueError("ASR_RESPONSE_INVALID")
            length = response.headers.get("content-length")
            if length is not None and (not length.isascii() or not length.isdigit() or len(length) > 20
                                       or int(length) > self.max_response_bytes):
                raise ValueError("ASR_RESPONSE_TOO_LARGE")
            if response.is_stream_consumed:
                if len(response.content) > self.max_response_bytes:
                    raise ValueError("ASR_RESPONSE_TOO_LARGE")
                body = bytearray(response.content)
            else:
                body = bytearray()
                async for chunk in response.aiter_raw():
                    if len(body) + len(chunk) > self.max_response_bytes:
                        raise ValueError("ASR_RESPONSE_TOO_LARGE")
                    body.extend(chunk)
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("ASR_RESPONSE_INVALID")
                result[key] = value
            return result
        parsed = json.loads(body, object_pairs_hook=unique)
        transcript = ASRResponse.model_validate(parsed).transcript
        if not transcript.strip() or len(transcript.encode()) > self.policy.max_transcript_bytes:
            raise ValueError("ASR_TRANSCRIPT_INVALID")
        return transcript
