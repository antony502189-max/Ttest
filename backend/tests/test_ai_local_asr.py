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
    monkeypatch.setenv("ASR_PRIVATE_SENTINEL", "must-not-enter-worker")
    async def reader(*_args, **kwargs):
        assert kwargs["env"] == {"PATH": "/usr/bin:/bin", "HF_HUB_OFFLINE": "1", "OMP_NUM_THREADS": "2",
            "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "1"}
        return await spawn(sys.executable, "-c", "import sys,json; data=sys.stdin.buffer.read(); assert len(data)==480044; print(json.dumps('fixture transcript'))", **kwargs)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", reader)
    assert await asr.transcribe(pcm(frames=240000), "audio/wav") == "fixture transcript"


@pytest.mark.asyncio
async def test_prepared_public_worker_receives_only_one_recording_then_exits(tmp_path, monkeypatch):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path, prewarm=True)
    spawn = asyncio.create_subprocess_exec
    children = []
    async def worker(*args, **kwargs):
        assert args[-1] == "--prewarm"
        child = await spawn(sys.executable, "-c",
            r"import sys,json;sys.stdout.buffer.write(b'ASR_READY\n');sys.stdout.buffer.flush();raw=sys.stdin.buffer.read();print(json.dumps(str(len(raw))),flush=True)", **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(asyncio, "create_subprocess_exec", worker)
    try:
        await asr.start()
        first = children[0]
        assert first.returncode is None and not first.stdin.is_closing()
        with pytest.raises(ValueError, match="VOICE_AUDIO_INVALID"):
            await asr.transcribe(b"not audio", "audio/wav")
        assert await asr.transcribe(pcm(), "audio/wav") == str(44+3200*2)
        assert first.returncode == 0
        await asr.start()
        second = children[1]
        assert second.pid != first.pid
        assert await asr.transcribe(pcm(frames=4000), "audio/wav") == str(44+4000*2)
        assert second.returncode == 0
    finally:
        await asr.close()
    assert all(child.returncode is not None for child in children)


@pytest.mark.asyncio
async def test_prepared_timeout_and_cancel_destroy_audio_worker_and_release_slot(tmp_path, monkeypatch):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path, seconds=.1, prewarm=True)
    spawn = asyncio.create_subprocess_exec
    children = []
    async def worker(*_args, **kwargs):
        child = await spawn(sys.executable, "-c",
            r"import sys,time;sys.stdout.buffer.write(b'ASR_READY\n');sys.stdout.buffer.flush();sys.stdin.buffer.read();time.sleep(10)", **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(asyncio, "create_subprocess_exec", worker)
    try:
        with pytest.raises(ValueError, match="LOCAL_ASR_BUSY"):
            await asr.transcribe(pcm(), "audio/wav")
        await asr.start()
        with pytest.raises(TimeoutError):
            await asr.transcribe(pcm(), "audio/wav")
        assert children[0].returncode is not None and not asr.lock.locked()
        await asr.start()
        task = asyncio.create_task(asr.transcribe(pcm(), "audio/wav"))
        async def locked():
            while not asr.lock.locked():
                await asyncio.sleep(0)
        await asyncio.wait_for(locked(), 1)
        with pytest.raises(ValueError, match="LOCAL_ASR_BUSY"):
            await asr.transcribe(pcm(), "audio/wav")
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert children[1].returncode is not None and not asr.lock.locked()
    finally:
        await asr.close()
    assert all(child.returncode is not None for child in children)


@pytest.mark.asyncio
@pytest.mark.parametrize("code, error", [
    ("import time;time.sleep(10)", TimeoutError),
    ("import sys,time;print('WRONG_READY',flush=True);time.sleep(10)", ValueError),
])
async def test_preparation_requires_bounded_exact_readiness_and_leaves_no_child(tmp_path, monkeypatch, code, error):
    (tmp_path/"model.bin").write_bytes(b"synthetic-test-model-not-used")
    asr = LocalPCMTranscriber(python=Path(sys.executable), model=tmp_path, prewarm=True, prepare_seconds=.2)
    spawn = asyncio.create_subprocess_exec
    children = []
    async def worker(*_args, **kwargs):
        child = await spawn(sys.executable, "-c", code, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(asyncio, "create_subprocess_exec", worker)
    try:
        with pytest.raises(error):
            await asr.start()
    finally:
        await asr.close()
    assert children and all(child.returncode is not None for child in children)
