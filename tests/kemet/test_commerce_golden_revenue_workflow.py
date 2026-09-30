import json
from uuid import uuid4

from app import create_app, db
from app.core.automation_control_plane import AutomationPlan, AutomationStep
from app.core.execution_evidence import execution_evidence
from app.core.execution_ledger import execution_ledger
from app.core.automation_runtime import AutomationRuntime
from app.models.automation_outcome import AutomationOutcome
from app.models.payment import Payment
from app.services.commerce_fulfillment_service import commerce_fulfillment_service
from app.services.commerce_revenue_evidence_service import commerce_revenue_evidence_service
from app.services.commercial_outcome_trace import commercial_outcome_trace


def test_commerce_golden_revenue_spine(monkeypatch):
    app = create_app()
    with app.app_context():
        organization_id = 1
        execution_key = f"golden-{uuid4().hex}"
        plan = commerce_fulfillment_service.build_plan(
            organization_id=organization_id,
            business_reference=f"order-{uuid4().hex}",
            customer={"firstName": "Ali", "mobile": "01000000000"},
            shipping_address={"city": "Cairo", "firstLine": "Test address"},
            cod=1250,
            items=[{"name": "Leather Wallet", "quantity": 1}],
        )
        assert plan["status"] == "approval_required"
        assert plan["governance"]["external_execution"] is False
        params = plan["fulfillment"]["payload"]
        step = AutomationStep(
            step_id="fulfill",
            action="bosta_create_delivery",
            parameters={
                "organization_id": organization_id,
                "business_reference": params["businessReference"],
                "customer": params["customer"],
                "shipping_address": params["dropOffAddress"],
                "cod": params["cod"],
                "items": params["items"],
                "package_type": params["specs"]["packageType"],
                "package_description": params["specs"]["packageDetails"]["description"],
                "_approved_execution": True,
                "_execution_authorization": {"execution_key": execution_key},
            },
            connector_id="bosta_api", operation="create_delivery", risk="high",
            requires_approval=True, reversible=False,
        )
        runtime_plan = AutomationPlan(
            plan_id=f"golden-plan-{uuid4().hex}", organization_id=organization_id,
            trigger="approved_commerce_fulfillment", steps=(step,), dry_run=False,
            approval_policy="human", metadata={"execution_key": execution_key},
        )
        monkeypatch.setenv("KEMET_BOSTA_ORG_1_API_KEY", "test-bosta-key")
        class Response:
            ok = True
            status_code = 201
            def json(self):
                return {"data": {"order": {"_id": "BOSTA-100", "trackingNumber": "TRK-100"}}}
        monkeypatch.setattr("app.services.bosta_connector_service.governed_request", lambda *a, **k: Response())
        monkeypatch.setattr("app.core.automation_runtime.execution_boundary.require", lambda **k: {"allowed": True})
        result = AutomationRuntime().execute(
            runtime_plan, authorization={"execution_key": execution_key},
            actor_id="approved-admin", execution_key=execution_key,
        )
        assert result["status"] == "completed"
        receipt = result["receipt"]["steps"][0]["result"]
        assert receipt["order_id"] == "BOSTA-100"
        assert receipt["tracking_number"] == "TRK-100"

        job_id = 991001
        execution_ledger.begin(organization_id=organization_id, execution_key=execution_key,
                               plan_hash=result["plan_hash"], job_id=job_id,
                               worker_id="golden-test", approval_hash="a" * 64)
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key, job_id=job_id,
            stage="runtime.finished", status="completed", evidence_key=f"{execution_key}:runtime.finished",
            receipt=receipt,
        )
        db.session.add(AutomationOutcome(
            organization_id=organization_id, job_id=job_id, status="completed", executed=True,
            cost_amount=25, currency="USD", business_outcome="order_fulfillment_completed",
            receipt_json=json.dumps(receipt),
        ))
        db.session.commit()

        from app.services.bosta_connector_service import bosta_connector_service
        tracking = bosta_connector_service.normalize_tracking_event(
            organization_id=organization_id,
            payload={"_id": "BOSTA-100", "trackingNumber": "TRK-100", "state": 45,
                     "businessReference": params["businessReference"], "timeStamp": 1770000000,
                     "isConfirmedDelivery": True},
        )
        binding = bosta_connector_service.record_tracking_evidence(
            organization_id=organization_id, event=tracking
        )
        assert binding["execution_key"] == execution_key

        payment = Payment(
            organization_id=organization_id, plan="business", amount=125,
            currency="USD", status="paid", provider="test",
            provider_transaction_id=f"tx-{uuid4().hex}",
        )
        db.session.add(payment)
        db.session.flush()
        outcome = AutomationOutcome.query.filter_by(organization_id=organization_id, job_id=job_id).order_by(AutomationOutcome.id.desc()).first()
        outcome_receipt = json.loads(outcome.receipt_json or "{}")
        outcome_receipt["revenue_record_id"] = payment.id
        outcome.receipt_json = json.dumps(outcome_receipt)
        db.session.commit()
        payment_result = commerce_revenue_evidence_service.verify(
            organization_id=organization_id, execution_key=execution_key,
            payment_id=payment.id,
        )
        assert payment_result["status"] == "verified"

        trace = commercial_outcome_trace.get(organization_id, execution_key)
        assert trace["business"]["payment"]["evidence_backed"] is True
        assert trace["business"]["fulfillment"]["status"] == "delivered"
        assert trace["business"]["revenue"]["amount"] == 125.0
        assert trace["business"]["roi"] == 4.0
        assert trace["measurement"]["causal_claim"] is False
        assert trace["business"]["learning"]["status"] == "pass"
