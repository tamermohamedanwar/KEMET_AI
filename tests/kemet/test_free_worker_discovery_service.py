from app.services.free_worker_discovery_service import FreeWorkerDiscoveryService


class FakeResponse:
    status_code = 200
    def __init__(self, body): self.body = body
    def json(self): return self.body


def body(**overrides):
    value = {
        "status": "READY", "worker_id": "w1", "provider_id": "free_gpu", "reported_at": 1000,
        "capabilities": ["VIDEO_GENERATION"],
        "capacity": {"in_flight": 0, "max_concurrency": 1, "queue_depth": 0, "max_queue_depth": 4,
                     "attestation": {"ready": True}},
        "hardware": {"gpu": "NVIDIA RTX", "vram_mb": 24576, "compute_runtime": "CUDA"},
        "pricing": {"free": True}, "license": {"commercial_use": True},
    }
    value.update(overrides)
    return value


def candidate(**overrides):
    value = {"worker_id": "w1", "provider_id": "free_gpu", "endpoint": "https://worker.example",
             "capabilities": ["VIDEO_GENERATION"], "free": True}
    value.update(overrides)
    return value


def test_valid_free_worker_is_admitted(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body()))
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate()], now=1040)
    assert out["status"] == "FREE_CAPACITY_READY"
    assert out["ready_count"] == 1
    assert out["results"][0]["provider"]["capacity_evidence"]["attestation"]["ready"] is True


def test_paid_candidate_is_rejected(monkeypatch):
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate(free=False)], now=1040)
    assert out["status"] == "WAITING_FOR_FREE_CAPACITY"
    assert out["results"][0]["error"] == "ValueError"


def test_missing_gpu_vram_runtime_attestation_is_rejected(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body(hardware={})))
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate()], now=1040)
    assert out["status"] == "WAITING_FOR_FREE_CAPACITY"
    assert out["results"][0]["ready"] is False


def test_license_gate_is_fail_closed(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body(license={"commercial_use": False})))
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate()], now=1040)
    assert out["status"] == "WAITING_FOR_FREE_CAPACITY"
    assert out["results"][0]["license_ok"] is False


def test_bad_endpoint_and_missing_capability_are_rejected():
    service = FreeWorkerDiscoveryService()
    out = service.discover(candidates=[candidate(endpoint="http://worker.example"), candidate(capabilities=["IMAGE_GENERATION"])], now=1040)
    assert out["ready_count"] == 0
    assert all(item["ready"] is False for item in out["results"])


def test_unreachable_worker_is_rejected(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("network_failure")))
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate()], now=1040)
    assert out["status"] == "WAITING_FOR_FREE_CAPACITY"
    assert out["results"][0]["ready"] is False


def test_discovery_does_not_grant_execution_authority(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body()))
    out = FreeWorkerDiscoveryService().discover(candidates=[candidate()], now=1040)
    assert out["governance"]["execution_authority"] is False
    assert out["free_compute"]["governance"]["execution_authority"] is False


def test_digest_is_deterministic(monkeypatch):
    monkeypatch.setattr("app.services.worker_health_attestation.governed_request", lambda *a, **k: FakeResponse(body()))
    service = FreeWorkerDiscoveryService()
    a = service.discover(candidates=[candidate()], now=1040)
    b = service.discover(candidates=[candidate()], now=1040)
    assert a["digest"] == b["digest"]
