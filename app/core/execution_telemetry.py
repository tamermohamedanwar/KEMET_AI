from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


class ExecutionTelemetry:
    VERSION = "1.0"

    def __init__(self) -> None:
        self.tracer = trace.get_tracer("kemet.execution", self.VERSION)

    @contextmanager
    def span(self, name: str, *, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
        started = time.perf_counter()
        with self.tracer.start_as_current_span(name) as current:
            for key, value in (attributes or {}).items():
                if value is not None:
                    current.set_attribute(str(key), _attribute_value(value))
            try:
                yield current
            except Exception as exc:
                current.record_exception(exc)
                current.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            finally:
                current.set_attribute("kemet.duration_ms", int((time.perf_counter() - started) * 1000))

    def event(self, name: str, *, attributes: dict[str, Any] | None = None) -> None:
        span = trace.get_current_span()
        if span.is_recording():
            span.add_event(name, attributes={k: _attribute_value(v) for k, v in (attributes or {}).items() if v is not None})


def _attribute_value(value: Any) -> str | bool | int | float:
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


execution_telemetry = ExecutionTelemetry()
