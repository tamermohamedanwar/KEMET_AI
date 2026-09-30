import json
from uuid import uuid4

from app import create_app, db
from app.core.execution_ledger import execution_ledger
from app.models.automation_outcome import AutomationOutcome
from app.services.commercial_outcome_trace import commercial_outcome_trace


def _execution_key():
    return f"commercial-test-{uuid4().hex}"


def _seed_execution(organization_id, job_id, receipt, cost=10):
    execution_key = _execution_key()
    execution_ledger.begin(
        organization_id=organization_id,
        execution_key=execution_key,
        plan_hash="a" * 64,
        job_id=job_id,
        worker_id="test-worker",
        approval_hash="b" * 64,
    )
    db.session.add(AutomationOutcome(
        organization_id=organization_id,
        job_id=job_id,
        status="completed",
        executed=True,
        cost_amount=cost,
        currency="USD",
        business_outcome="lead_converted",
        receipt_json=json.dumps(receipt),
    ))
    db.session.commit()
    return execution_key


def test_commercial_trace_is_tenant_scoped_and_fail_closed():
    app = create_app()
    with app.app_context():
        assert commercial_outcome_trace.get(None, "x") is None
        assert commercial_outcome_trace.get(999999, "missing") is None


def test_commercial_trace_builds_complete_observed_business_chain():
    app = create_app()
    with app.app_context():
        key = _seed_execution(1, 987654, {
            "customer": "customer-6",
            "intent": "increase_sales",
            "lead_id": 6,
            "qualification": "qualified",
            "opportunity_id": "opp-6",
            "decision": "follow_up",
            "action": "revenue_autopilot_run",
            "recorded_revenue": 50,
            "revenue_source": "recorded_outcome",
        })
        result = commercial_outcome_trace.get(1, key)

    assert result["business"]["customer"] == "customer-6"
    assert result["business"]["intent"] == "increase_sales"
    assert result["business"]["lead"] == 6
    assert result["business"]["qualification"] == "qualified"
    assert result["business"]["opportunity"] == "opp-6"
    assert result["business"]["decision"] == "follow_up"
    assert result["business"]["approval"]["present"] is True
    assert result["business"]["action"] == "revenue_autopilot_run"
    assert result["business"]["outcome"] == "lead_converted"
    assert result["business"]["revenue"]["amount"] == 50.0
    assert result["business"]["revenue"]["source"] == "recorded_outcome"
    assert result["business"]["revenue"]["provenance"] == "reported_outcome"
    assert result["business"]["revenue"]["evidence_backed"] is False
    assert result["business"]["cost"] == 10.0
    assert result["business"]["roi"] is None
    assert result["measurement"]["roi_proven"] is False
    assert result["measurement"]["causal_claim"] is False


def test_commercial_trace_never_infers_revenue_or_roi():
    app = create_app()
    with app.app_context():
        key = _seed_execution(1, 987655, {
            "lead_id": 6,
            "estimated_value": 5000,
            "conversion_status": "converted",
        })
        result = commercial_outcome_trace.get(1, key)

    assert result["business"]["revenue"] is None
    assert result["business"]["roi"] is None
    assert result["measurement"]["roi_proven"] is False
    assert result["measurement"]["causal_claim"] is False


def test_commercial_trace_payment_evidence_proves_roi_and_overrides_reported_revenue():
    from app.core.execution_evidence import execution_evidence

    app = create_app()
    with app.app_context():
        key = _seed_execution(1, 987658, {
            "recorded_revenue": 999,
            "revenue_source": "recorded_outcome",
            "content_id": "c1",
            "publication_id": "p1",
            "execution_key": key if False else "",
        }, cost=25)
        from app.models.payment import Payment
        payment = Payment(organization_id=1, plan="business", amount=125, currency="USD", status="paid", provider="paymob", provider_transaction_id="trace-payment-001")
        db.session.add(payment); db.session.commit()
        execution_evidence.record(
            organization_id=1,
            execution_key=key,
            job_id=987658,
            stage="payment.completed",
            status="completed",
            evidence_key=f"{key}:payment:verified",
            receipt={"payment_id": payment.id, "amount": 999, "currency": "USD", "provider": "paymob", "provider_transaction_id": "trace-payment-001", "content_id": "c1", "publication_id": "p1", "execution_key": key},
        )
        result = commercial_outcome_trace.get(1, key)
        db.session.delete(payment); db.session.commit()

    assert result["business"]["revenue"]["amount"] == 125.0
    assert result["business"]["revenue"]["source"] == "payment_record"
    assert result["business"]["revenue"]["provenance"] == "payment_evidence"
    assert result["business"]["revenue"]["evidence_backed"] is True
    assert result["business"]["roi"] == 4.0
    assert result["measurement"]["roi_proven"] is True
    assert result["measurement"]["revenue_attribution"]["evidence_backed"] is True
    assert result["measurement"]["causal_claim"] is False


def test_commercial_trace_rejects_cross_tenant_lookup():
    app = create_app()
    with app.app_context():
        key = _seed_execution(1, 987656, {
            "lead_id": 6,
            "recorded_revenue": 25,
        })
        assert commercial_outcome_trace.get(2, key) is None


def test_commercial_trace_is_observational_and_read_only():
    assert commercial_outcome_trace.VERSION == "1.1"
    assert not hasattr(commercial_outcome_trace, "execute")
    assert not hasattr(commercial_outcome_trace, "dispatch")
    assert not hasattr(commercial_outcome_trace, "save")


def test_commercial_trace_exposes_delivery_evidence():
    from app.core.execution_evidence import execution_evidence

    app = create_app()
    with app.app_context():
        key = _seed_execution(1, 987657, {"lead_id": 6, "recorded_revenue": 75})
        execution_evidence.record(
            organization_id=1,
            execution_key=key,
            job_id=987657,
            stage="channel.delivery",
            status="delivered",
            evidence_key=f"{key}:delivery:delivered",
            receipt={"provider": "meta_whatsapp_cloud", "message_id": "wamid.trace"},
        )
        result = commercial_outcome_trace.get(1, key)

    assert result["business"]["delivery"]["status"] == "delivered"
    assert result["business"]["delivery"]["evidence_backed"] is True
    assert result["business"]["delivery"]["latest"]["message_id"] == "wamid.trace"
