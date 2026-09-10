from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.execution_telemetry import ExecutionTelemetry


def test_execution_telemetry_records_span_and_event():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    telemetry = ExecutionTelemetry()
    telemetry.tracer = provider.get_tracer("kemet.execution", telemetry.VERSION)
    with telemetry.span("kemet.execution.test", attributes={"kemet.execution_key": "e-1", "kemet.organization_id": 7}):
        telemetry.event("execution.step.completed", attributes={"kemet.step": "validate"})
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "kemet.execution.test"
    assert spans[0].attributes["kemet.execution_key"] == "e-1"
    assert any(event.name == "execution.step.completed" for event in spans[0].events)
