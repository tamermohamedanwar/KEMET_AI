import uuid

import pytest

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.external_task_lifecycle import (
    ExternalTaskLifecycleError,
    external_task_lifecycle,
)
from app.core.execution_ledger import execution_ledger
from app.core.federation.external_task_control_plane import external_task_control_plane


def _org(prefix="Recon"):
    uid = uuid.uuid4().hex
    row = Organization(name=f"{prefix} {uid}", slug=f"{prefix.lower()}-{uid}")
    db.session.add(row)
    db.session.commit()
    return row


def _task(org, uid=None):
    uid = uid or uuid.uuid4().hex
    execution_key = f"exec-{uid}"
    external_task_id = f"manus-{uid}"
    request_id = f"req-{uid}"
    execution_ledger.begin(
        organization_id=org.id, execution_key=execution_key, plan_hash="plan-recon",
    )
    external_task_lifecycle.create_submission(
        organization_id=org.id, provider_id="manus", external_task_id=external_task_id,
        execution_key=execution_key, plan_hash="plan-recon", action="manus.task.create",
        request_id=request_id,
    )
    execution_ledger.finish(
        organization_id=org.id, execution_key=execution_key, status="submitted",
        receipt={"provider_id": "manus", "external_task_id": external_task_id,
                 "request_id": request_id, "status": "submitted"},
    )
    return execution_key, external_task_id, request_id


def test_late_completion_after_ambiguous_reconciles_only_exact_reserved_identity():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        external_task_lifecycle.mark_ambiguous(
            organization_id=org.id, execution_key=execution_key, reason="timeout_after_submit"
        )
        result = external_task_control_plane.reconcile_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
            result={"summary": "late but authentic"},
        )
        assert result["status"] == "completed"
        assert result["result"] == {"summary": "late but authentic"}


def test_provider_task_id_substitution_fails_closed():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, _, request_id = _task(org)
        with pytest.raises(ExternalTaskLifecycleError, match="external_task_id_mismatch"):
            external_task_control_plane.reconcile_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id="manus-attacker", plan_hash="plan-recon", request_id=request_id,
                result={"summary": "substituted"},
            )


def test_provider_request_id_substitution_fails_closed():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, _ = _task(org)
        with pytest.raises(ExternalTaskLifecycleError, match="provider_request_id_mismatch"):
            external_task_control_plane.reconcile_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id="wrong-request",
                result={"summary": "substituted"},
            )


def test_duplicate_completion_is_idempotent_and_result_immutable():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        first = external_task_lifecycle.reconcile_provider_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
            result={"value": 1},
        )
        second = external_task_lifecycle.reconcile_provider_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
            result={"value": 1},
        )
        assert first["id"] == second["id"]
        assert second["status"] == "completed"
        with pytest.raises(ExternalTaskLifecycleError, match="completed_result_substitution"):
            external_task_lifecycle.reconcile_provider_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
                result={"value": 2},
            )


def test_cross_tenant_completion_fails_closed():
    with application.app_context():
        db.create_all()
        owner = _org("Owner")
        attacker = _org("Attacker")
        execution_key, external_task_id, request_id = _task(owner)
        with pytest.raises(ExternalTaskLifecycleError, match="external_task_not_found"):
            external_task_control_plane.reconcile_completion(
                organization_id=attacker.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
                result={"summary": "cross tenant"},
            )


def test_completion_replay_cannot_change_completed_identity():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        external_task_lifecycle.reconcile_provider_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
            result={"summary": "original"},
        )
        with pytest.raises(ExternalTaskLifecycleError, match="completed_result_substitution"):
            external_task_lifecycle.reconcile_provider_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
                result={"summary": "replayed attacker result"},
            )


def test_failed_or_cancelled_state_rejects_new_completion():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=execution_key, status="running"
        )
        external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=execution_key, status="failed"
        )
        with pytest.raises(ExternalTaskLifecycleError, match="stale_external_task_reconciliation"):
            external_task_lifecycle.reconcile_provider_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
                result={"summary": "late after failure"},
            )


def test_stale_reconciliation_rejects_invalid_submission_state():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=execution_key, status="running"
        )
        external_task_lifecycle.update_state(
            organization_id=org.id, execution_key=execution_key, status="cancelled"
        )
        with pytest.raises(ExternalTaskLifecycleError, match="stale_external_task_reconciliation"):
            external_task_control_plane.reconcile_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
                result={"summary": "stale"},
            )


def test_reconciliation_updates_receipt_without_changing_execution_identity():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        external_task_lifecycle.reconcile_provider_completion(
            organization_id=org.id, execution_key=execution_key, provider_id="manus",
            external_task_id=external_task_id, plan_hash="plan-recon", request_id=request_id,
            result={"value": "final"},
        )
        ledger = execution_ledger.get(organization_id=org.id, execution_key=execution_key)
        assert ledger["status"] == "completed"
        assert ledger["receipt"]["provider_id"] == "manus"
        assert ledger["receipt"]["external_task_id"] == external_task_id
        assert ledger["receipt"]["request_id"] == request_id
        assert ledger["receipt"]["provider_completion"]["status"] == "completed"
        assert ledger["receipt"]["provider_completion"]["result_digest"]


def test_reconciliation_rejects_ledger_task_substitution_before_state_mutation():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        with pytest.raises(ExternalTaskLifecycleError, match="external_task_id_mismatch"):
            external_task_lifecycle.reconcile_provider_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id="manus-substitute", plan_hash="plan-recon", request_id=request_id,
                result={"value": "attacker"},
            )
        assert execution_ledger.get(
            organization_id=org.id, execution_key=execution_key
        )["status"] == "submitted"


def test_reconciliation_rejects_ledger_request_substitution_before_state_mutation():
    with application.app_context():
        db.create_all()
        org = _org()
        execution_key, external_task_id, request_id = _task(org)
        with pytest.raises(ExternalTaskLifecycleError, match="provider_request_id_mismatch"):
            external_task_lifecycle.reconcile_provider_completion(
                organization_id=org.id, execution_key=execution_key, provider_id="manus",
                external_task_id=external_task_id, plan_hash="plan-recon", request_id="wrong",
                result={"value": "attacker"},
            )
        assert execution_ledger.get(
            organization_id=org.id, execution_key=execution_key
        )["status"] == "submitted"
