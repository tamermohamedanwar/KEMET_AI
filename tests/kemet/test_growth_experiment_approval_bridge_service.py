from app.services.growth_experiment_approval_bridge_service import growth_experiment_approval_bridge_service
from wsgi import application
from app import db


def proposal():
    return {
        "channel": "facebook",
        "basis": {"verified_revenue": 100, "qualified_views": 5000, "reconciled_content_count": 2, "evidence_bindings": [
            {"content_id": "c1", "publication_id": "p1", "execution_key": "e1", "metric_evidence_digest": "m1"},
            {"content_id": "c2", "publication_id": "p2", "execution_key": "e2", "metric_evidence_digest": "m2"},
        ]},
        "proposal": {
            "objective": "validate_repeatable_distribution_or_content_signal",
            "success_metric": "incremental_verified_revenue",
            "guardrail": "do_not_treat_unverified_attribution_as_revenue",
        },
    }


def test_prepares_approval_ready_intent_without_execution():
    result = growth_experiment_approval_bridge_service.prepare(organization_id=1, proposal=proposal())
    assert result["approval_status"] == "approval_required"
    assert result["execution_requested"] is False
    assert result["intent"]["channel"] == "facebook"
    assert result["intent_hash"]
    assert result["governance"]["external_execution"] is False


def test_rejects_unreconciled_proposal():
    item = proposal()
    item["basis"]["reconciled_content_count"] = 0
    try:
        growth_experiment_approval_bridge_service.prepare(organization_id=1, proposal=item)
    except ValueError as exc:
        assert str(exc) == "reconciled_evidence_required"
    else:
        raise AssertionError("expected reconciled_evidence_required")


def test_prepares_canonical_approval_package_binding():
    result = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
    assert result["approval_package"]["organization_id"] == 1
    assert result["approval_package"]["approval_required"] is True
    assert result["approval_package"]["package_hash"]
    assert result["context"]["plan_hash"] == result["approval_package"]["plan_hash"]
    assert result["risk_assessment"]["approval_required"] is True
    assert result["execution_requested"] is False
    assert result["governance"]["approval_package_bound"] is True


def test_prepares_package_for_same_input_deterministically():
    first = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
    second = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
    assert first["approval_package"]["package_hash"] == second["approval_package"]["package_hash"]
    assert first["context"]["context_fingerprint"] == second["context"]["context_fingerprint"]


def test_approved_package_creates_gate_handoff_for_existing_action():
    prepared = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
    result = growth_experiment_approval_bridge_service.approve_to_gate(
        organization_id=1,
        package_payload=prepared["approval_package"],
        plan=prepared["plan"],
        approver_id=7,
        approved=True,
        reason="reviewed",
        action="facebook_publish",
        execution_key="exec-growth-001",
    )
    assert result["status"] == "approved_for_gate"
    assert result["gate_handoff"]["organization_id"] == 1
    assert result["gate_handoff"]["action"] == "facebook_publish"
    assert result["one_time_authorization_required"] is True
    assert result["execution_requested"] is False


def test_approved_gate_issues_bound_one_time_authorization():
    from app.core.execution.authorization import execution_authorization
    previous = execution_authorization.secret
    execution_authorization.secret = "test-secret"
    try:
        prepared = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
        gated = growth_experiment_approval_bridge_service.approve_to_gate(
            organization_id=1,
            package_payload=prepared["approval_package"],
            plan=prepared["plan"],
            approver_id=7,
            approved=True,
            reason="reviewed",
            action="facebook_publish",
            execution_key="exec-growth-auth-001",
        )
        issued = growth_experiment_approval_bridge_service.issue_one_time_authorization(
            organization_id=1,
            plan=prepared["plan"],
            gate_handoff=gated["gate_handoff"],
        )
        assert issued["authorization"]["authorized"] is True
        assert issued["authorization"]["one_time"] is True
        assert issued["authorization"]["authorization_source"] == "human_approval"
        assert issued["authorization"]["handoff_hash"] == gated["gate_handoff"]["handoff_hash"]
        assert issued["authorization"]["execution_key"] == "exec-growth-auth-001"
        from app.core.execution.central_gate import CentralExecutionGate
        from app.core.central_gate_handoff import GateHandoff
        gate_result = CentralExecutionGate().authorize_with_handoff(
            prepared["plan"],
            issued["authorization"],
            GateHandoff(**gated["gate_handoff"]),
            "facebook_publish",
            "exec-growth-auth-001",
        )
        assert gate_result["allowed"] is True
        assert gate_result["executed"] is False
    finally:
        execution_authorization.secret = previous


def test_authorized_dry_run_reaches_canonical_runtime_and_consumes_once():
    from app.core.execution.authorization import execution_authorization
    from app.automation.action_registry import registry
    previous_secret = execution_authorization.secret
    previous_handler = registry.get("facebook_publish")
    execution_authorization.secret = "test-secret"
    try:
        with application.app_context():
            db.create_all()
            prepared = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
            gated = growth_experiment_approval_bridge_service.approve_to_gate(
                organization_id=1,
                package_payload=prepared["approval_package"],
                plan=prepared["plan"],
                approver_id=7,
                approved=True,
                reason="reviewed",
                action="facebook_publish",
                execution_key="exec-growth-runtime-001",
            )
            issued = growth_experiment_approval_bridge_service.issue_one_time_authorization(
                organization_id=1,
                plan=prepared["plan"],
                gate_handoff=gated["gate_handoff"],
            )
            registry.register("facebook_publish", lambda parameters, user_id=None: {
                "success": True,
                "status": "completed",
                "executed": True,
                "external_execution": False,
                "dry_run": True,
            })
            first = growth_experiment_approval_bridge_service.execute_authorized_dry_run(
                organization_id=1,
                plan=prepared["plan"],
                authorization=issued["authorization"],
                user_id=7,
            )
            assert first["success"] is True
            assert first["governance"]["canonical_runtime"] is True
            assert first["governance"]["one_time_authorization_consumed"] is True
            second = growth_experiment_approval_bridge_service.execute_authorized_dry_run(
                organization_id=1,
                plan=prepared["plan"],
                authorization=issued["authorization"],
                user_id=7,
            )
            assert second["success"] is False
            assert second["result"]["error"] == "execution_authorization_used"
    finally:
        if previous_handler is not None:
            registry.register("facebook_publish", previous_handler)
        execution_authorization.secret = previous_secret


def test_authorization_rejects_tenant_mismatch():
    from app.core.execution.authorization import execution_authorization
    previous = execution_authorization.secret
    execution_authorization.secret = "test-secret"
    try:
        prepared = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
        gated = growth_experiment_approval_bridge_service.approve_to_gate(
            organization_id=1,
            package_payload=prepared["approval_package"],
            plan=prepared["plan"],
            approver_id=7,
            approved=True,
            reason="reviewed",
            action="facebook_publish",
            execution_key="exec-growth-auth-002",
        )
        try:
            growth_experiment_approval_bridge_service.issue_one_time_authorization(
                organization_id=2, plan=prepared["plan"], gate_handoff=gated["gate_handoff"]
            )
        except ValueError as exc:
            assert str(exc) == "tenant_context_mismatch"
        else:
            raise AssertionError("expected tenant_context_mismatch")
    finally:
        execution_authorization.secret = previous


def test_unknown_action_fails_closed():
    prepared = growth_experiment_approval_bridge_service.prepare_approval_package(organization_id=1, proposal=proposal(), user_id=7)
    try:
        growth_experiment_approval_bridge_service.approve_to_gate(
            organization_id=1, package_payload=prepared["approval_package"], plan=prepared["plan"],
            approver_id=7, approved=True, action="growth_experiment_execute", execution_key="exec-growth-002"
        )
    except ValueError as exc:
        assert str(exc) == "action_not_governed"
    else:
        raise AssertionError("expected action_not_governed")


def test_rejects_invalid_organization():
    try:
        growth_experiment_approval_bridge_service.prepare(organization_id=0, proposal=proposal())
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("expected organization_required")
