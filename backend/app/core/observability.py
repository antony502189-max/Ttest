from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest  # type: ignore[import-not-found]

from .config import get_settings

REQUESTS = Counter(
    "ttest_http_requests_total",
    "HTTP requests handled by the API",
    ("method", "route", "status"),
)
REQUEST_DURATION = Histogram(
    "ttest_http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
)
UNHANDLED_ERRORS = Counter(
    "ttest_unhandled_errors_total",
    "Unhandled application errors",
    ("exception",),
)
EXTERNAL_IMPORTS = Counter(
    "ttest_external_import_runs_total",
    "External import source runs",
    ("source", "result"),
)
EXTERNAL_IMPORT_DURATION = Histogram(
    "ttest_external_import_duration_seconds",
    "External import source duration",
    ("source",),
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("request_id", "method", "path", "status", "duration_ms", "actor_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter()
        if settings.structured_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
