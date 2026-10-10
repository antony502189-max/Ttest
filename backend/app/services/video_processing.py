from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException

from ..core.config import get_settings

SUPPORTED_VIDEO_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".asf",
    ".f4v",
    ".flv",
    ".mxf",
    ".vob",
    ".wmv",
    ".avi",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogv",
    ".ts",
    ".webm",
}
VIDEO_TRANSCODE_TIMEOUT_SECONDS = 480


def is_supported_video_upload(content_type: str, filename: str = "") -> bool:
    normalized_type = (content_type or "").split(";", 1)[0].strip().casefold()
    suffix = Path(filename or "").suffix.casefold()
    return normalized_type.startswith("video/") or suffix in SUPPORTED_VIDEO_EXTENSIONS


@dataclass(frozen=True)
class PreparedVideo:
    content: bytes
    width: int
    height: int
    duration_seconds: float


def _probe(path: Path) -> tuple[int, int, float]:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,duration:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(422, "Video could not be inspected") from exc
    if result.returncode != 0:
        raise HTTPException(415, "Invalid video file")
    try:
        payload = json.loads(result.stdout)
        stream = (payload.get("streams") or [])[0]
        width = int(stream["width"])
        height = int(stream["height"])
        raw_duration = stream.get("duration") or (payload.get("format") or {}).get("duration")
        if raw_duration is None:
            raise ValueError("missing video duration")
        duration = float(raw_duration)
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(415, "Invalid video file") from exc
    if width < 1 or height < 1 or not math.isfinite(duration) or duration <= 0:
        raise HTTPException(415, "Invalid video file")
    return width, height, duration


def prepare_video(content: bytes | BinaryIO, content_type: str, filename: str = "") -> PreparedVideo:
    settings = get_settings()
    if not is_supported_video_upload(content_type, filename):
        raise HTTPException(415, "A valid video file is required")

    suffix = Path(filename or "").suffix.casefold()
    if suffix not in SUPPORTED_VIDEO_EXTENSIONS:
        suffix = ".video"
    with tempfile.TemporaryDirectory(prefix="listing-video-") as temp_dir:
        source = Path(temp_dir) / f"source{suffix}"
        target = Path(temp_dir) / "normalized.mp4"
        if isinstance(content, bytes):
            if not content or len(content) > settings.max_video_upload_bytes:
                raise HTTPException(413, "Video is too large")
            source.write_bytes(content)
        else:
            total_bytes = 0
            with source.open("wb") as destination:
                while chunk := content.read(1024 * 1024):
                    total_bytes += len(chunk)
                    if total_bytes > settings.max_video_upload_bytes:
                        raise HTTPException(413, "Video is too large")
                    destination.write(chunk)
            if total_bytes == 0:
                raise HTTPException(413, "Video is too large")

        _, _, duration = _probe(source)
        if duration > float(settings.max_video_duration_seconds):
            raise HTTPException(
                422,
                f"Video must be {settings.max_video_duration_seconds} seconds or shorter",
            )

        scale_filter = (
            f"scale=w='min(iw,{settings.max_video_dimension})':"
            f"h='min(ih,{settings.max_video_dimension})':"
            "force_original_aspect_ratio=decrease:force_divisible_by=2"
        )
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-vf",
                    scale_filter,
                    "-filter_threads",
                    "2",
                    "-c:v",
                    "libx264",
                    "-threads",
                    "2",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "26",
                    "-maxrate",
                    "4M",
                    "-bufsize",
                    "8M",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ac",
                    "2",
                    "-ar",
                    "44100",
                    "-movflags",
                    "+faststart",
                    str(target),
                ],
                capture_output=True,
                text=True,
                timeout=VIDEO_TRANSCODE_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HTTPException(422, "Video processing failed") from exc
        if result.returncode != 0 or not target.exists():
            raise HTTPException(422, "Video processing failed")
        if target.stat().st_size > settings.max_video_output_bytes:
            raise HTTPException(422, "Normalized video is too large")

        width, height, normalized_duration = _probe(target)
        if normalized_duration > float(settings.max_video_duration_seconds):
            raise HTTPException(
                422,
                f"Video must be {settings.max_video_duration_seconds} seconds or shorter",
            )
        return PreparedVideo(
            content=target.read_bytes(),
            width=width,
            height=height,
            duration_seconds=normalized_duration,
        )
