from app.services.local_acceleration_capability import local_acceleration_capability


def test_local_acceleration_probe_is_read_only_and_fail_safe():
    snapshot = local_acceleration_capability.snapshot()
    assert snapshot["capability_id"] == "local_ai_acceleration"
    assert snapshot["execution_authority"] == "none"
    assert snapshot["policy"]["read_only_probe"] is True
    assert snapshot["policy"]["no_secret_discovery"] is True
    assert snapshot["policy"]["no_mandatory_runtime_dependency"] is True
    assert snapshot["cuda"]["available"] in (True, False)


def test_local_acceleration_does_not_claim_cuda_without_runtime_evidence():
    snapshot = local_acceleration_capability.snapshot()
    if not snapshot["nvidia_smi"] and not snapshot["cuda"]["available"]:
        assert snapshot["cuda"]["device_count"] == 0
        assert snapshot["cuda"]["device_names"] == []
