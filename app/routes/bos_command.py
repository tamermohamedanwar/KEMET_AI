from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

from app.services.business_control_loop import BusinessControlLoopService
from app.services.business_feedback import business_feedback
from app.services.decision_learning import decision_learning
from app.services.decision_feedback_loop import decision_feedback_loop
from app.services.outcome_priority import OutcomePriorityService
from app.services.bos_intelligence import BOSIntelligenceService
from app.services.saas_control_plane import saas_control_plane
from app.services.monetization_guard import monetization_guard

from app.automation.orchestrator import orchestrator
from app.core.orchestration.command_center_wiring import KemetCommandCenterWiring
from app.core.decision.decision_engine import DecisionEngine


bos_command_bp = Blueprint(
    "bos_command",
    __name__,
    url_prefix="/api/bos",
)


_kemet_command_center = KemetCommandCenterWiring()
_kemet_decision_engine = DecisionEngine()
@bos_command_bp.get("/saas-control")
@login_required
def bos_saas_control():
    organization_id = getattr(current_user, "organization_id", None)
    result = saas_control_plane.overview(organization_id)
    return jsonify(result), 200 if result.get("success") else 400


@bos_command_bp.post("/plan")
@login_required
def bos_command_plan():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command") or data.get("instruction") or "").strip()
    if not command:
        return jsonify({"success": False, "error": "command_required"}), 400
    try:
        plan = orchestrator.plan(command)
        return jsonify(plan), 200
    except ValueError as exc:
        return jsonify({
            "success": False,
            "status": "unmapped",
            "error": "command_not_mapped",
            "message": str(exc),
        }), 422
    except Exception:
        return jsonify({
            "success": False,
            "error": "planner_error",
            "message": "Planner could not safely create a plan.",
        }), 500


@bos_command_bp.post("/command")
@login_required
def bos_command():
    # Kemet advisory intelligence layer.
    # Existing orchestrator execution remains intact and governed.
    kemet_center = KemetCommandCenterWiring()

    data = request.get_json(silent=True) or {}

    command = str(
        data.get("command")
        or data.get("instruction")
        or ""
    ).strip()

    if not command:
        return jsonify({
            "success": False,
            "error": "command_required",
        }), 400

    organization_id = getattr(
        current_user,
        "organization_id",
        None,
    )

    user_id = getattr(
        current_user,
        "id",
        None,
    )

    if not organization_id:
        return jsonify({
            "success": False,
            "error": "organization_required",
        }), 400

    # Kemet live business context.
    # Tenant identity is derived from the authenticated user.
    live_command_context = _kemet_command_center.build_command_context(
        organization_id=organization_id,
        user_id=user_id,
        message=command,
    )

    # Kemet Decision Engine consumes the live tenant context.
    live_decision = _kemet_decision_engine.decide(
        command=command,
        live_context=live_command_context,
    )

    try:
        result = orchestrator.execute(
            command,
            organization_id=organization_id,
            user_id=user_id,
        )

        status = result.get("status", "unknown")

        if not result.get("success", False):
            if status in {
                "waiting_approval",
                "pending",
            }:
                http_status = 200
            else:
                http_status = 422
        else:
            http_status = 200

        return jsonify({
            "success": result.get("success", False),
            "status": status,
            "command": command,
            "organization_id": organization_id,
            "user_id": user_id,
            "intent": result.get("intent"),
            "action": result.get("action"),
            "parameters": result.get("parameters", {}),
            "confidence": result.get("confidence"),
            "requires_approval": result.get(
                "requires_approval",
                False,
            ),
            "workflow_id": result.get("workflow_id"),
            "workflow_name": result.get("workflow_name"),
            "result": result.get("result"),
            "live_context": live_command_context,
            "decision": live_decision,
            "dispatch": result.get("dispatch"),
            "reason": result.get("reason"),
            "message": result.get("message"),
        }), http_status

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "orchestrator_error",
            "message": str(exc),
        }), 500


@bos_command_bp.get("/capabilities/analytics")
@login_required
def bos_capability_analytics():
    from app.services.capability_analytics import capability_analytics
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.feature(organization_id, "advanced_analytics")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    return jsonify(capability_analytics.summary(organization_id)), 200


@bos_command_bp.get("/capabilities")
@login_required
def bos_capabilities():
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    lifecycle = request.args.get("lifecycle")
    try:
        data = capability_registry.catalog(lifecycle=lifecycle)
    except ValueError:
        return jsonify({"success": False, "error": "invalid_lifecycle"}), 400
    return jsonify({"success": True, "engine": "kemet_capability_registry", "version": capability_registry.VERSION, "data": data}), 200


@bos_command_bp.get("/capabilities/<path:capability_id>")
@login_required
def bos_capability(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.capability(organization_id, capability_id)
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "capability_id": capability_id, "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    definition = capability_registry.get(capability_id)
    if not definition:
        return jsonify({"success": False, "error": "capability_not_found"}), 404
    return jsonify({"success": True, "engine": "kemet_capability_registry", "version": capability_registry.VERSION, "data": definition}), 200


@bos_command_bp.post("/capabilities/<path:capability_id>/plan")
@login_required
def bos_capability_plan(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    gate = monetization_guard.capability(organization_id, capability_id)
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "capability_id": capability_id, "plan": gate.get("plan")}), 403
    from app.services.capability_registry import capability_registry
    data = request.get_json(silent=True) or {}
    try:
        result = capability_registry.plan(capability_id, data.get("parameters") or {})
        return jsonify(result), 200
    except ValueError:
        return jsonify({"success": False, "error": "capability_unavailable"}), 422


@bos_command_bp.get("/playbooks")
@login_required
def bos_playbooks():
    from app.automation.playbook_engine import playbook_engine
    return jsonify({
        "success": True,
        "engine": "kemet_playbook_catalog",
        "version": playbook_engine.VERSION,
        "governance": {"advisory": True, "approval_required": True, "external_execution": False},
        "data": playbook_engine.catalog(),
    }), 200


@bos_command_bp.get("/playbooks/<action>")
@login_required
def bos_playbook(action):
    from app.automation.playbook_engine import playbook_engine
    definition = playbook_engine.get_definition(action)
    if not definition:
        return jsonify({"success": False, "error": "playbook_not_found"}), 404
    return jsonify({
        "success": True,
        "engine": "kemet_playbook_catalog",
        "version": playbook_engine.VERSION,
        "data": definition,
        "governance": {"advisory": True, "approval_required": True, "external_execution": False},
    }), 200


@bos_command_bp.post("/capabilities/<path:capability_id>/attribution")
@login_required
def bos_capability_attribution(capability_id):
    organization_id = getattr(current_user, "organization_id", None)
    data = request.get_json(silent=True) or {}
    from app.services.business_outcome_attribution import BusinessOutcomeAttribution
    result = BusinessOutcomeAttribution.build(
        organization_id, capability_id, data.get("before") or {}, data.get("after") or {}
    )
    return jsonify(result), 200 if result.get("success") else (400 if result.get("error") == "organization_required" else 404)


@bos_command_bp.post("/outcome-decision-loop")
@login_required
def outcome_decision_loop():
    """Read-only feedback loop: observed outcomes re-rank pending decisions."""
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        payload = request.get_json(silent=True) or {}
        period = payload.get("period", "30d")
        decisions = payload.get("decisions")
        if decisions is None:
            decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        ranked = OutcomePriorityService.rank(organization_id, decisions, period=period)
        return jsonify({
            "success": True,
            "engine": "kemet_outcome_decision_loop",
            "version": "1.0",
            "organization_id": organization_id,
            "period": period,
            "items": ranked.get("decisions", ranked.get("items", [])),
            "count": len(ranked.get("decisions", ranked.get("items", []))),
            "feedback": {"observed_outcomes": True, "re_ranking": True, "causal_claim": False, "roi_claim": False},
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False, "approval_required_for_execution": True},
        }), 200
    except Exception:
        current_app.logger.exception("outcome_decision_loop_unavailable")
        return jsonify({"success": False, "error": "outcome_decision_loop_unavailable"}), 500


@bos_command_bp.post("/outcome-priority")
@login_required
def bos_outcome_priority():
    from app.services.outcome_priority import outcome_priority
    organization_id = getattr(current_user, "organization_id", None)
    data = request.get_json(silent=True) or {}
    period = str(data.get("period") or "30d").strip()
    decisions = data.get("decisions") or []
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        result = outcome_priority.rank(organization_id, decisions, period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "outcome_priority_unavailable", "message": "Kemet could not safely rank outcome priorities."}), 500


@bos_command_bp.post("/decision-learning")
@login_required
def bos_decision_learning():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    period = str(data.get("period") or "30d").strip()
    decisions = data.get("decisions") or []
    try:
        result = decision_learning.enrich(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_learning_unavailable", "message": "Kemet could not safely build decision learning signals."}), 500


@bos_command_bp.get("/decision-learning")
@login_required
def bos_decision_learning_summary():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    period = str(request.args.get("period") or "30d").strip()
    try:
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        result = decision_learning.build(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_learning_unavailable", "message": "Kemet could not safely build decision learning signals."}), 500


@bos_command_bp.get("/decision-intelligence")
@login_required
def bos_decision_intelligence():
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    period = str(request.args.get("period") or "30d").strip()
    try:
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        from app.services.decision_intelligence import decision_intelligence
        result = decision_intelligence.build(organization_id, decisions, period=period)
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "decision_intelligence_unavailable", "message": "Kemet could not safely build decision intelligence."}), 500


@bos_command_bp.get("/outcome-intelligence")
@login_required
def bos_outcome_intelligence():
    from app.services.outcome_intelligence import outcome_intelligence
    organization_id = getattr(current_user, "organization_id", None)
    period = str(request.args.get("period") or "30d").strip()
    capability_id = request.args.get("capability_id")
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        if capability_id:
            result = outcome_intelligence.build(organization_id, capability_id, period)
        else:
            result = outcome_intelligence.summary(organization_id, period=period)
        return jsonify(result), 200 if result.get("success") else 404
    except Exception:
        return jsonify({"success": False, "error": "outcome_intelligence_unavailable", "message": "Kemet could not safely build outcome intelligence."}), 500


@bos_command_bp.get("/outcome")
@login_required
def bos_outcome():
    data = request.args
    organization_id = getattr(current_user, "organization_id", None)
    period = str(data.get("period") or "30d").strip()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.business_outcome_service import business_outcome_service
        result = business_outcome_service.build(organization_id, period=period)
        return jsonify(result), 200
    except Exception:
        return jsonify({
            "success": False,
            "error": "outcome_unavailable",
            "message": "Kemet could not safely build the business outcome snapshot.",
        }), 500


@bos_command_bp.post("/operate")
@login_required
def bos_operate():
    data = request.get_json(silent=True) or {}
    command = str(data.get("command") or data.get("instruction") or "").strip()
    organization_id = getattr(current_user, "organization_id", None)
    if not command:
        return jsonify({"success": False, "error": "command_required"}), 400
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    gate = monetization_guard.feature(organization_id, "bos")
    if not gate.get("allowed"):
        return jsonify({"success": False, "error": "feature_not_entitled", "reason": gate.get("reason"), "plan": gate.get("plan")}), 403
    try:
        from app.services.bos_runtime import bos_runtime
        result = bos_runtime.operate(command, organization_id, getattr(current_user, "id", None))
        http_status = 200 if result.get("success") or result.get("status") == "waiting_approval" else 422
        return jsonify({"success": result.get("success", False), "status": result.get("status", "operated"), **result}), http_status
    except ValueError as exc:
        return jsonify({"success": False, "status": "unmapped", "error": "command_not_mapped", "message": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "status": "blocked", "error": "operation_not_safe", "message": "Kemet stopped before unsafe execution."}), 500


@bos_command_bp.post("/approvals/<int:approval_id>/approve")
@login_required
def bos_approve(approval_id):
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    if getattr(current_user, "role", None) != "admin":
        return jsonify({"success": False, "error": "admin_approval_required"}), 403
    from app.services.bos_runtime import bos_runtime
    result = bos_runtime.approve(approval_id, organization_id, current_user.id)
    return jsonify(result), 200 if result.get("success") else 422


@bos_command_bp.post("/approvals/<int:approval_id>/reject")
@login_required
def bos_reject(approval_id):
    organization_id = getattr(current_user, "organization_id", None)
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    if getattr(current_user, "role", None) != "admin":
        return jsonify({"success": False, "error": "admin_approval_required"}), 403
    data = request.get_json(silent=True) or {}
    from app.services.bos_runtime import bos_runtime
    result = bos_runtime.reject(approval_id, organization_id, current_user.id, data.get("reason"))
    return jsonify(result), 200 if result.get("success") else 422


@bos_command_bp.route("/business-control-loop/feedback-summary", methods=["GET"])
@login_required
def bos_business_feedback_summary():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
        items = []
        for decision in decisions or []:
            feedback = decision.get("feedback") or {}
            if feedback:
                feedback["decision_id"] = decision.get("decision_id") or decision.get("id")
                feedback["capability_id"] = decision.get("capability_id") or decision.get("action")
                items.append(feedback)
        result = decision_feedback_loop.build(items)
        result["organization_id"] = organization_id
        result["review_queue"] = {"count": len(decisions or []), "approval_required": True, "auto_execute": False}
        return jsonify(result), 200
    except Exception:
        return jsonify({"success": False, "error": "business_feedback_summary_unavailable"}), 500


@bos_command_bp.route("/business-control-loop/feedback", methods=["POST"])
@login_required
def bos_business_control_loop_feedback():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        payload = request.get_json(silent=True) or {}
        result = business_feedback.build(
            organization_id,
            decision_id=payload.get("decision_id"),
            capability_id=payload.get("capability_id"),
            signal=payload.get("signal", "neutral"),
            note=payload.get("note", ""),
            period=payload.get("period", "30d"),
        )
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "business_control_loop_feedback_unavailable"}), 500


@bos_command_bp.route("/business-control-loop", methods=["GET", "POST"])
@login_required
def bos_business_control_loop():
    try:
        organization_id = getattr(current_user, "organization_id", None)
        if not organization_id:
            return jsonify({"success": False, "error": "organization_required"}), 400
        if request.method == "GET":
            decisions = BOSIntelligenceService.get_decisions(organization_id, limit=10)
            period = str(request.args.get("period") or "30d").strip()
        else:
            payload = request.get_json(silent=True) or {}
            decisions = payload.get("decisions") or []
            period = payload.get("period", "30d")
        result = BusinessControlLoopService.build(
            organization_id,
            decisions=decisions,
            period=period,
        )
        return jsonify(result), 200 if result.get("success") else 400
    except Exception:
        return jsonify({"success": False, "error": "business_control_loop_unavailable"}), 500



