import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.execution_evidence import execution_evidence
from app.services.publication_evidence_service import publication_evidence_service


def test_publication_receipt_is_verified_without_claiming_metrics_or_revenue():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Publication {uid}", slug=f"publication-{uid}")
        db.session.add(org)
        db.session.commit()
        key = f"pub-{uid}"
        execution_evidence.record(
            organization_id=org.id,
            execution_key=key,
            stage="channel.facebook.publish",
            status="published",
            evidence_key=f"{key}:receipt",
            receipt={"provider": "facebook", "publication_id": "post-123"},
        )
        result = publication_evidence_service.verify(
            organization_id=org.id,
            execution_key=key,
            channel="facebook",
        )
        assert result["verified"] is True
        assert result["records"][0]["publication_id"] == "post-123"
        assert result["records"][0]["metrics_verified"] is False
        assert result["records"][0]["revenue_verified"] is False


def test_telegram_publication_receipt_is_verified_without_metrics_claim():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Telegram {uid}", slug=f"telegram-{uid}")
        db.session.add(org)
        db.session.commit()
        key = f"tg-{uid}"
        execution_evidence.record(
            organization_id=org.id,
            execution_key=key,
            stage="channel.telegram.publish",
            status="published",
            evidence_key=f"{key}:receipt",
            receipt={"provider": "telegram_bot_api", "publication_id": "msg-123", "channel_ref": "@kemet"},
        )
        result = publication_evidence_service.verify(
            organization_id=org.id, execution_key=key, channel="telegram"
        )
        assert result["verified"] is True
        assert result["records"][0]["publication_id"] == "msg-123"
        assert result["records"][0]["metrics_verified"] is False
        assert result["records"][0]["revenue_verified"] is False


def test_missing_publication_receipt_fails_closed():
    with application.app_context():
        db.create_all()
        uid = uuid.uuid4().hex
        org = Organization(name=f"Publication Missing {uid}", slug=f"publication-missing-{uid}")
        db.session.add(org)
        db.session.commit()
        result = publication_evidence_service.verify(
            organization_id=org.id,
            execution_key=f"missing-{uid}",
            channel="instagram",
        )
        assert result["verified"] is False
        assert result["status"] == "publication_evidence_missing"
