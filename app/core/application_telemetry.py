from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


_SENSITIVE_KEY_NAMES = {
    "authorization", "cookie", "password", "secret", "token", "api_key",
    "client_secret", "access_token", "refresh_token", "database_url",
}


def _safe_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in values.items():
        normalized = str(key).lower().replace("-", "_")
        if any(name in normalized for name in _SENSITIVE_KEY_NAMES):
            safe[str(key)] = "[REDACTED]"
        else:
            safe[str(key)] = _safe_scalar(value)
    return safe


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        fields = getattr(record, "kemet_fields", None)
        if isinstance(fields, dict):
            payload.update(_redact_mapping(fields))
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class ApplicationTelemetry:
    VERSION = "1.0"

    def __init__(self) -> None:
        self.tracer = trace.get_tracer("kemet.application", self.VERSION)
        self.logger = logging.getLogger("kemet.application")

    def configure_logging(self) -> None:
        level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        level = getattr(logging, level_name, logging.INFO)
        self.logger.setLevel(level)
        self.logger.propagate = False
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(JsonLogFormatter())
            self.logger.addHandler(handler)

    def start_request(self, *, method: str, path: str, correlation_id: str):
        span = self.tracer.start_span("kemet.http.request")
        span.set_attribute("http.request.method", method)
        span.set_attribute("url.path", path)
        span.set_attribute("kemet.correlation_id", correlation_id)
        return span, time.perf_counter()

    def finish_request(
        self,
        *,
        span: Any,
        started: float,
        method: str,
        path: str,
        status_code: int,
        correlation_id: str,
    ) -> None:
        duration_ms = (time.perf_counter() - started) * 1000
        span.set_attribute("http.response.status_code", status_code)
        span.set_attribute("kemet.duration_ms", duration_ms)
        if status_code >= 500:
            span.set_status(Status(StatusCode.ERROR, "server_error"))
        span.end()
        self.logger.info(
            "http.request.completed",
            extra={"kemet_fields": {
                "method": method,
                "path": path,
                "status": status_code,
                "duration_ms": round(duration_ms, 3),
                "correlation_id": correlation_id,
            }},
        )

    def record_exception(
        self,
        *,
        span: Any,
        method: str,
        path: str,
        correlation_id: str,
        exception: BaseException,
    ) -> None:
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, type(exception).__name__))
        self.logger.error(
            "http.request.failed",
            extra={"kemet_fields": {
                "method": method,
                "path": path,
                "error_type": type(exception).__name__,
                "correlation_id": correlation_id,
            }},
        )


application_telemetry = ApplicationTelemetry()
