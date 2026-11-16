"""Bounded local PCM transcription. Audio never goes to an external ASR vendor."""
import asyncio
import io
import json
import wave
from contextlib import suppress
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
    def __init__(self, *, python: Path, model: Path, seconds: float = 8,
                 prewarm: bool = False, prepare_seconds: float = 15):
        if (not python.is_file() or not (model/"model.bin").is_file() or not 0 < seconds <= 18
                or type(prewarm) is not bool or not 0 < prepare_seconds <= 15):
            raise ValueError("LOCAL_ASR_ASSETS_REQUIRED")
        self.python, self.model, self.seconds = python, model, seconds
        self.prewarm, self.prepare_seconds = prewarm, prepare_seconds
        self.lock = asyncio.Lock()
        self._warm: asyncio.Task[asyncio.subprocess.Process] | None = None
        self._active: asyncio.subprocess.Process | None = None
        self._closed = False

    async def _spawn(self, *, prepared: bool = False) -> asyncio.subprocess.Process:
        return await asyncio.create_subprocess_exec(str(self.python), str(Path(__file__).with_name("ai_local_asr_worker.py")),
            str(self.model), *(["--prewarm"] if prepared else []),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=16384,
            # Match the two-CPU model budget while keeping NumPy imports bounded.
            env={"PATH": "/usr/bin:/bin", "HF_HUB_OFFLINE": "1", "OMP_NUM_THREADS": "2",
                 "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "1"})

    @staticmethod
    async def _dispose(process: asyncio.subprocess.Process) -> None:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
        await process.wait()

    async def _prepare(self) -> asyncio.subprocess.Process:
        process = None
        try:
            async with asyncio.timeout(self.prepare_seconds):
                process = await self._spawn(prepared=True)
                assert process.stdout is not None
                if await process.stdout.readline() != b"ASR_READY\n" or process.returncode is not None:
                    raise ValueError("LOCAL_ASR_UNAVAILABLE")
            return process
        except BaseException:
            if process is not None:
                await self._dispose(process)
            raise

    def _schedule(self) -> asyncio.Task[asyncio.subprocess.Process] | None:
        if self.prewarm and not self._closed and self._warm is None:
            self._warm = asyncio.create_task(self._prepare())
            # Record a preparation failure without an unobserved-task warning.
            # The next caller still sees the failed task and cannot use it.
            self._warm.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        return self._warm

    async def start(self) -> None:
        if self._closed:
            raise ValueError("LOCAL_ASR_UNAVAILABLE")
        task = self._schedule()
        if task is not None:
            await asyncio.shield(task)

    async def close(self) -> None:
        self._closed = True
        task, self._warm = self._warm, None
        if task is not None:
            if not task.done():
                task.cancel()
            try:
                process = await task
            except (asyncio.CancelledError, ValueError, OSError, TimeoutError):
                pass
            else:
                await self._dispose(process)
        if self._active is not None:
            await self._dispose(self._active)

    async def transcribe(self, audio: bytes, media_type: str) -> str:
        if media_type != "audio/wav":
            raise ValueError("VOICE_MEDIA_INVALID")
        validate_pcm(audio)
        if self._closed:
            raise ValueError("LOCAL_ASR_UNAVAILABLE")
        if self.lock.locked():
            raise LocalASRBusy("LOCAL_ASR_BUSY")
        async with self.lock:
            process = None
            try:
                if self.prewarm:
                    task = self._schedule()
                    if task is None or not task.done():
                        # No audio enters a process that is still loading public
                        # weights. Capacity rejection does not spend a search.
                        raise LocalASRBusy("LOCAL_ASR_BUSY")
                    self._warm = None
                    try:
                        process = task.result()
                    except (ValueError, OSError, TimeoutError):
                        raise LocalASRBusy("LOCAL_ASR_BUSY") from None
                    if process.returncode is not None:
                        raise LocalASRBusy("LOCAL_ASR_BUSY")
                else:
                    process = await self._spawn()
                self._active = process
                async with asyncio.timeout(self.seconds):
                    # Canonical PCM is already bounded. Worker emits only a small
                    # JSON transcript; a broken worker cannot fill parent memory.
                    assert process.stdin is not None and process.stdout is not None
                    process.stdin.write(audio)
                    await process.stdin.drain()
                    process.stdin.close()
                    body = await process.stdout.read(12003)
                    await process.wait()
                    if process.returncode != 0 or len(body) > 12002:
                        raise ValueError("LOCAL_ASR_UNAVAILABLE")
                    value = json.loads(body)
                    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
                        raise ValueError("VOICE_TRANSCRIPT_INVALID")
                    return value
            finally:
                if process is not None:
                    await self._dispose(process)
                self._active = None
                # A fresh process loads only public weights. Every process that
                # received audio has exited before another one is prepared.
                self._schedule()
