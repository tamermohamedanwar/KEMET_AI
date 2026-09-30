from datetime import datetime, timezone

from app.services.production_capacity_evidence_service import production_capacity_evidence_service


def provider(provider_id="video-free", ready=True):
    return {
        "provider_id": provider_id,
        "configured": ready,
        "healthy": ready,
        "available": ready,
        "capabilities": ["VIDEO_GENERATION"],
        "capacity": {"in_flight": 0, "max_concurrency": 1, "queue_depth": 0, "max_queue_depth": 10},
    }


def test_capacity_certification_is_fail_closed_without_free_evidence():
    out = production_capacity_evidence_service.certify(
        organization_id=1,
        providers=[provider()],
        free_providers=[{"provider_id": "piper", "free": True, "status": "UNKNOWN", "capabilities": ["tts"]}],
        required_capabilities=["VIDEO_GENERATION"],
        captured_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    assert out["decision"] == "BLOCKED"
    assert out["free_selection"]["VIDEO_GENERATION"]["status"] == "WAITING_FOR_FREE_CAPACITY"
    assert out["governance"]["external_execution"] is False


def test_capacity_certification_requires_live_provider_capacity():
    out = production_capacity_evidence_service.certify(
        organization_id=1,
        providers=[provider("blocked", False)],
        free_providers=[],
        required_capabilities=["VIDEO_GENERATION"],
        captured_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    assert out["decision"] == "BLOCKED"
    assert out["provider_capacity_gate"]["status"] == "BLOCKED"


def test_verified_free_capacity_is_selectable_without_paid_fallback():
    out = production_capacity_evidence_service.certify(
        organization_id=1,
        providers=[provider("paid-or-live")],
        free_providers=[{
            "provider_id": "free-video", "free": True, "status": "READY",
            "capabilities": ["VIDEO_GENERATION"],
            "capacity_evidence": {
                "queue_depth": 0,
                "observed_at": "2026-09-20T00:00:00+00:00",
                "attestation_digest": "attestation-test-digest",
                "attestation": {"ready": True},
            },
            "queue_depth": 0,
        }],
        required_capabilities=["VIDEO_GENERATION"],
        captured_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    assert out["decision"] == "READY"
    assert out["free_selection"]["VIDEO_GENERATION"]["selected_provider"]["provider_id"] == "free-video"
    assert out["policy"]["no_paid_fallback"] is True


def test_capacity_digest_is_stable_for_same_input():
    kwargs = dict(
        organization_id=1,
        providers=[provider("blocked", False)],
        free_providers=[],
        required_capabilities=["VIDEO_GENERATION"],
        captured_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
    )
    a = production_capacity_evidence_service.certify(**kwargs)
    b = production_capacity_evidence_service.certify(**kwargs)
    assert a["digest"] == b["digest"]
