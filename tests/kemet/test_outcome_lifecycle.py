import json
import uuid

import pytest

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.external_task_lifecycle import external_task_lifecycle
from app.core.execution_ledger import execution_ledger
from app.core.execution_evidence import execution_evidence
from app.core.federation.outcome_control import OutcomeControlService
from app.core.federation.outcome_lifecycle import OutcomeLifecycleError, outcome_lifecycle
from app.models.external_task import ExternalTaskRecord


def _setup():
    uid = uuid.uuid4().hex
    org = Organization(name=f"Outcome {uid}", slug=f"outcome-{uid}")
    db.session.add(org)
    db.session.commit()
    execution_key = f"exec-{uid}"
    external_task_lifecycle.create_submission(
        organization_id=org.id, provider_id="manus", external_task_id=f"m-{uid}",
        execution_key=execution_key, plan_hash="plan-outcome", action="manus.task.create",
        metadata={"task_id": "task-1"},
    )
    execution_ledger.begin(organization_id=org.id, execution_key=execution_key, plan_hash="plan-outcome",
                           decision_hash="decision-hash-1")
    receipt = {"provider_id": "manus", "action": "manus.task.create",
               "external_task_id": f"m-{uid}", "request_id": f"r-{uid}", "status": "submitted"}
    execution_ledger.finish(organization_id=org.id, execution_key=execution_key,
                            status="submitted", receipt=receipt)
    execution_evidence.record(organization_id=org.id, execution_key=execution_key,
                              stage="specialist.execution_submitted", status="submitted",
                              evidence_key=f"{execution_key}:specialist.execution_submitted",
                              plan_hash="plan-outcome", receipt=receipt)
    return org, execution_key


def _contract(org):
    return OutcomeControlService().contract(decision={
        "decision_id": "decision-1", "task_id": "task-1",
        "organization_id": org.id, "digest": "d" * 64,
        "decision_hash": "decision-hash-1",
    }, expected_metrics=[{"metric": "revenue", "baseline": 100, "target": 150}])


def test_outcome_lifecycle_binds_durable_identity_and_is_idempotent():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        first = outcome_lifecycle.bind_contract(
            contract=contract, organization_id=org.id, execution_key=key,
            provider_id="manus", evidence_context_hash="evidence-1",
            measurement_context={"window": "30d", "as_of": "2026-09-12"},
        )
        second = outcome_lifecycle.bind_contract(
            contract=contract, organization_id=org.id, execution_key=key,
            provider_id="manus", evidence_context_hash="evidence-1",
            measurement_context={"window": "30d", "as_of": "2026-09-12"},
        )
        assert first == second
        assert first["status"] == "bound"
        assert first["measurement_count"] == 0


def test_outcome_replay_is_blocked():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                        provider_id="manus", evidence_context_hash="evidence-1",
                                        measurement_context=ctx)
        outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                  contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                  measurement_context=ctx, observed={"revenue": 160})
        with pytest.raises(OutcomeLifecycleError, match="outcome_measurement_replay"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                      measurement_context=ctx, observed={"revenue": 160})


def test_stale_measurement_context_fails_closed():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                        provider_id="manus", evidence_context_hash="evidence-1",
                                        measurement_context={"window": "30d", "as_of": "2026-09-12"})
        with pytest.raises(OutcomeLifecycleError, match="stale_measurement_context"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                      measurement_context={"window": "7d", "as_of": "2026-09-12"}, observed={"revenue": 160})


def test_provider_result_substitution_and_cross_tenant_mixing_fail_closed():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                        provider_id="manus", evidence_context_hash="evidence-1",
                                        measurement_context=ctx)
        with pytest.raises(OutcomeLifecycleError, match="outcome_provider_id_mismatch"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="grok",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                      measurement_context=ctx, observed={"revenue": 160})
        with pytest.raises(OutcomeLifecycleError, match="outcome_evidence_context_hash_mismatch"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-2",
                                      measurement_context=ctx, observed={"revenue": 160})


def test_execution_receipt_substitution_fails_closed():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                        provider_id="manus", evidence_context_hash="evidence-1",
                                        measurement_context=ctx)
        ledger = execution_ledger.get(organization_id=org.id, execution_key=key)
        row = db.session.get(__import__("app.models.automation_execution_ledger", fromlist=["AutomationExecutionLedger"]).AutomationExecutionLedger, ledger["id"])
        row.receipt_json = json.dumps({"provider_id": "grok", "action": "manus.task.create",
                                      "external_task_id": "substituted",
                                      "execution_identity": {"decision_hash": "decision-hash-1"}})
        db.session.commit()
        with pytest.raises(OutcomeLifecycleError, match="execution_receipt_binding_mismatch"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                      measurement_context=ctx, observed={"revenue": 160})


def test_execution_evidence_substitution_fails_closed():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                        provider_id="manus", evidence_context_hash="evidence-1",
                                        measurement_context=ctx)
        from app.models.execution_evidence import ExecutionEvidence
        evidence = ExecutionEvidence.query.filter_by(organization_id=org.id, execution_key=key,
                                                      stage="specialist.execution_submitted").first()
        evidence.receipt_json = '{"provider_id":"grok","action":"manus.task.create","external_task_id":"substituted"}'
        db.session.commit()
        with pytest.raises(OutcomeLifecycleError, match="execution_evidence_binding_mismatch"):
            outcome_lifecycle.measure(organization_id=org.id, execution_key=key, provider_id="manus",
                                      contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                                      measurement_context=ctx, observed={"revenue": 160})


def test_cross_tenant_execution_receipt_binding_fails_closed():
    with application.app_context():
        db.create_all()
        first, key = _setup()
        second = Organization(name=f"Outcome Other {uuid.uuid4().hex}", slug=f"outcome-other-{uuid.uuid4().hex}")
        db.session.add(second)
        db.session.commit()
        contract = _contract(first)
        with pytest.raises(OutcomeLifecycleError, match="outcome_contract_tenant_mismatch"):
            outcome_lifecycle.bind_contract(contract=contract, organization_id=second.id, execution_key=key,
                                            provider_id="manus", evidence_context_hash="evidence-1",
                                            measurement_context={"window": "30d", "as_of": "2026-09-12"})


def test_outcome_binding_cannot_downgrade_execution_binding():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        first = outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                                provider_id="manus", evidence_context_hash="evidence-1",
                                                measurement_context=ctx)
        with pytest.raises(OutcomeLifecycleError, match="outcome_lifecycle_identity_conflict"):
            outcome_lifecycle.bind_contract(contract=contract, organization_id=org.id, execution_key=key,
                                            provider_id="manus", evidence_context_hash="evidence-2",
                                            measurement_context=ctx)
        assert first["execution_receipt_digest"]
        assert first["execution_evidence_binding_digest"]


def test_outcome_rejects_different_approved_decision_hash():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        contract["decision_hash"] = "different-approved-decision"
        contract_payload = dict(contract)
        contract_payload.pop("digest", None)
        contract["digest"] = OutcomeControlService()._digest(contract_payload)
        with pytest.raises(OutcomeLifecycleError, match="outcome_decision_hash_binding_mismatch"):
            outcome_lifecycle.bind_contract(
                contract=contract,
                organization_id=org.id,
                execution_key=key,
                provider_id="manus",
                evidence_context_hash="evidence-1",
                measurement_context={"window": "30d", "as_of": "2026-09-12"},
            )


def test_outcome_rejects_tampered_decision_identity_after_binding():
    with application.app_context():
        db.create_all()
        org, key = _setup()
        contract = _contract(org)
        ctx = {"window": "30d", "as_of": "2026-09-12"}
        outcome_lifecycle.bind_contract(
            contract=contract, organization_id=org.id, execution_key=key,
            provider_id="manus", evidence_context_hash="evidence-1",
            measurement_context=ctx,
        )
        row = ExternalTaskRecord.query.filter_by(
            organization_id=org.id, execution_key=key
        ).first()
        metadata = json.loads(row.metadata_json or "{}")
        metadata["outcome_lifecycle"]["decision_hash"] = "tampered"
        row.metadata_json = json.dumps(metadata)
        db.session.commit()
        with pytest.raises(OutcomeLifecycleError, match="outcome_decision_hash_binding_mismatch"):
            outcome_lifecycle.measure(
                organization_id=org.id, execution_key=key, provider_id="manus",
                contract_digest=contract["digest"], evidence_context_hash="evidence-1",
                measurement_context=ctx, observed={"revenue": 160},
            )
