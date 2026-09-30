from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_unified_approval_routes_exist():
    from wsgi import application
    routes = {str(rule) for rule in application.url_map.iter_rules()}
    assert "/command-center/api/bos/plan" in routes
    assert "/command-center/api/bos/decide-plan" in routes
    assert "/command-center/api/bos/execute-approved" in routes


def test_unified_approval_uses_canonical_runtime():
    text = (ROOT / "app/routes/command_center.py").read_text()
    assert "decide_approval(" in text
    assert "create_gate_handoff(" in text
    assert "verify_gate_handoff(" in text
    assert "execution_authorization.create_authorization" in text
    assert "canonical_execution_runtime.execute" in text
    assert "execution_evidence_fabric.execution_record" in text


def test_unified_approval_binds_package_and_route():
    text = (ROOT / "app/routes/command_center.py").read_text()
    assert "package.package_hash != package_hash" in text
    assert '"central_gate_handoff_hash"' in text
    assert '"federation_routing"' in text
    assert '"data_policy"' in text and '"entitlement_fingerprint"' in text
    assert '"approval_package_mismatch"' in text


def test_command_center_ui_uses_unified_plan_and_decision_flow():
    text = (ROOT / "app/templates/command_center.html").read_text()
    assert '"/command-center/api/bos/plan"' in text
    assert '"/command-center/api/bos/decide-plan"' in text
    assert "pendingPlan" in text
    assert "approval_package_hash" in text


def test_no_execution_path_without_gate_handoff():
    text = (ROOT / "app/routes/command_center.py").read_text()
    gate = text.index("handoff = create_gate_handoff(")
    runtime = text.index("canonical_execution_runtime.execute(")
    assert gate < runtime


def test_gate_handoff_contract_is_bound_to_execution_key():
    from app.core.approval_package import build_approval_package
    from app.core.approval_decision import decide_approval
    from app.core.central_gate_handoff import create_gate_handoff, verify_gate_handoff
    from app.core.plan_context import PlanContext, bind_plan_context
    from app.core.plan_risk import assess_plan_risk
    from app.core.task_planner import TaskPlanningEngine
    plan = TaskPlanningEngine().plan("build a website", organization_id=1, task_id="gate-test")
    binding = bind_plan_context(plan, PlanContext(organization_id=1))
    package = build_approval_package(plan, binding, assess_plan_risk(plan))
    decision = decide_approval(package, 1, True, "test")
    handoff = create_gate_handoff(package, decision, action="business_insights", execution_key="gate-test")
    assert verify_gate_handoff(handoff, organization_id=1, execution_key="gate-test")
    assert not verify_gate_handoff(handoff, organization_id=2, execution_key="gate-test")


def test_route_is_recomputed_before_approval_package_verification():
    text = (ROOT / "app/routes/command_center.py").read_text()
    route = text.index("routing = federation_routing_preview.preview(")
    package = text.index("evidence_context = execution_evidence_fabric.context_package(", route)
    verify = text.index("if package.package_hash != package_hash:")
    assert route < package < verify


