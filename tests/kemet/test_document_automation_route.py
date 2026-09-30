import io
import json

from app import db
from app.core.automation_outcome_service import automation_outcome_service
from app.core.execution_evidence import execution_evidence
from app.core.execution_ledger import execution_ledger
from app.models.automation_outcome import AutomationOutcome
from wsgi import application


def test_document_automation_route_records_canonical_execution(tmp_path, monkeypatch):
    application.config["WTF_CSRF_ENABLED"] = False
    def fake_process_files_v4(saved_files):
        return {
            "readiness_gate": {"status": "READY"},
            "summary": {"files": len(saved_files), "records": 1},
            "quality": {"score": 1.0},
        }

    def fake_export_delivery_package_v4(payload, output_dir):
        from pathlib import Path

        target = Path(output_dir)
        target.mkdir(parents=True, exist_ok=True)
        output = target / "normalized.csv"
        output.write_text("invoice_id,total\nINV-001,100\n", encoding="utf-8")
        return {"normalized.csv": str(output)}

    monkeypatch.setattr(
        "app.services.document_automation.process_files_v4",
        fake_process_files_v4,
    )
    monkeypatch.setattr(
        "app.services.document_automation.export_delivery_package_v4",
        fake_export_delivery_package_v4,
    )

    with application.app_context():
        client = application.test_client()

        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True

        response = client.post(
            "/api/document-automation/process",
            data={
                "files": (
                    io.BytesIO(b"invoice_id,total\nINV-001,100\n"),
                    "invoice.csv",
                )
            },
            content_type="multipart/form-data",
        )

        print("\nROUTE_STATUS:", response.status_code)
        print("ROUTE_BODY:", response.get_json(silent=True))
        assert response.status_code == 200

        body = response.get_json()
        assert body["ok"] is True
        assert body["product"] == "Kemet Document Intelligence"
        assert body["status"] == "READY"
        assert body["execution_key"]

        execution_key = body["execution_key"]
        organization_id = 1

        ledger = execution_ledger.get(
            organization_id=organization_id,
            execution_key=execution_key,
        )
        assert ledger is not None
        assert ledger["status"] == "completed"

        history = execution_evidence.history(
            organization_id=organization_id,
            execution_key=execution_key,
        )
        stages = {item["stage"] for item in history}

        assert "document_automation.intake" in stages
        assert "document_automation.processing" in stages
        assert "document_automation.delivery" in stages

        outcome = (
            AutomationOutcome.query
            .filter_by(
                organization_id=organization_id,
                correlation_id=execution_key,
            )
            .order_by(AutomationOutcome.id.desc())
            .first()
        )

        assert outcome is not None
        assert outcome.status == "DELIVERED"
        assert outcome.executed is True
        assert outcome.business_outcome == "document_delivery"

        assert body["outputs"]
        assert "normalized.csv" in body["outputs"]
