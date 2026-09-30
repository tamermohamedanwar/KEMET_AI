import pytest

from app.services.remote_worker_registry import remote_worker_registry


def test_registry_emits_router_compatible_provider_snapshot():
    snapshot = remote_worker_registry.register(worker_id="wan2-2-worker", provider_id="wan2_2_remote", capabilities=["VIDEO_GENERATION", "IMAGE_GENERATION"], endpoint="https://worker.example", configured=True, healthy=True, available=True, capacity={"in_flight": 0, "max_concurrency": 2, "queue_depth": 0, "max_queue_depth": 20})
    assert snapshot["schema"] == "kemet.media.remote_worker_registry.v1"
    assert snapshot["trust"] == "untrusted"
    provider = remote_worker_registry.as_router_provider(snapshot)
    assert provider["provider_id"] == "wan2_2_remote"
    assert "VIDEO_GENERATION" in provider["capabilities"]
    assert provider["capacity"]["max_concurrency"] == 2


def test_registry_requires_endpoint():
    with pytest.raises(ValueError, match="worker_endpoint_required"):
        remote_worker_registry.register(worker_id="w", provider_id="p", capabilities=["VIDEO_GENERATION"], endpoint="", configured=True)
