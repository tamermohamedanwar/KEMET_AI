from app.core.federation.capability_federation import CapabilityFederation


def test_capability_snapshot_is_deterministic():
    service = CapabilityFederation()
    first = service.snapshot(configured_only=False)
    second = service.snapshot(configured_only=False)
    assert first == second
    assert first["capabilities"]
    assert len(first["fingerprint"]) == 64


def test_capability_resolution_fails_closed_when_missing():
    service = CapabilityFederation()
    try:
        service.resolve("capability-that-does-not-exist")
    except LookupError as exc:
        assert str(exc) == "capability_unavailable"
    else:
        raise AssertionError("unknown capability must fail closed")


def test_capability_entries_expose_ready_providers():
    snapshot = CapabilityFederation().snapshot(configured_only=False)
    names = {item["capability"] for item in snapshot["capabilities"]}
    assert "research" in names or "coding" in names


def test_route_prefers_verified_configured_provider(monkeypatch):
    from app.core.federation.capability_federation import capability_federation

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = capability_federation.route(
        {"reasoning", "coding"}, verified={"openai", "anthropic"}, preferred=None
    )
    assert result["selected"]["provider_id"] == "openai"
    assert result["candidates"][0]["coverage"] == 2
    assert result["required_capabilities"] == ["coding", "reasoning"]

def test_route_exposes_runtime_provider_state(monkeypatch):
    from app.core.federation.capability_federation import capability_federation

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    result = capability_federation.route(
        {"reasoning", "coding"}, verified={"openai", "anthropic"}, preferred=None
    )
    assert result["selection_policy"] == "capability_coverage_then_priority_then_preference"
    assert result["provider_states"]
    state = result["provider_states"][0]
    assert {"provider_id", "known", "enabled", "execution_ready", "configured", "healthy", "priority"}.issubset(state)
