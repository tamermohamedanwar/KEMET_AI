from app.core.automation_control_plane import (
    AutomationControlPlane,
    AutomationLimits,
    AutomationPlan,
    AutomationStep,
)
from app.core.integration.connector_contract import ConnectorContract
from app.core.integration.connector_registry import connector_registry


def _plan(*steps, policy="auto_safe", dry_run=True):
    return AutomationPlan(
        plan_id="test-plan",
        organization_id=1,
        trigger="manual",
        steps=tuple(steps),
        dry_run=dry_run,
        approval_policy=policy,
    )


def test_safe_plan_compiles_without_execution():
    plan = _plan(
        AutomationStep(
            step_id="step-1",
            action="business_insights",
            risk="low",
            requires_approval=False,
        )
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is True
    assert result["status"] == "simulation_ready"
    assert result["execution"]["executed"] is False
    assert result["execution"]["external_execution"] is False
    assert result["execution"]["database_mutation"] is False
    assert len(result["plan_hash"]) == 64


def test_unknown_action_fails_closed():
    plan = _plan(
        AutomationStep(
            step_id="step-1",
            action="not_a_real_action",
            risk="low",
        )
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "unknown_action:not_a_real_action" in result["validation"]["errors"]


def test_high_risk_plan_requires_human_policy():
    plan = _plan(
        AutomationStep(
            step_id="step-1",
            action="send_notification",
            risk="high",
            requires_approval=True,
            reversible=False,
        )
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "high_risk_plan_cannot_use_auto_safe" in result["validation"]["errors"]


def test_external_connector_is_tenant_scoped():
    connector_registry.clear()
    connector_registry.register(
        ConnectorContract(
            connector_id="whatsapp",
            organization_id=1,
            operations=("send_message",),
            risk_tier="high",
            approval_level="human",
            evidence_required=True,
        )
    )
    plan = AutomationPlan(
        plan_id="connector-plan",
        organization_id=2,
        trigger="manual",
        steps=(
            AutomationStep(
                step_id="step-1",
                action="send_notification",
                connector_id="whatsapp",
                operation="send_message",
                risk="high",
                requires_approval=True,
                reversible=False,
            ),
        ),
        approval_policy="human",
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "connector_not_allowed:whatsapp:send_message" in result["validation"]["errors"]
    connector_registry.clear()


def test_budget_limits_fail_closed():
    plan = AutomationPlan(
        plan_id="budget-plan",
        organization_id=1,
        trigger="manual",
        steps=(
            AutomationStep(step_id="one", action="business_insights"),
            AutomationStep(step_id="two", action="business_insights"),
        ),
        limits=AutomationLimits(max_steps=1),
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "step_budget_exceeded" in result["validation"]["errors"]


def test_plan_cannot_raise_cost_ceiling_to_bypass_dow_guard():
    plan = AutomationPlan(
        plan_id="dow-ceiling",
        organization_id=1,
        trigger="manual",
        steps=(AutomationStep(step_id="one", action="business_insights", estimated_cost=150.0),),
        limits=AutomationLimits(max_estimated_cost=150.0),
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "estimated_cost_ceiling_exceeded" in result["validation"]["errors"]


def test_nan_cost_fails_closed():
    plan = _plan(AutomationStep(step_id="one", action="business_insights", estimated_cost=float("nan")))
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "invalid_cost:one" in result["validation"]["errors"]


def test_infinite_cost_fails_closed():
    plan = _plan(AutomationStep(step_id="one", action="business_insights", estimated_cost=float("inf")))
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "invalid_cost:one" in result["validation"]["errors"]


def test_budget_numeric_types_fail_closed():
    limits = AutomationLimits(max_steps=True, max_retries_per_step=1.5, max_runtime_seconds=0, max_external_operations=1.0, max_estimated_cost=float("nan"))
    plan = AutomationPlan(
        plan_id="budget-types",
        organization_id=1,
        trigger="manual",
        steps=(AutomationStep(step_id="one", action="business_insights"),),
        limits=limits,
    )
    result = AutomationControlPlane().compile(plan)
    assert result["success"] is False
    assert "max_steps_invalid" in result["validation"]["errors"]
    assert "max_retries_invalid" in result["validation"]["errors"]
    assert "max_runtime_invalid" in result["validation"]["errors"]
    assert "max_external_operations_invalid" in result["validation"]["errors"]
    assert "max_estimated_cost_invalid" in result["validation"]["errors"]
