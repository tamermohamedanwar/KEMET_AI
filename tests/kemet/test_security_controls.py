from datetime import datetime, timedelta, timezone
import pytest

from app.core.egress_policy import EgressDenied, validate_public_http_target
from app.core.secret_boundary import redact, secret_reference
from app.core.security_policy import AuthorizationPolicyEngine, PolicyDenied, PolicyGrant


def test_authorization_is_deny_by_default_and_tenant_scoped():
    engine = AuthorizationPolicyEngine()
    with pytest.raises(PolicyDenied):
        engine.authorize(grant=None, subject_id="1", organization_id=1, action="execute", resource="invoice:1")
    grant = PolicyGrant("1", 7, ("execute",), ("invoice:1",), datetime.now(timezone.utc) + timedelta(minutes=5))
    assert engine.authorize(grant=grant, subject_id="1", organization_id=7, action="execute", resource="invoice:1")["authorized"]
    with pytest.raises(PolicyDenied):
        engine.authorize(grant=grant, subject_id="1", organization_id=8, action="execute", resource="invoice:1")


def test_secret_boundary_redacts_nested_data():
    value = {"token": "abc", "nested": {"password": "xyz"}, "text": "Authorization: Bearer abc"}
    safe = redact(value)
    assert safe["token"] == "[REDACTED]"
    assert safe["nested"]["password"] == "[REDACTED]"
    assert "abc" not in safe["text"]
    assert secret_reference("openrouter", "primary") != secret_reference("openrouter", "secondary")


def test_egress_policy_blocks_private_targets():
    with pytest.raises(EgressDenied):
        validate_public_http_target("http://127.0.0.1:8000/health")
    with pytest.raises(EgressDenied):
        validate_public_http_target("http://localhost/test")


def test_execution_boundary_enforces_optional_tenant_policy_grant():
    from app.core.execution.execution_boundary import ExecutionBoundary
    from datetime import datetime, timedelta, timezone
    boundary = ExecutionBoundary()
    plan = {
        "organization_id": 7,
        "resource": "invoice:1",
        "action": "execute",
        "security_policy_grant": {
            "subject_id": "42",
            "organization_id": 7,
            "actions": ["execute"],
            "resources": ["invoice:1"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        },
    }
    blocked = boundary.authorize(plan, None, "execute", subject_id=43)
    assert blocked["allowed"] is False
    assert blocked["error"] == "security_policy_denied"


def test_execution_boundary_allows_matching_tenant_policy_before_gate():
    from app.core.execution.execution_boundary import ExecutionBoundary
    from datetime import datetime, timedelta, timezone
    boundary = ExecutionBoundary()
    plan = {
        "organization_id": 7, "resource": "invoice:1", "action": "execute",
        "security_policy_grant": {
            "subject_id": "42", "organization_id": 7, "actions": ["execute"],
            "resources": ["invoice:1"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        },
    }
    blocked = boundary.authorize(plan, None, "execute", subject_id=42)
    assert blocked["error"] == "execution_authorization_required"


def test_egress_policy_blocks_reserved_and_non_http_targets():
    with pytest.raises(EgressDenied):
        validate_public_http_target("ftp://example.com/file")
    with pytest.raises(EgressDenied):
        validate_public_http_target("http://[::1]/")


def test_security_policy_rejects_expired_grant():
    from datetime import datetime, timedelta, timezone
    engine = AuthorizationPolicyEngine()
    grant = PolicyGrant("42", 7, ("execute",), ("invoice:1",), datetime.now(timezone.utc) - timedelta(seconds=1))
    with pytest.raises(PolicyDenied):
        engine.authorize(grant=grant, subject_id="42", organization_id=7, action="execute", resource="invoice:1")


def test_secret_boundary_redacts_common_header_forms():
    safe = redact({"Authorization": "Bearer super-secret", "api_key": "live-secret", "value": "token=secret-value"})
    assert "super-secret" not in str(safe)
    assert "live-secret" not in str(safe)
    assert "secret-value" not in str(safe)


def test_egress_policy_blocks_link_local_and_multicast_literals():
    for url in ("http://169.254.169.254/latest/meta-data", "http://224.0.0.1/"):
        with pytest.raises(EgressDenied):
            validate_public_http_target(url)


def test_secret_boundary_redacts_oauth_and_provider_headers():
    safe = redact({
        "x-api-key": "provider-secret",
        "access_token": "access-secret",
        "refresh-token": "refresh-secret",
        "client_secret": "client-secret",
        "Set-Cookie": "session=secret",
    })
    assert all(value == "[REDACTED]" for value in safe.values())


def test_egress_policy_blocks_ipv6_link_local_and_reserved_literals():
    for url in ("http://[fe80::1]/", "http://[::ffff:127.0.0.1]/"):
        with pytest.raises(EgressDenied):
            validate_public_http_target(url)


def test_egress_policy_rejects_mixed_public_and_private_dns_results(monkeypatch):
    public = ("AF_INET", None, None, None, ("93.184.216.34", 443))
    private = ("AF_INET", None, None, None, ("127.0.0.1", 443))
    monkeypatch.setattr("app.core.egress_policy.socket.getaddrinfo", lambda *args, **kwargs: [public, private])
    with pytest.raises(EgressDenied, match="private_address_blocked"):
        validate_public_http_target("https://example.com")


def test_egress_policy_rejects_dns_metadata_target(monkeypatch):
    metadata = ("AF_INET", None, None, None, ("169.254.169.254", 80))
    monkeypatch.setattr("app.core.egress_policy.socket.getaddrinfo", lambda *args, **kwargs: [metadata])
    with pytest.raises(EgressDenied, match="private_address_blocked"):
        validate_public_http_target("https://metadata.example")


def test_security_policy_rejects_action_escalation():
    engine = AuthorizationPolicyEngine()
    grant = PolicyGrant("42", 7, ("read_invoice",), ("invoice:1",), datetime.now(timezone.utc) + timedelta(minutes=5))
    with pytest.raises(PolicyDenied, match="policy_denied"):
        engine.authorize(grant=grant, subject_id="42", organization_id=7, action="approve_refund", resource="invoice:1")


def test_security_policy_rejects_resource_escalation():
    engine = AuthorizationPolicyEngine()
    grant = PolicyGrant("42", 7, ("execute",), ("invoice:1",), datetime.now(timezone.utc) + timedelta(minutes=5))
    with pytest.raises(PolicyDenied, match="policy_denied"):
        engine.authorize(grant=grant, subject_id="42", organization_id=7, action="execute", resource="invoice:2")
