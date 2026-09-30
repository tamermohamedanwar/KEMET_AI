import json
from uuid import uuid4

from app import create_app, db
from app.core.execution_ledger import execution_ledger
from app.models.automation_outcome import AutomationOutcome
from app.models.payment import Payment
from app.services.commerce_revenue_evidence_service import commerce_revenue_evidence_service


def _seed_trace(org=1, revenue=125, cost=25):
    key = f"evidence-{uuid4().hex}"
    job_id = 990000 + (uuid4().int % 1000000)
    execution_ledger.begin(organization_id=org, execution_key=key, plan_hash="a" * 64,
                           job_id=job_id, worker_id="test-worker", approval_hash="b" * 64)
    db.session.add(AutomationOutcome(
        organization_id=org, job_id=job_id, status="completed", executed=True,
        cost_amount=cost, currency="USD", business_outcome="lead_converted",
        receipt_json=json.dumps({"lead_id": 6, "recorded_revenue": revenue, "revenue_source": "payment_record", "revenue_record_id": None}),
    ))
    payment = Payment(organization_id=org, plan="business", amount=revenue,
                      currency="USD", status="paid", provider="test",
                      provider_transaction_id=f"tx-{uuid4().hex}")
    db.session.add(payment)
    db.session.flush()
    outcome = AutomationOutcome.query.filter_by(organization_id=org, job_id=job_id).order_by(AutomationOutcome.id.desc()).first()
    receipt = json.loads(outcome.receipt_json)
    receipt["revenue_record_id"] = payment.id
    outcome.receipt_json = json.dumps(receipt)
    db.session.commit()
    return key, payment.id


def test_revenue_evidence_verifies_real_payment_and_trace():
    app = create_app()
    with app.app_context():
        key, payment_id = _seed_trace()
        result = commerce_revenue_evidence_service.verify(
            organization_id=1, execution_key=key, payment_id=payment_id
        )
    assert result["success"] is True
    assert result["status"] == "verified"
    assert result["evidence"]["payment"]["payment_id"] == payment_id
    assert result["evidence"]["payment"]["provider_transaction_id"]
    assert result["evidence"]["payment"]["provider_order_id"] is None
    assert result["commercial"]["revenue"] == {
        "amount": 125.0, "currency": "USD", "source": "payment_record",
        "evidence_backed": True, "provenance": "payment_evidence",
    }
    assert result["commercial"]["roi"] == 4.0
    assert result["commercial"]["causal_claim"] is False
    lineage = result["provenance_lineage"]
    assert lineage["schema"] == "kemet.provenance_lineage.v1"
    assert lineage["governance"]["external_execution"] is False
    assert [node["type"] for node in lineage["nodes"]] == ["transaction"]
    assert lineage["nodes"][0]["id"] == str(payment_id)


def test_revenue_evidence_rejects_unbound_same_tenant_payment():
    app = create_app()
    with app.app_context():
        key, _ = _seed_trace()
        unrelated = Payment(organization_id=1, plan="business", amount=999,
                            currency="USD", status="paid", provider="test",
                            provider_transaction_id=f"unrelated-{uuid4().hex}")
        db.session.add(unrelated)
        db.session.commit()
        result = commerce_revenue_evidence_service.verify(
            organization_id=1, execution_key=key, payment_id=unrelated.id
        )
    assert result["success"] is False
    assert result["error"] == "payment_execution_binding_mismatch"
    assert result["commercial"]["roi"] == "not_proven"


def test_revenue_evidence_requires_existing_execution_trace():
    app = create_app()
    with app.app_context():
        payment = Payment(organization_id=1, plan="business", amount=125,
                          currency="USD", status="paid", provider="test",
                          provider_transaction_id=f"tx-{uuid4().hex}")
        db.session.add(payment)
        db.session.commit()
        result = commerce_revenue_evidence_service.verify(
            organization_id=1, execution_key=f"missing-{uuid4().hex}", payment_id=payment.id
        )
    assert result["success"] is False
    assert result["error"] == "execution_trace_not_found"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False


def test_revenue_evidence_is_idempotent_for_same_payment_trace():
    app = create_app()
    with app.app_context():
        key, payment_id = _seed_trace()
        first = commerce_revenue_evidence_service.verify(
            organization_id=1, execution_key=key, payment_id=payment_id
        )
        second = commerce_revenue_evidence_service.verify(
            organization_id=1, execution_key=key, payment_id=payment_id
        )
        from app.models.execution_evidence import ExecutionEvidence
        rows = ExecutionEvidence.query.filter_by(
            organization_id=1, execution_key=key, stage="payment.completed",
            evidence_key=f"{key}:payment:{payment_id}"
        ).all()
    assert first["success"] is True
    assert second["success"] is True
    assert len(rows) == 1
    assert second["commercial"]["causal_claim"] is False


def test_revenue_evidence_is_tenant_scoped_and_fail_closed():
    app = create_app()
    with app.app_context():
        key, payment_id = _seed_trace()
        wrong = commerce_revenue_evidence_service.verify(
            organization_id=2, execution_key=key, payment_id=payment_id
        )
    assert wrong["success"] is False
    assert wrong["error"] == "recorded_payment_not_found"
    assert wrong["commercial"]["revenue"] == "not_available"
    assert wrong["commercial"]["roi"] == "not_proven"
