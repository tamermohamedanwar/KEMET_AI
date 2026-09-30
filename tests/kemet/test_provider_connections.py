import os
import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.models.provider_connection import ProviderConnectionRecord
from app.core.federation.provider_connections import ProviderConnectionRegistry
from app.core.federation.connection_lifecycle import ConnectionLifecycleService


def test_connection_matrix_is_provider_neutral_and_no_native_sync():
    items = ProviderConnectionRegistry().all(1, 2)
    assert {item.provider_id for item in items} >= {"openai", "anthropic", "google", "xai", "meta"}
    assert all(item.metadata["native_chat_sync"] is False for item in items)


def test_connection_status_does_not_expose_secret():
    os.environ.pop("OPENAI_API_KEY", None)
    item = ProviderConnectionRegistry().capabilities("openai", 1, 2)
    payload = item.as_dict()
    assert payload["status"] == "requires_user_action"
    assert "api_key" not in str(payload).lower()


def test_handoff_connection_is_scoped_and_redacts_metadata():
    item = ProviderConnectionRegistry().register_handoff(
        "anthropic", 7, 11, {"token": "secret", "channel": "user_initiated", "source": "claude"}
    )
    assert item.organization_id == 7 and item.user_id == 11
    assert item.status == "available"
    assert "token" not in item.as_dict()["metadata"]
    assert item.mode == "user_handoff"


def test_unknown_provider_fails_closed():
    item = ProviderConnectionRegistry().capabilities("unknown", 1, 2)
    assert item.status == "unsupported" and item.capabilities == ()


def test_durable_connection_lifecycle_is_tenant_and_user_scoped():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org_a = Organization(name=f"Conn A {uid}", slug=f"conn-a-{uid}")
        org_b = Organization(name=f"Conn B {uid}", slug=f"conn-b-{uid}")
        db.session.add_all([org_a, org_b])
        db.session.commit()
        row = ConnectionLifecycleService.register(org_a.id, 101, "openai", scopes=["generate"])
        assert row.status in {"configured", "requires_user_action"}
        assert ConnectionLifecycleService.list_for_user(org_b.id, 101) == []
        public = ConnectionLifecycleService.as_public(row)
        assert "credential_ref" not in public
        assert "api_key" not in str(public).lower()


def test_connection_verification_is_read_only_by_default():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Verify {uid}", slug=f"verify-{uid}")
        db.session.add(org)
        db.session.commit()
        row = ConnectionLifecycleService.register(org.id, 202, "xai")
        result = ConnectionLifecycleService.verify(row, live=False)
        assert result["network_call"] is False
        assert row.status in {"configured", "requires_user_action"}
        assert row.status != "verified"


def test_revocation_is_durable_and_fail_closed():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Revoke {uid}", slug=f"revoke-{uid}")
        db.session.add(org)
        db.session.commit()
        row = ConnectionLifecycleService.register(org.id, 303, "google")
        ConnectionLifecycleService.revoke(row)
        saved = db.session.get(ProviderConnectionRecord, row.id)
        assert saved.status == "revoked"
        try:
            ConnectionLifecycleService.verify(saved, live=False)
            assert False
        except ValueError as exc:
            assert str(exc) == "connection_revoked"
