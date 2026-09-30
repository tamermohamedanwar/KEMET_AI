import pytest

from app.services.omnichannel_service import omnichannel_service
from app.services.revenue_workforce_contract import revenue_workforce_contract


@pytest.mark.parametrize(
    "channel,external_user_id,text",
    [
        ("web", "web-user-1", "I need content for my business"),
        ("telegram", "tg-user-1", "محتاج محتوى إعلاني لشركتي"),
        ("whatsapp", "wa-user-1", "I need an advertising campaign"),
    ],
)
def test_cross_channel_golden_path_preserves_one_kemet_contract(
    monkeypatch, channel, external_user_id, text
):
    captured = {}

    def fake_context(**kwargs):
        captured.update(kwargs)
        return {
            "digest": "ctx-digest-1",
            "query_digest": "query-digest-1",
            "sources": [{
                "filename": "commercial-policy.md",
                "chunk_index": 0,
                "content_digest": "source-digest-1",
            }],
            "retrieval": {"excluded": 0},
        }

    monkeypatch.setattr(
        "app.services.revenue_workforce_contract.evidence_backed_context_service.build",
        fake_context,
    )

    message = omnichannel_service.normalize(
        channel,
        external_user_id,
        text,
        organization_id=1,
    )
    routed = omnichannel_service.route(message)
    assert routed["next"] == "kemet_core"
    assert routed["identity"]["organization_id"] == 1
    assert routed["governance"]["external_execution"] is False
    assert routed["governance"]["auto_execute"] is False
    assert routed["governance"]["human_approval_required"] is True

    result = revenue_workforce_contract.build(
        organization_id=1,
        product={"name": "Kemet Content Service"},
        qualification={
            "status": "qualified",
            "missing_fields": [],
            "score": 90,
        },
        lead_id="internal-golden-test",
        channel=channel,
        language=message.language,
        context_query="commercial content pricing",
        task_id=f"cross-channel-{channel}",
    )

    evidence = result["workflow"]["evidence_context"]
    assert result["contract"] == "Kemet Revenue Workforce"
    assert result["authority"]["kemet"] == "decide_approve_execute_measure_audit"
    assert evidence["digest"] == "ctx-digest-1"
    assert evidence["references"][0]["content_digest"] == "source-digest-1"
    assert captured["organization_id"] == 1
    assert captured["source_metadata"]["channel"] == channel
    assert result["governance"]["tenant_scoped"] is True
    assert result["governance"]["fail_closed"] is True
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False


def test_cross_channel_golden_path_rejects_tenant_mismatch(monkeypatch):
    def fake_context(**kwargs):
        assert kwargs["organization_id"] == 7
        return {
            "digest": "ctx-tenant-7",
            "query_digest": "query-tenant-7",
            "sources": [],
            "retrieval": {"excluded": 0},
        }

    monkeypatch.setattr(
        "app.services.revenue_workforce_contract.evidence_backed_context_service.build",
        fake_context,
    )

    message = omnichannel_service.normalize(
        "telegram",
        "tg-user-7",
        "pricing please",
        organization_id=7,
    )
    assert message.organization_id == 7

    result = revenue_workforce_contract.build(
        organization_id=7,
        product={"name": "Kemet"},
        qualification={"status": "qualified"},
        channel=message.channel,
        context_query="pricing",
        task_id="cross-channel-tenant-7",
    )
    assert result["organization_id"] == 7
    assert result["workflow"]["evidence_context"]["digest"] == "ctx-tenant-7"
def test_cross_channel_golden_path_requires_complete_context_binding():
    with pytest.raises(ValueError, match="context_query_and_task_id_required"):
        revenue_workforce_contract.build(
            organization_id=1,
            product={"name": "Kemet"},
            qualification={"status": "qualified"},
            channel="telegram",
            context_query="pricing",
        )
