from app.core.federation.context_models import ContextEnvelope
from app.core.federation.model_handoff import create_handoff, verify_handoff
from app.core.federation.context_gateway import FederationContextGateway


def test_context_envelope_is_deterministic_and_redacts_metadata():
    item = ContextEnvelope(
        provider_id="openai", external_conversation_id="chat-1",
        organization_id=1, user_id=2, summary="Kemet Termux milestone",
        source_metadata={"api_key": "hidden", "channel": "chat"},
    )
    assert item.fingerprint() == item.fingerprint()
    assert "api_key" not in item.as_dict()["source_metadata"]


def test_handoff_is_tenant_bound_and_tamper_evident():
    item = create_handoff(
        organization_id=1, user_id=2, source_provider="openai",
        target_provider="anthropic", task_id="termux-1",
        context={"summary": "shared project state"}, requested_role="code-review",
    )
    assert verify_handoff(item, organization_id=1, user_id=2, target_provider="anthropic")
    assert not verify_handoff(item, organization_id=2, user_id=2, target_provider="anthropic")
    assert not verify_handoff(item, organization_id=1, user_id=2, target_provider="google")


def test_gateway_snapshot_is_provider_neutral():
    class FakeRow:
        provider_id = "openai"
        external_conversation_id = "chat-a"
        task_id = None
        role = "participant"
        summary = "shared"
        decisions_json = []
        artifacts_json = []
        context_hash = "a" * 64
        updated_at = None

    class FakeRegistry:
        @staticmethod
        def for_scope(*args):
            return [FakeRow()]

    gateway = FederationContextGateway(FakeRegistry())
    snap = gateway.snapshot(1, 2)
    assert snap.conversations[0]["provider_id"] == "openai"
    assert snap.termux == {}
