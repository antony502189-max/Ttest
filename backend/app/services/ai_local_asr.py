"""Bounded local PCM transcription. Audio never goes to an external ASR vendor."""
import asyncio
import io
import json
import wave
from pathlib import Path


class LocalASRBusy(ValueError):
    """A bounded capacity rejection, never an audio recognition failure."""


def validate_pcm(audio: bytes) -> None:
    if type(audio) is not bytes or not 3244 <= len(audio) <= 480_044:
        raise ValueError("VOICE_AUDIO_INVALID")
    # Deliberately accept one canonical PCM WAV, no container codecs, URLs,
    # playlists, extra chunks or decompression before the media bounds.
    if (audio[:4] != b"RIFF" or audio[8:12] != b"WAVE" or audio[12:16] != b"fmt "
            or audio[16:20] != b"\x10\0\0\0" or audio[36:40] != b"data"
            or audio[20:36] != b"\x01\0\x01\0\x80\x3e\0\0\0\x7d\0\0\x02\0\x10\0"
            or int.from_bytes(audio[4:8], "little") != len(audio)-8
            or int.from_bytes(audio[40:44], "little") != len(audio)-44):
        raise ValueError("VOICE_AUDIO_INVALID")
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16000
                    or wav.getcomptype() != "NONE" or not 1600 <= wav.getnframes() <= 240000
                    or wav.getnframes()*2 != len(audio)-44):
                raise ValueError("VOICE_AUDIO_INVALID")
    except (wave.Error, EOFError):
        raise ValueError("VOICE_AUDIO_INVALID") from None


class LocalPCMTranscriber:
    def __init__(self, *, python: Path, model: Path, seconds: float = 8):
        if not python.is_file() or not (model/"model.bin").is_file() or not 0 < seconds <= 8:
            raise ValueError("LOCAL_ASR_ASSETS_REQUIRED")
        self.python, self.model, self.seconds = python, model, seconds
        self.lock = asyncio.Lock()

    async def transcribe(self, audio: bytes, media_type: str) -> str:
        if media_type != "audio/wav":
            raise ValueError("VOICE_MEDIA_INVALID")
        validate_pcm(audio)
        if self.lock.locked():
            raise LocalASRBusy("LOCAL_ASR_BUSY")
        async with self.lock:
            process = await asyncio.create_subprocess_exec(str(self.python), str(Path(__file__).with_name("ai_local_asr_worker.py")),
                str(self.model), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=4096,
                env={"PATH": "/usr/bin:/bin", "HF_HUB_OFFLINE": "1"})
            try:
                async with asyncio.timeout(self.seconds):
                    # Canonical PCM is already bounded. Worker emits only a small
                    # JSON transcript; a broken worker cannot fill parent memory.
                    assert process.stdin is not None and process.stdout is not None
                    process.stdin.write(audio)
                    await process.stdin.drain()
                    process.stdin.close()
                    body = await process.stdout.read(2049)
                    await process.wait()
                    if process.returncode != 0 or len(body) > 2048:
                        raise ValueError("LOCAL_ASR_UNAVAILABLE")
                    value = json.loads(body)
                    if not isinstance(value, str) or not value.strip() or len(value) > 160:
                        raise ValueError("VOICE_TRANSCRIPT_INVALID")
                    return value
            finally:
                if process.returncode is None:
                    process.kill()
                await process.wait()
