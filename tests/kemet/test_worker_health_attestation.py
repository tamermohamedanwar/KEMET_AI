from app.services.worker_health_attestation import worker_health_attestation


class FakeResponse:
    status_code = 200
    def __init__(self, body): self.body = body
    def json(self): return self.body


def test_attestation_accepts_fresh_matching_worker(monkeypatch):
    body = {"status":"READY","worker_id":"w1","provider_id":"wan2_2_remote","reported_at":1000,
            "capabilities":["VIDEO_GENERATION"],
            "capacity":{"in_flight":0,"max_concurrency":2,"queue_depth":0,"max_queue_depth":4,"attestation":{"ready":True}},
            "hardware":{"gpu":"NVIDIA RTX","vram_mb":24576,"compute_runtime":"CUDA"},
            "pricing":{"free":True},"license":{"commercial_use":True}}
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body))
    out = worker_health_attestation.attest(worker_id="w1", provider_id="wan2_2_remote", endpoint="https://worker.example", expected_capabilities=["VIDEO_GENERATION"], now=1040)
    assert out["ready"] is True
    assert all(out["checks"].values())
    assert out["trust"] == "untrusted"


def test_attestation_blocks_stale_or_full_worker(monkeypatch):
    body = {"status":"READY","worker_id":"w1","provider_id":"wan2_2_remote","reported_at":900,
            "capabilities":["VIDEO_GENERATION"],
            "capacity":{"in_flight":2,"max_concurrency":2,"queue_depth":4,"max_queue_depth":4,"attestation":{"ready":True}},
            "hardware":{"gpu":"NVIDIA RTX","vram_mb":24576,"compute_runtime":"CUDA"},
            "pricing":{"free":True},"license":{"commercial_use":True}}
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body))
    out = worker_health_attestation.attest(worker_id="w1", provider_id="wan2_2_remote", endpoint="https://worker.example", expected_capabilities=["VIDEO_GENERATION"], now=1000)
    assert out["ready"] is False
    assert out["checks"]["freshness_ok"] is False
    assert out["checks"]["capacity_ok"] is False


def test_attestation_blocks_missing_hardware_capacity_attestation_or_license(monkeypatch):
    body = {"status":"READY","worker_id":"w1","provider_id":"wan2_2_remote","reported_at":1000,
            "capabilities":["VIDEO_GENERATION"],
            "capacity":{"in_flight":0,"max_concurrency":2,"queue_depth":0,"max_queue_depth":4}}
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body))
    out = worker_health_attestation.attest(worker_id="w1", provider_id="wan2_2_remote", endpoint="https://worker.example", expected_capabilities=["VIDEO_GENERATION"], now=1040)
    assert out["ready"] is False
    assert out["checks"]["hardware_ok"] is False
    assert out["checks"]["attestation_ok"] is False
    assert out["checks"]["license_ok"] is False


def test_attestation_blocks_non_commercial_license(monkeypatch):
    body = {"status":"READY","worker_id":"w1","provider_id":"wan2_2_remote","reported_at":1000,
            "capabilities":["VIDEO_GENERATION"],
            "capacity":{"in_flight":0,"max_concurrency":2,"queue_depth":0,"max_queue_depth":4,"attestation":{"ready":True}},
            "hardware":{"gpu":"NVIDIA RTX","vram_mb":24576,"compute_runtime":"CUDA"},
            "pricing":{"free":True},"license":{"commercial_use":False}}
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body))
    out = worker_health_attestation.attest(worker_id="w1", provider_id="wan2_2_remote", endpoint="https://worker.example", expected_capabilities=["VIDEO_GENERATION"], now=1040)
    assert out["ready"] is False
    assert out["checks"]["license_ok"] is False


def test_registry_attest_refreshes_router_capacity(monkeypatch):
    from app.services.remote_worker_registry import remote_worker_registry
    body = {"status":"READY","worker_id":"w1","provider_id":"wan2_2_remote","reported_at":1000,
            "capabilities":["VIDEO_GENERATION"],
            "capacity":{"in_flight":0,"max_concurrency":2,"queue_depth":0,"max_queue_depth":4,"attestation":{"ready":True}},
            "hardware":{"gpu":"NVIDIA RTX","vram_mb":24576,"compute_runtime":"CUDA"},
            "pricing":{"free":True},"license":{"commercial_use":True}}
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body))
    snapshot = remote_worker_registry.register(worker_id="w1", provider_id="wan2_2_remote", capabilities=["VIDEO_GENERATION"], endpoint="https://worker.example", configured=True)
    refreshed = remote_worker_registry.attest(snapshot=snapshot, now=1040)
    provider = remote_worker_registry.as_router_provider(refreshed)
    assert refreshed["healthy"] is True
    assert refreshed["available"] is True
    assert provider["capacity"]["max_concurrency"] == 2
