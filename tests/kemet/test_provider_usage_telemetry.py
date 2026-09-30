from app.core.provider_usage_telemetry import ProviderUsageTelemetry


def test_usage_telemetry_records_usage_latency_and_observed_cost():
    telemetry = ProviderUsageTelemetry()
    telemetry.record_success("openai", latency_ms=12.5, input_tokens=10,
                              output_tokens=20, total_tokens=30,
                              observed_cost_usd=0.0012)
    item = telemetry.snapshot()[0]
    assert item["requests"] == 1
    assert item["successes"] == 1
    assert item["failures"] == 0
    assert item["total_tokens"] == 30
    assert item["avg_latency_ms"] == 12.5
    assert item["cost_usd_observed"] == 0.0012
    assert item["cost_status"] == "observed"


def test_usage_telemetry_never_invents_cost():
    telemetry = ProviderUsageTelemetry()
    telemetry.record_success("google", latency_ms=5, total_tokens=7)
    item = telemetry.snapshot()[0]
    assert item["cost_usd_observed"] == 0.0
    assert item["cost_observations"] == 0
    assert item["cost_status"] == "not_observed"


def test_usage_telemetry_records_failures_and_resets():
    telemetry = ProviderUsageTelemetry()
    telemetry.record_failure("xai", latency_ms=20)
    assert telemetry.snapshot()[0]["failures"] == 1
    telemetry.reset()
    assert telemetry.snapshot() == []
