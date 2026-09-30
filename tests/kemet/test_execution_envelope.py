import uuid
from app.core.federation.execution_envelope import execution_envelope

def auth(): return {"plan_hash": "plan-1", "plan_id": "auth-1"}

def test_envelope_binds_governance_identities():
    key = uuid.uuid4().hex
    env = execution_envelope.build(approval_package_hash="pkg-1", decision_hash="dec-1", handoff_hash="handoff-1", authorization=auth(), execution_key=key, provider_id="kemet", action="business_insights")
    assert execution_envelope.verify(env, authorization=auth(), execution_key=key, provider_id="kemet", action="business_insights")

def test_envelope_fails_on_identity_change():
    key = uuid.uuid4().hex
    env = execution_envelope.build(approval_package_hash="pkg-1", decision_hash="dec-1", handoff_hash="handoff-1", authorization=auth(), execution_key=key, provider_id="kemet", action="business_insights")
    assert not execution_envelope.verify(env, authorization=auth(), execution_key=key, provider_id="manus", action="business_insights")

def test_envelope_detects_tampering():
    key = uuid.uuid4().hex
    env = execution_envelope.build(approval_package_hash="pkg-1", decision_hash="dec-1", handoff_hash="handoff-1", authorization=auth(), execution_key=key, provider_id="kemet", action="business_insights")
    env["decision_hash"] = "tampered"
    assert not execution_envelope.verify(env, authorization=auth(), execution_key=key, provider_id="kemet", action="business_insights")

def test_envelope_requires_identity():
    try:
        execution_envelope.build(approval_package_hash="", decision_hash="dec", handoff_hash="handoff", authorization=auth(), execution_key="x", provider_id="kemet", action="business_insights")
    except ValueError as exc:
        assert str(exc) == "execution_envelope_identity_required"
    else:
        raise AssertionError("incomplete identity must fail closed")
