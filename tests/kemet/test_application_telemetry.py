import logging

from app.core.application_telemetry import ApplicationTelemetry


def test_application_telemetry_records_request_span_and_safe_log(caplog):
    telemetry = ApplicationTelemetry()
    telemetry.logger.setLevel(logging.INFO)
    with caplog.at_level(logging.INFO, logger="kemet.application"):
        span, started = telemetry.start_request(method="GET", path="/api/health", correlation_id="c-1")
        telemetry.finish_request(
            span=span,
            started=started,
            method="GET",
            path="/api/health",
            status_code=200,
            correlation_id="c-1",
        )
    assert any(record.message == "http.request.completed" for record in caplog.records)
    assert any(getattr(record, "kemet_fields", {}).get("correlation_id") == "c-1" for record in caplog.records)


def test_application_telemetry_redacts_sensitive_log_fields():
    telemetry = ApplicationTelemetry()
    telemetry.configure_logging()
    record = telemetry.logger.makeRecord(
        telemetry.logger.name,
        logging.INFO,
        __file__,
        1,
        "sensitive.test",
        (),
        None,
        extra={"kemet_fields": {"api_key": "secret-value", "safe": "ok"}},
    )
    rendered = telemetry.logger.handlers[0].formatter.format(record)
    assert "secret-value" not in rendered
    assert "[REDACTED]" in rendered
    assert '"safe":"ok"' in rendered


def test_application_telemetry_uses_request_correlation_header():
    from app import create_app

    app = create_app()
    with app.test_client() as client:
        response = client.get("/api/health", headers={"X-Request-ID": "request-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "request-123"
    assert response.headers["X-Kemet-Correlation-ID"] == "request-123"
