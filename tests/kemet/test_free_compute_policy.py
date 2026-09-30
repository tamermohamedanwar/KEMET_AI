from app.services.free_compute_policy import evaluate


def test_free_provider_requires_real_capacity_and_quota():
    assert evaluate("hf_zerogpu", configured=True, healthy=True, available=True, free_tier=True, quota_remaining=True).eligible
    assert not evaluate("hf_zerogpu", configured=True, healthy=True, available=True, free_tier=True, quota_remaining=False).eligible
    assert not evaluate("paid_gpu", configured=True, healthy=True, available=True, free_tier=False, quota_remaining=True).eligible
