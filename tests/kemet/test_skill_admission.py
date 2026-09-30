import pytest

from app.core.skills.admission import SkillAdmissionError, SkillAdmissionService, SkillManifest


def _manifest(**overrides):
    service = SkillAdmissionService()
    base = SkillManifest(
        skill_id="security-review",
        version="1.0.0",
        provenance="internal",
        owner="kemet",
        domain="engineering",
        allowed_tools=("read_file",),
        security_scan="passed",
        prompt_injection_review="passed",
        sandbox=True,
        signed=True,
        status="approved",
    )
    values = {**base.__dict__, **overrides}
    candidate = SkillManifest(**values)
    return SkillManifest(**{**candidate.__dict__, "digest": service.digest(candidate)})


def test_verified_skill_is_admitted_without_execution_authority():
    manifest = _manifest()
    result = SkillAdmissionService().admit(manifest)
    assert result["admitted"] is True
    assert result["execution_authority"] is False


def test_unsigned_skill_is_rejected():
    manifest = _manifest(signed=False)
    with pytest.raises(SkillAdmissionError, match="signed_manifest_required"):
        SkillAdmissionService().admit(manifest)


def test_tampered_manifest_digest_is_rejected():
    manifest = _manifest()
    tampered = SkillManifest(**{**manifest.__dict__, "allowed_tools": ("read_file", "write_file")})
    with pytest.raises(SkillAdmissionError, match="manifest_digest_mismatch"):
        SkillAdmissionService().admit(tampered)


def test_wildcard_tool_permission_is_rejected():
    manifest = _manifest(allowed_tools=("*",))
    with pytest.raises(SkillAdmissionError, match="wildcard_or_empty_tool_permission"):
        SkillAdmissionService().admit(manifest)


def test_untrusted_skill_requires_sandbox():
    manifest = _manifest(provenance="verified_vendor", sandbox=False)
    with pytest.raises(SkillAdmissionError, match="untrusted_skill_requires_sandbox"):
        SkillAdmissionService().admit(manifest)


def test_skill_cannot_claim_execution_authority():
    manifest = _manifest(execution_authority=True)
    with pytest.raises(SkillAdmissionError, match="skill_execution_authority_forbidden"):
        SkillAdmissionService().admit(manifest)


def test_registry_rejects_same_version_with_different_digest():
    service = SkillAdmissionService()
    from app.core.skills.registry import SkillRegistry
    registry = SkillRegistry()
    manifest = _manifest()
    assert registry.register(manifest)["registered"] is True
    tampered = SkillManifest(**{**manifest.__dict__, "owner": "attacker", "digest": service.digest(manifest)})
    result = registry.register(tampered)
    assert result["registered"] is False
    assert "manifest_digest_mismatch" in result["errors"]


def test_registry_requires_approval_before_publish():
    from app.core.skills.registry import SkillRegistry
    registry = SkillRegistry()
    manifest = _manifest()
    assert registry.register(manifest)["registered"] is True
    assert registry.publish(manifest.skill_id, manifest.version)["error"] == "skill_approval_required"
    assert registry.approve(manifest.skill_id, manifest.version, "security-reviewer")["approved"] is True
    published = registry.publish(manifest.skill_id, manifest.version)
    assert published["published"] is True
    assert published["execution_authority"] is False
    assert registry.get(manifest.skill_id).version == manifest.version


def test_registry_retirement_removes_active_version():
    from app.core.skills.registry import SkillRegistry
    registry = SkillRegistry()
    manifest = _manifest()
    registry.register(manifest)
    registry.approve(manifest.skill_id, manifest.version, "reviewer")
    registry.publish(manifest.skill_id, manifest.version)
    assert registry.retire(manifest.skill_id, manifest.version)["retired"] is True
    assert registry.get(manifest.skill_id) is None


def test_durable_registry_persists_across_registry_instances():
    from app import create_app, db
    from app.core.skills.registry import SkillRegistry
    app = create_app()
    with app.app_context():
        db.create_all()
        manifest = _manifest(version="2.0.0")
        first = SkillRegistry()
        assert first.register(manifest)["registered"] is True
        second = SkillRegistry()
        loaded = second.get(manifest.skill_id, manifest.version)
        assert loaded is not None
        assert loaded.digest == manifest.digest


def test_durable_registry_same_digest_is_idempotent():
    from app import create_app, db
    from app.core.skills.registry import SkillRegistry
    app = create_app()
    with app.app_context():
        db.create_all()
        manifest = _manifest(version="2.0.1")
        registry = SkillRegistry()
        assert registry.register(manifest)["registered"] is True
        result = registry.register(manifest)
        assert result["registered"] is True
        assert result["idempotent"] is True


def test_durable_publish_switches_active_version_atomically():
    from app import create_app, db
    from app.core.skills.registry import SkillRegistry
    app = create_app()
    with app.app_context():
        db.create_all()
        registry = SkillRegistry()
        v1 = _manifest(version="3.0.0")
        v2 = _manifest(version="3.1.0")
        registry.register(v1)
        registry.register(v2)
        registry.approve(v1.skill_id, v1.version, "reviewer")
        registry.publish(v1.skill_id, v1.version)
        registry.approve(v2.skill_id, v2.version, "reviewer")
        registry.publish(v2.skill_id, v2.version)
        assert registry.get(v1.skill_id).version == v2.version
        from app.models.skill_registry import SkillVersionRecord
        assert SkillVersionRecord.query.filter_by(skill_id=v1.skill_id, active=True).count() == 1


def test_durable_retirement_requires_fresh_approval_for_republish():
    from app import create_app, db
    from app.core.skills.registry import SkillRegistry
    app = create_app()
    with app.app_context():
        db.create_all()
        registry = SkillRegistry()
        manifest = _manifest(version="4.0.0")
        registry.register(manifest)
        registry.approve(manifest.skill_id, manifest.version, "reviewer")
        registry.publish(manifest.skill_id, manifest.version)
        registry.retire(manifest.skill_id, manifest.version)
        assert registry.publish(manifest.skill_id, manifest.version)["error"] == "skill_approval_required"
        registry.approve(manifest.skill_id, manifest.version, "reviewer")
        assert registry.publish(manifest.skill_id, manifest.version)["published"] is True


def test_skill_registry_health_detects_persisted_digest_tampering():
    from app import create_app, db
    from app.core.skills.registry import SkillRegistry
    from app.models.skill_registry import SkillVersionRecord
    app = create_app()
    with app.app_context():
        db.create_all()
        registry = SkillRegistry()
        manifest = _manifest(version="5.0.0")
        registry.register(manifest)
        row = SkillVersionRecord.query.filter_by(skill_id=manifest.skill_id, version=manifest.version).one()
        row.digest = "0" * 64
        db.session.commit()
        result = registry.health()
        assert result["ok"] is False
        assert any(item["error"] == "skill_persistence_integrity_failed" for item in result["issues"])


def test_skill_lifecycle_emits_tamper_evident_audit_events():
    from app import create_app, db
    from app.core.security_events import verify_security_event_chain
    from app.core.skills.registry import SkillRegistry
    from app.models.security_event import SecurityEventRecord
    app = create_app()
    with app.app_context():
        db.create_all()
        SecurityEventRecord.query.delete()
        db.session.commit()
        registry = SkillRegistry()
        manifest = _manifest(version="6.0.0")
        registry.register(manifest)
        registry.approve(manifest.skill_id, manifest.version, "auditor")
        registry.publish(manifest.skill_id, manifest.version)
        registry.retire(manifest.skill_id, manifest.version)
        events = SecurityEventRecord.query.filter(SecurityEventRecord.action == "skill_registry").all()
        types = [event.event_type for event in events]
        assert types == ["skill_registered", "skill_approved", "skill_published", "skill_retired"]
        assert verify_security_event_chain()["ok"] is True
