from app import create_app
from hashlib import sha256

from app.services.capability_registry import capability_registry


def test_registry_is_versioned_and_active():
    items = capability_registry.catalog()
    assert capability_registry.VERSION == "1.2"
    assert items
    assert all(item["lifecycle"] == "active" for item in items)


def test_capability_contract_contains_governance_and_metrics():
    item = capability_registry.get("kemet.business_insights")
    assert item["registry_version"] == "1.2"
    assert item["version"] == "2.0"
    assert item["metrics"]
    assert item["governance"]["fail_closed"] is True
    assert item["governance"]["external_execution"] is False


def test_unknown_capability_fails_closed():
    assert capability_registry.get("kemet.unknown_action") is None


def test_plan_returns_playbook_without_execution():
    result = capability_registry.plan("kemet.business_insights", {"domain": "marketing"})
    assert result["status"] == "planned"
    assert result["playbook"]["execution"]["mode"] == "governed_sequential"
    assert all(step["policy"]["external_execution"] is False for step in result["playbook"]["steps"])


def test_refund_capability_preserves_approval_gate():
    item = capability_registry.get("kemet.refund_request")
    assert item["governance"]["requires_approval"] is True
    assert item["governance"]["external_execution"] is False


def test_capability_analytics_is_organization_scoped():
    from app.services.capability_analytics import capability_analytics
    app = create_app()
    with app.app_context():
        result = capability_analytics.summary(7)
    assert result["success"] is True
    assert result["organization_id"] == 7
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False


def test_registry_routes_are_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/capabilities" in routes
    assert "/api/bos/capabilities/<path:capability_id>" in routes
    assert "/api/bos/capabilities/<path:capability_id>/plan" in routes
    assert "/api/bos/capabilities/analytics" in routes


def test_lifecycle_filter_rejects_unknown_value():
    try:
        capability_registry.catalog("unknown")
    except ValueError:
        return
    assert False, "invalid lifecycle must fail closed"


def test_self_owned_catalog_is_provider_independent_and_read_only():
    snapshot = capability_registry.self_owned_catalog(7)
    assert snapshot["ownership"] == "KEMET_LOCAL_RUNTIME"
    assert snapshot["governance"]["provider_dependency"] is False
    assert snapshot["governance"]["execution_authority"] is False
    assert snapshot["governance"]["external_execution"] is False
    assert snapshot["media"]
    assert snapshot["compute"]["state"] in {"LOCAL_READY", "CPU_ONLY"}



def _valid_bundle(tmp_path):
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_bytes(b"verified-checkpoint")
    return checkpoint, {
        "model_id": "kemet-test-video",
        "model_version": "1.0.0",
        "model_family": "test-video",
        "modality": "TEXT_TO_VIDEO",
        "checkpoint_uri": str(checkpoint),
        "checkpoint_digest": sha256(checkpoint.read_bytes()).hexdigest(),
        "hardware_requirements": {"vram_gb": 0, "ram_gb": 1, "disk_free_gb": 1},
        "commercial_use": True,
        "license_evidence": {"verified": True, "license": "test-commercial"},
        "benchmark_evidence": [{"success": True, "artifact_digest": "artifact-1"}],
    }


def _valid_runtime():
    return {
        "runtime_id": "kemet-test-runtime",
        "runtime_version": "1.0.0",
        "framework": "test-framework",
        "backend": "cpu",
        "platform": "linux",
        "health_status": "READY",
        "health_evidence": {"verified": True},
        "commercial_use": True,
        "license_evidence": {"verified": True, "license": "test-runtime"},
    }


def test_model_runtime_admission_is_ready_only_with_integrity_license_hardware_runtime_and_benchmark(tmp_path):
    checkpoint, bundle = _valid_bundle(tmp_path)
    hardware = {"architecture": "aarch64", "ram_gb": 4, "disk_free_gb": 50, "vram_gb": [], "cuda": {"available": False}}
    bundle["hardware_requirements"]["architecture"] = "aarch64"
    out = capability_registry.admit_model_runtime(bundle=bundle, runtime=_valid_runtime(), hardware=hardware)
    assert out["status"] == "READY"
    assert out["model"]["provider_id"] is None
    assert out["governance"]["provider_independent"] is True


def test_model_runtime_admission_fails_closed_on_checkpoint_digest(tmp_path):
    checkpoint, bundle = _valid_bundle(tmp_path)
    bundle["checkpoint_digest"] = "0" * 64
    out = capability_registry.admit_model_runtime(bundle=bundle, runtime=_valid_runtime())
    assert out["status"] == "BLOCKED"
    assert "checkpoint_digest_mismatch" in out["failures"]


def test_model_runtime_admission_requires_commercial_license_and_runtime_health(tmp_path):
    checkpoint, bundle = _valid_bundle(tmp_path)
    bundle["commercial_use"] = False
    runtime = _valid_runtime()
    runtime["health_status"] = "UNKNOWN"
    out = capability_registry.admit_model_runtime(bundle=bundle, runtime=runtime)
    assert out["status"] == "BLOCKED"
    assert "model_commercial_license_unverified" in out["failures"]
    assert "runtime_health_unverified" in out["failures"]


def test_model_runtime_admission_blocks_hardware_mismatch(tmp_path):
    checkpoint, bundle = _valid_bundle(tmp_path)
    bundle["hardware_requirements"]["vram_gb"] = 24
    hardware = {"architecture": "aarch64", "ram_gb": 4, "disk_free_gb": 50, "vram_gb": [], "cuda": {"available": False}}
    out = capability_registry.admit_model_runtime(bundle=bundle, runtime=_valid_runtime(), hardware=hardware)
    assert out["status"] == "BLOCKED"
    assert "vram_insufficient" in out["failures"]
