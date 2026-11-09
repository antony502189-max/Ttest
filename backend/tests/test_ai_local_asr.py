import asyncio
import io
import sys
import wave
from pathlib import Path

import pytest

from app.services.ai_local_asr import LocalPCMTranscriber, validate_pcm


def pcm(*, rate=16000, channels=1, width=2, frames=3200):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((channels, width, rate, 0, "NONE", "not compressed"))
        output.writeframes(b"\0"*(frames*width*channels))
    return buffer.getvalue()


@pytest.mark.parametrize("changes", [{"rate":48000}, {"channels":2}, {"width":1}, {"frames":1599}, {"frames":240001}])
def test_noncanonical_or_unbounded_media_rejected(changes):
    with pytest.raises(ValueError, match="VOICE_AUDIO_INVALID"):
        validate_pcm(pcm(**changes))


def test_only_complete_canonical_pcm_is_accepted_without_decoding_codecs():
    validate_pcm(pcm())
    validate_pcm(pcm(frames=240000))
    value = pcm()
    for invalid in (value[:-1], value+b"junk", b"https://127.0.0.1/private", b"OggS"+value,
                    value[:20]+b"\x03\0"+value[22:], value[:36]+b"LIST"+value[40:]):
        with pytest.raises((ValueError, wave.Error)):
            validate_pcm(invalid)


@pytest.mark.asyncio
async def test_timeout_kills_real_child_and_releases_slot(tmp_path, monkeypatch):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path, seconds=.1)
    spawn = asyncio.create_subprocess_exec
    children = []
    async def sleeper(*_args, **kwargs):
        process = await spawn(sys.executable, "-c", "import time; time.sleep(30)", **kwargs)
        children.append(process)
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", sleeper)
    for _ in range(2):
        with pytest.raises(TimeoutError):
            await asr.transcribe(pcm(), "audio/wav")
        assert children[-1].returncode is not None and not asr.lock.locked()


@pytest.mark.asyncio
async def test_cancel_kills_real_child_and_overlapping_asr_fails_closed(tmp_path, monkeypatch):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path)
    spawn = asyncio.create_subprocess_exec
    started = asyncio.Event()
    children = []
    async def sleeper(*_args, **kwargs):
        process = await spawn(sys.executable, "-c", "import time; time.sleep(30)", **kwargs)
        children.append(process); started.set()
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", sleeper)
    task = asyncio.create_task(asr.transcribe(pcm(), "audio/wav"))
    await asyncio.wait_for(started.wait(), 5)
    with pytest.raises(ValueError, match="LOCAL_ASR_BUSY"):
        await asr.transcribe(pcm(), "audio/wav")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert children[0].returncode is not None and not asr.lock.locked()


@pytest.mark.asyncio
async def test_maximum_pcm_flushes_stdin_eof_without_pipe_deadlock(tmp_path, monkeypatch):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path)
    spawn = asyncio.create_subprocess_exec
    async def reader(*_args, **kwargs):
        return await spawn(sys.executable, "-c", "import sys,json; data=sys.stdin.buffer.read(); assert len(data)==480044; print(json.dumps('fixture transcript'))", **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", reader)
    assert await asr.transcribe(pcm(frames=240000), "audio/wav") == "fixture transcript"
