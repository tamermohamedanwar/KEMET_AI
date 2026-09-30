from app.services.free_compute_fabric import FreeComputeFabricV1


def test_free_first_blocks_unverified_capacity():
    fabric = FreeComputeFabricV1()
    snapshot = fabric.snapshot([{"provider_id": "free-a", "free": True, "status": "READY", "capabilities": ["VIDEO_GENERATION"]}])
    assert snapshot["ready_provider_count"] == 0
    assert fabric.select(snapshot, "VIDEO_GENERATION")["status"] == "WAITING_FOR_FREE_CAPACITY"


def test_free_capacity_requires_evidence():
    fabric = FreeComputeFabricV1()
    snapshot = fabric.snapshot([{
        "provider_id": "free-a", "free": True, "status": "READY",
        "capabilities": ["VIDEO_GENERATION"], "capacity_evidence": {"queue_depth": 0, "observed_at": 1, "attestation_digest": "att-digest", "attestation": {"ready": True}}, "queue_depth": 0,
    }])
    result = fabric.select(snapshot, "VIDEO_GENERATION")
    assert result["status"] == "FREE_CAPACITY_READY"
    assert result["selected_provider"]["provider_id"] == "free-a"


def test_capacity_without_worker_attestation_is_not_ready():
    fabric = FreeComputeFabricV1()
    snapshot = fabric.snapshot([{
        "provider_id": "free-a", "free": True, "status": "READY",
        "capabilities": ["VIDEO_GENERATION"], "capacity_evidence": {"queue_depth": 0, "observed_at": 1, "attestation_digest": "x"}, "queue_depth": 0,
    }])
    assert snapshot["ready_provider_count"] == 0
    assert fabric.select(snapshot, "VIDEO_GENERATION")["status"] == "WAITING_FOR_FREE_CAPACITY"


def test_paid_provider_never_selected_by_free_first():
    fabric = FreeComputeFabricV1()
    snapshot = fabric.snapshot([{
        "provider_id": "paid-a", "free": False, "status": "READY",
        "capabilities": ["VIDEO_GENERATION"], "capacity_evidence": {"queue_depth": 0}, "queue_depth": 0,
    }])
    assert fabric.select(snapshot, "VIDEO_GENERATION")["status"] == "WAITING_FOR_FREE_CAPACITY"


def test_cost_classification_is_truthful():
    fabric = FreeComputeFabricV1()
    assert fabric.classify_cost({"free": True}) == "FREE"
    assert fabric.classify_cost({"free": True, "quota_limited": True}) == "FREE_WITH_CAPACITY_LIMIT"
    assert fabric.classify_cost({"self_hosted": True, "free": True}) == "SELF_HOSTED"
    assert fabric.classify_cost({"free": False}) == "PAID"


def test_snapshot_records_cost_classification():
    fabric = FreeComputeFabricV1()
    snapshot = fabric.snapshot([{"provider_id": "free-a", "free": True, "quota_limited": True}])
    assert snapshot["providers"][0]["cost_classification"] == "FREE_WITH_CAPACITY_LIMIT"
