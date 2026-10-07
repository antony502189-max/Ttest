from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import video_processing


def test_video_over_sixty_seconds_is_rejected_before_transcode(monkeypatch):
    monkeypatch.setattr(
        video_processing,
        "get_settings",
        lambda: Settings(max_video_duration_seconds=60, max_video_dimension=1920),
    )
    monkeypatch.setattr(video_processing, "_probe", lambda _path: (1280, 720, 60.2))

    with pytest.raises(HTTPException) as error:
        video_processing.prepare_video(b"not-decoded-because-probe-is-mocked", "video/mp4")

    assert error.value.status_code == 422
    assert "60 seconds" in str(error.value.detail)


def test_non_video_without_video_extension_is_rejected():
    with pytest.raises(HTTPException) as error:
        video_processing.prepare_video(b"video", "application/octet-stream", "notes.txt")

    assert error.value.status_code == 415


def test_corrupt_video_is_rejected_by_probe(monkeypatch):
    monkeypatch.setattr(
        video_processing.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout="", stderr="invalid"),
    )
    with pytest.raises(HTTPException) as error:
        video_processing.prepare_video(b"corrupt", "video/mp4")
    assert error.value.status_code == 415


def test_probe_accepts_decodable_webm_container(monkeypatch, tmp_path):
    monkeypatch.setattr(
        video_processing.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"streams":[{"width":640,"height":360,"duration":"10"}],"format":{"format_name":"matroska,webm","duration":"10"}}',
            stderr="",
        ),
    )

    assert video_processing._probe(tmp_path / "video.webm") == (640, 360, 10.0)


def test_empty_phone_mime_is_accepted_by_video_extension(monkeypatch):
    probes = iter([(1920, 1080, 10.0), (1920, 1080, 10.0)])
    monkeypatch.setattr(video_processing, "_probe", lambda _path: next(probes))

    def fake_run(command, **kwargs):
        assert kwargs["timeout"] == video_processing.VIDEO_TRANSCODE_TIMEOUT_SECONDS
        Path(command[-1]).write_bytes(b"normalized-mp4")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(video_processing.subprocess, "run", fake_run)

    prepared = video_processing.prepare_video(b"phone-video", "", "camera.MOV")

    assert prepared.content == b"normalized-mp4"
    assert prepared.duration_seconds == 10.0


def test_video_is_normalized_to_browser_mp4(monkeypatch):
    probes = iter([(1080, 1920, 12.5), (720, 1280, 12.5)])
    monkeypatch.setattr(
        video_processing,
        "get_settings",
        lambda: Settings(max_video_duration_seconds=60, max_video_dimension=1920),
    )
    monkeypatch.setattr(video_processing, "_probe", lambda _path: next(probes))

    seen_command: list[str] = []

    def fake_run(command, **_kwargs):
        seen_command.extend(command)
        Path(command[-1]).write_bytes(b"normalized-mp4")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(video_processing.subprocess, "run", fake_run)

    prepared = video_processing.prepare_video(b"source-video", "video/quicktime")

    assert prepared.content == b"normalized-mp4"
    assert prepared.duration_seconds == 12.5
    assert (prepared.width, prepared.height) == (720, 1280)
    assert "libx264" in seen_command
    assert "yuv420p" in seen_command
    assert "+faststart" in seen_command
    assert seen_command[seen_command.index("-maxrate") + 1] == "4M"
    assert seen_command[seen_command.index("-threads") + 1] == "2"


def test_video_input_over_100_mib_is_rejected_before_probe(monkeypatch):
    monkeypatch.setattr(
        video_processing,
        "get_settings",
        lambda: Settings(max_video_upload_bytes=4),
    )
    monkeypatch.setattr(
        video_processing,
        "_probe",
        lambda _path: (_ for _ in ()).throw(AssertionError("probe must not run")),
    )

    with pytest.raises(HTTPException) as error:
        video_processing.prepare_video(b"12345", "video/mp4")

    assert error.value.status_code == 413


def test_normalized_video_output_is_bounded(monkeypatch):
    monkeypatch.setattr(
        video_processing,
        "get_settings",
        lambda: Settings(max_video_output_bytes=4),
    )
    monkeypatch.setattr(video_processing, "_probe", lambda _path: (640, 360, 10.0))

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"too-large")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(video_processing.subprocess, "run", fake_run)
    with pytest.raises(HTTPException) as error:
        video_processing.prepare_video(b"source", "video/mp4")
    assert error.value.status_code == 422
