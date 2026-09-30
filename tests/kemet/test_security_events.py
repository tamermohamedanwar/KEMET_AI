from app import create_app, db
from app.core.security_events import record_security_event, verify_security_event_chain
from app.models.security_event import SecurityEventRecord


def test_security_event_redaction_and_hash_chain():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        SecurityEventRecord.query.delete()
        db.session.commit()
        record_security_event(
            "authorization_denied", severity="high", action="execute",
            metadata={"token": "do-not-store", "nested": {"password": "secret", "safe": "ok"}},
        )
        record_security_event("execution_approved", metadata={"safe": "yes"})
        rows = SecurityEventRecord.query.order_by(SecurityEventRecord.id).all()
        assert len(rows) == 2
        assert rows[0].get_metadata()["token"] == "[REDACTED]"
        assert rows[0].get_metadata()["nested"]["password"] == "[REDACTED]"
        assert rows[1].previous_hash == rows[0].event_hash
        assert verify_security_event_chain()["ok"] is True


def test_security_readiness_flags_memory_storage_in_production(monkeypatch):
    from app.core.security_readiness import security_readiness
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "memory://")
    result = security_readiness()
    assert result["ready"] is False
    assert "rate_limit_shared_storage" in result["blocking"]
