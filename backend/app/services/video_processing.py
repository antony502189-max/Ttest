from __future__ import annotations

import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from ..core.config import get_settings

SUPPORTED_VIDEO_MIME_TYPES = {"video/mp4", "video/quicktime", "video/x-m4v"}


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
                "stream=width,height,duration:format=duration,format_name",
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
        format_names = set((payload.get("format") or {}).get("format_name", "").split(","))
        if not format_names.intersection({"mov", "mp4", "m4v"}):
            raise ValueError("unsupported video container")
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


def prepare_video(content: bytes, content_type: str) -> PreparedVideo:
    settings = get_settings()
    if content_type not in SUPPORTED_VIDEO_MIME_TYPES:
        raise HTTPException(415, "Only MP4 and MOV videos are supported")

    suffix = ".mov" if content_type == "video/quicktime" else ".mp4"
    with tempfile.TemporaryDirectory(prefix="listing-video-") as temp_dir:
        source = Path(temp_dir) / f"source{suffix}"
        target = Path(temp_dir) / "normalized.mp4"
        source.write_bytes(content)

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
                timeout=90,
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
