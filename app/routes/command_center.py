
from datetime import datetime, timezone
import json
import subprocess

from flask import Blueprint, jsonify, render_template, request, redirect
from flask_login import login_required, current_user

from app import db

from app.models.automation import (
    AutomationExecution,
    AutomationApproval,
    AutomationWorkflow,
    AutomationAction,
)
from app.models.ticket import Ticket
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.ai_usage import AIUsage
from app.models.audit import AuditRecord
from app.core.execution.governed_executor import governed_execution_service
from app.core.approval_sla import approval_state
from app.core.task_planner import task_planner
from app.core.plan_context import PlanContext, bind_plan_context
from app.core.data_boundary import DataEntitlement, data_boundary
from app.core.plan_risk import assess_plan_risk
from app.core.approval_package import build_approval_package
from app.core.federation.routing_preview import federation_routing_preview
from app.core.federation.specialist_orchestrator import specialist_orchestrator
from app.core.federation.execution_envelope import execution_envelope
from app.core.federation.connection_lifecycle import ConnectionLifecycleService
from app.core.federation.external_task_control_plane import external_task_control_plane
from app.core.approval_decision import decide_approval
from app.core.central_gate_handoff import create_gate_handoff, verify_gate_handoff
from app.core.execution.authorization import execution_authorization
from app.core.execution.runtime import canonical_execution_runtime
from app.core.evidence import execution_evidence_fabric
from app.core.federation.project_intelligence import project_intelligence
from app.core.federation.outcome_control import outcome_control
from app.services.sales_support_command_center import sales_support_command_center
from app.services.distribution_service import distribution_service
from app.services.revenue_collection_service import revenue_collection_service
from app.services.kemet_worlds_intelligence_service import kemet_worlds_intelligence_service
from app.services.public_api_catalog_service import public_api_catalog_service
from app.services.kemet_visibility_intelligence_service import kemet_visibility_intelligence_service
from app.services.youtube_evidence_service import youtube_evidence_service
from app.services.tool_intelligence_registry import tool_intelligence_registry
from app.services.google_sheets_connector_service import google_sheets_connector_service
from app.core.social_credential_store import social_credential_store
from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service
from app.services.mendes.mendes_governed_pilot_service import mendes_governed_pilot_service
from app.services.mendes.mendes_production_job_store import mendes_production_job_store
from app.services.social_measurement_service import social_measurement_service, MeasurementRequest
from app.core.federation.capability_federation import capability_federation
from app.services.content_factory_service import content_factory_service
from app.services.content_revenue_bridge_service import content_revenue_bridge_service
from app.services.content_commercial_loop_service import content_commercial_loop_service
from app.services.publication_measurement_evidence_service import publication_measurement_evidence_service
from app.services.revenue_center_evidence_service import revenue_center_evidence_service
from app.services.revenue_intelligence_service import revenue_intelligence_service
from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service
from app.services.revenue_content_decision_signal_service import revenue_content_decision_signal_service
from app.services.revenue_portfolio_service import revenue_portfolio_service
from app.services.growth_experiment_proposal_service import growth_experiment_proposal_service
from app.services.growth_experiment_approval_bridge_service import growth_experiment_approval_bridge_service
from app.services.visual_direction_service import visual_direction_service
from app.services.cinematic_production_os import cinematic_production_os
from app.core.execution_evidence import execution_evidence


command_center_bp = Blueprint(
    "command_center",
    __name__,
    url_prefix="/command-center",
)


def _organization_id():
    return getattr(current_user, "organization_id", None)


def _count(query):
    try:
        return query.count()
    except Exception:
        return 0


@command_center_bp.route("/")
@login_required
def index():
    return render_template(
        "command_center_minimal.html",
        user=current_user,
    )






@command_center_bp.get("/guide")
@login_required
def command_center_guide():
    language = request.args.get("lang", "ar").lower()
    if language not in {"ar", "en"}:
        language = "ar"
    topic = request.args.get("topic", "command-center").lower()
    allowed_topics = {"command-center", "kemet-worlds", "revenue-center", "entrepreneurship"}
    if topic not in allowed_topics:
        topic = "command-center"
    return render_template("command_center_guide.html", language=language, topic=topic)


@command_center_bp.get("/api/bos/revenue-center")
@login_required
def bos_revenue_center():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    youtube_evidence = None
    try:
        youtube_evidence = youtube_evidence_service.measure(int(organization_id))
    except Exception:
        youtube_evidence = None
    return jsonify({
        "success": True,
        "revenue_center": revenue_collection_service.snapshot(int(organization_id), youtube_evidence),
    })


@command_center_bp.get("/api/bos/content-revenue")
@login_required
def bos_content_revenue():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    content_id = (request.args.get("content_id") or "").strip()
    channel = (request.args.get("channel") or "").strip().lower()
    publication_id = (request.args.get("publication_id") or "").strip()
    execution_key = (request.args.get("execution_key") or "").strip()
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    if not content_id or not channel or not publication_id:
        return jsonify({"success": False, "error": "content_measurement_binding_required"}), 400
    if not execution_key:
        return jsonify({"success": False, "error": "execution_key_required"}), 400
    try:
        history = execution_evidence.history(
            organization_id=int(organization_id), execution_key=execution_key
        )
        payment_evidence = [
            row for row in history
            if row.get("stage") == "payment.completed"
            and isinstance(row.get("receipt"), dict)
        ]
        result = content_revenue_bridge_service.measure_and_attribute(
            organization_id=int(organization_id),
            user_id=int(user_id),
            channel=channel,
            content_id=content_id,
            publication_id=publication_id,
            payment_evidence=payment_evidence,
        )
        summary = revenue_center_evidence_service.summarize(
            organization_id=int(organization_id), content_results=[result]
        )
        return jsonify({
            "success": bool(result.get("success")),
            "content_revenue": result,
            "revenue_center_evidence": summary,
        }), 200 if result.get("success") else 422
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({
            "success": False,
            "error": "content_revenue_unavailable",
            "verified": False,
        }), 503


@command_center_bp.get("/api/bos/revenue-reconciliation")
@login_required
def bos_revenue_reconciliation():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    content_id = (request.args.get("content_id") or "").strip()
    publication_id = (request.args.get("publication_id") or "").strip()
    execution_key = (request.args.get("execution_key") or "").strip()
    if not content_id or not publication_id or not execution_key:
        return jsonify({"success": False, "error": "revenue_identity_binding_required"}), 400
    try:
        history = execution_evidence.history(
            organization_id=int(organization_id), execution_key=execution_key
        )
        result = revenue_identity_reconciliation_service.reconcile(
            organization_id=int(organization_id),
            content_id=content_id,
            publication_id=publication_id,
            execution_key=execution_key,
            evidence=history,
        )
        return jsonify({"success": True, "reconciliation": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "revenue_reconciliation_unavailable"}), 503


def _server_verified_revenue_portfolio(organization_id: int, user_id: int, content_bindings):
    if not isinstance(content_bindings, list) or not content_bindings:
        raise ValueError("content_bindings_required")
    results = []
    for binding in content_bindings:
        if not isinstance(binding, dict):
            continue
        content_id = str(binding.get("content_id") or "").strip()
        channel = str(binding.get("channel") or "").strip().lower()
        publication_id = str(binding.get("publication_id") or "").strip()
        execution_key = str(binding.get("execution_key") or "").strip()
        if not all((content_id, channel, publication_id, execution_key)):
            continue
        result = content_commercial_loop_service.evaluate_verified(
            organization_id=int(organization_id), user_id=int(user_id),
            content_id=content_id, channel=channel,
            publication_id=publication_id, execution_key=execution_key,
        )
        if result.get("success") is True:
            results.append(result)
    return revenue_portfolio_service.aggregate(
        organization_id=int(organization_id), content_results=results
    )


@command_center_bp.post("/api/bos/revenue-portfolio")
@login_required
def bos_revenue_portfolio():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    content_bindings = payload.get("content_bindings")
    try:
        result = _server_verified_revenue_portfolio(
            int(organization_id), int(user_id), content_bindings
        )
        return jsonify({"success": True, "revenue_portfolio": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "revenue_portfolio_unavailable"}), 503


@command_center_bp.post("/api/bos/growth-experiment-proposals")
@login_required
def bos_growth_experiment_proposals():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    content_bindings = payload.get("content_bindings")
    try:
        portfolio = _server_verified_revenue_portfolio(
            int(organization_id), int(user_id), content_bindings
        )
        result = growth_experiment_proposal_service.propose(
            organization_id=int(organization_id), portfolio=portfolio
        )
        return jsonify({
            "success": True,
            "revenue_portfolio": portfolio,
            "growth_experiment_proposals": result,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_proposals_unavailable"}), 503


@command_center_bp.post("/api/bos/growth-experiment-approval-bridge")
@login_required
def bos_growth_experiment_approval_bridge():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    proposal = payload.get("proposal") or {}
    try:
        result = growth_experiment_approval_bridge_service.prepare(
            organization_id=int(organization_id), proposal=proposal
        )
        return jsonify({"success": True, "approval_bridge": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_approval_bridge_unavailable"}), 503


@command_center_bp.post("/api/bos/growth-experiment-approval-package")
@login_required
def bos_growth_experiment_approval_package():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    content_bindings = payload.get("content_bindings")
    channel = str(payload.get("channel") or "").strip().lower()
    if not isinstance(content_bindings, list) or not channel:
        return jsonify({"success": False, "error": "server_verified_proposal_binding_required"}), 400
    try:
        portfolio = _server_verified_revenue_portfolio(
            int(organization_id), int(getattr(current_user, "id", 0) or 0), content_bindings
        )
        proposals = growth_experiment_proposal_service.propose(
            organization_id=int(organization_id), portfolio=portfolio
        )
        matches = [item for item in proposals.get("proposals", []) if item.get("channel") == channel]
        if len(matches) != 1:
            raise ValueError("server_verified_proposal_not_found")
        result = growth_experiment_approval_bridge_service.prepare_approval_package(
            organization_id=int(organization_id), proposal=matches[0], user_id=getattr(current_user, "id", None)
        )
        return jsonify({"success": True, "approval_package": result}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_approval_package_unavailable"}), 503


@command_center_bp.post("/api/bos/growth-experiment-approve")
@login_required
def bos_growth_experiment_approve():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        result = growth_experiment_approval_bridge_service.approve_to_gate(
            organization_id=int(organization_id),
            package_payload=payload.get("approval_package") or {},
            plan=payload.get("plan") or {},
            approver_id=int(getattr(current_user, "id", 0) or 0),
            approved=bool(payload.get("approved", False)),
            reason=str(payload.get("reason") or ""),
            action=str(payload.get("action") or ""),
            execution_key=str(payload.get("execution_key") or ""),
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_approval_failed"}), 503


@command_center_bp.post("/api/bos/growth-experiment-authorization")
@login_required
def bos_growth_experiment_authorization():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        result = growth_experiment_approval_bridge_service.issue_one_time_authorization(
            organization_id=int(organization_id),
            plan=payload.get("plan") or {},
            gate_handoff=payload.get("gate_handoff") or {},
        )
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_authorization_failed"}), 503


@command_center_bp.post("/api/bos/growth-experiment-execute-dry-run")
@login_required
def bos_growth_experiment_execute_dry_run():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        result = growth_experiment_approval_bridge_service.execute_authorized_dry_run(
            organization_id=int(organization_id),
            plan=payload.get("plan") or {},
            authorization=payload.get("authorization") or {},
            user_id=int(getattr(current_user, "id", 0) or 0),
        )
        return jsonify(result), 200 if result.get("success") else 422
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "growth_experiment_dry_run_failed"}), 503


@command_center_bp.get("/api/bos/revenue-intelligence")
@login_required
def bos_revenue_intelligence():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    content_id = (request.args.get("content_id") or "").strip()
    channel = (request.args.get("channel") or "").strip().lower()
    publication_id = (request.args.get("publication_id") or "").strip()
    execution_key = (request.args.get("execution_key") or "").strip()
    if not content_id or not channel or not publication_id or not execution_key:
        return jsonify({"success": False, "error": "revenue_intelligence_binding_required"}), 400
    try:
        history = execution_evidence.history(
            organization_id=int(organization_id), execution_key=execution_key
        )
        payment_evidence = [
            row for row in history
            if row.get("stage") == "payment.completed"
            and isinstance(row.get("receipt"), dict)
        ]
        result = content_revenue_bridge_service.measure_and_attribute(
            organization_id=int(organization_id),
            user_id=int(getattr(current_user, "id", 0)),
            channel=channel,
            content_id=content_id,
            publication_id=publication_id,
            execution_key=execution_key,
            payment_evidence=payment_evidence,
        )
        reconciliation = revenue_identity_reconciliation_service.reconcile(
            organization_id=int(organization_id),
            content_id=content_id,
            publication_id=publication_id,
            execution_key=execution_key,
            evidence=history,
        )
        result["reconciliation"] = reconciliation
        result["execution_key"] = execution_key
        result.setdefault("publication", {})["publication_id"] = publication_id
        intelligence = revenue_intelligence_service.analyze(
            organization_id=int(organization_id), content_results=[result]
        )
        signals = revenue_content_decision_signal_service.build(
            organization_id=int(organization_id),
            intelligence=intelligence,
        )
        return jsonify({
            "success": True,
            "revenue_intelligence": intelligence,
            "reconciliation": reconciliation,
            "revenue_decision_signals": signals,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "revenue_intelligence_unavailable"}), 503


@command_center_bp.get("/api/bos/public-api-catalog")
@login_required
def bos_public_api_catalog():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    return jsonify({"success": True, "public_api_catalog": public_api_catalog_service.snapshot(int(organization_id))})


@command_center_bp.get("/api/bos/kemet-worlds-intelligence")
@login_required
def bos_kemet_worlds_intelligence():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    world_id = request.args.get("world_id") or "kemet-worlds"
    youtube_evidence = None
    try:
        youtube_evidence = youtube_evidence_service.measure(int(organization_id))
    except Exception:
        youtube_evidence = None
    return jsonify({"success": True, "worlds_intelligence": kemet_worlds_intelligence_service.snapshot(int(organization_id), world_id, youtube_evidence)})


@command_center_bp.get("/api/bos/visibility-intelligence")
@login_required
def bos_visibility_intelligence():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    market = request.args.get("market") or "global"
    return jsonify({"success": True, "visibility_intelligence": kemet_visibility_intelligence_service.snapshot(int(organization_id), market)})


@command_center_bp.get("/api/bos/youtube-evidence")
@login_required
def bos_youtube_evidence():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        evidence = youtube_evidence_service.measure(int(organization_id))
        return jsonify({"success": True, "youtube_evidence": evidence})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "verified": False}), 422
    except subprocess.TimeoutExpired:
        return jsonify({"success": False, "error": "youtube_measurement_timeout", "verified": False}), 504
    except Exception:
        return jsonify({"success": False, "error": "youtube_evidence_unavailable", "verified": False}), 503


@command_center_bp.get("/api/bos/social-measurement")
@login_required
def bos_social_measurement():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    channel = (request.args.get("channel") or "").strip().lower()
    publication_id = (request.args.get("publication_id") or "").strip()
    execution_key = (request.args.get("execution_key") or "").strip()
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required", "verified": False}), 400
    if channel not in {"facebook", "instagram"} or not publication_id or not execution_key:
        return jsonify({"success": False, "error": "measurement_binding_required", "verified": False}), 400
    try:
        result = publication_measurement_evidence_service.verify(
            organization_id=int(organization_id),
            user_id=int(user_id),
            execution_key=execution_key,
            channel=channel,
            publication_id=publication_id,
        )
        return jsonify({"success": bool(result.get("success")), "social_measurement": result}), 200 if result.get("success") else 422
    except Exception:
        return jsonify({"success": False, "error": "social_measurement_unavailable", "verified": False}), 503


@command_center_bp.get("/api/bos/project-intelligence")
@login_required
def bos_project_intelligence():
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    snapshot = project_intelligence.snapshot(
        int(organization_id), int(user_id),
        project_id=request.args.get("project_id") or "kemet-ai",
    )
    return jsonify({"success": True, "project_intelligence": snapshot.as_dict()})


@command_center_bp.get("/api/bos/sales-support")
@login_required
def bos_sales_support():
    """Return a tenant-scoped, read-only sales priority snapshot."""
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        snapshot = sales_support_command_center.snapshot(organization_id=int(organization_id))
        return jsonify({"success": True, "sales_support": snapshot})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@command_center_bp.get("/api/bos/sales-support/follow-up")
@login_required
def bos_sales_support_follow_up():
    """Build a tenant-bound, approval-ready follow-up proposal without executing it."""
    organization_id = _organization_id()
    lead_id = request.args.get("lead_id", type=int)
    channel = (request.args.get("channel") or "web").strip().lower()
    if not organization_id or not lead_id:
        return jsonify({"success": False, "error": "organization_and_lead_required"}), 400

    from app.models.demo_lead import DemoLead
    from app.services.governed_followup_service import governed_followup_service

    lead = db.session.get(DemoLead, lead_id)
    if not lead or lead.organization_id != int(organization_id):
        return jsonify({"success": False, "error": "lead_organization_mismatch"}), 404

    qualification_status = str(lead.status or "").strip().lower()
    qualification = {
        "status": "qualified" if qualification_status in {"qualified", "proposal"} else qualification_status,
        "missing_fields": [],
        "score": int(lead.lead_score or 0),
    }
    try:
        plan = governed_followup_service.build_plan(
            organization_id=int(organization_id),
            qualification=qualification,
            channel=channel,
            lead_id=lead.id,
            customer_id=None,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "follow_up": plan})


@command_center_bp.get("/api/bos/distribution")
@login_required
def bos_distribution():
    """Return a tenant-scoped advisory distribution preview without mutating ownership."""
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        snapshot = distribution_service.preview_sales(
            organization_id=int(organization_id),
            limit=request.args.get("limit", type=int),
        )
        return jsonify({"success": True, "distribution": snapshot})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@command_center_bp.route("/api/bos/visual-directions", methods=["POST"])
@login_required
def bos_visual_directions():
    """Return contextual visual directions without creating an execution path."""
    organization_id = _organization_id()
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or payload.get("instruction") or "").strip()
    if not command:
        return jsonify({"success": False, "error": "command_required"}), 400
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        directions = visual_direction_service.suggest(command, payload.get("task_type"))
        return jsonify({
            "success": True,
            "version": visual_direction_service.VERSION,
            "directions": directions,
            "detail_options": {item["id"]: visual_direction_service.details(item["id"])["options"] for item in directions},
            "source_of_truth": "canonical_production_state",
            "executed": False,
            "external_call": False,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400


@command_center_bp.route("/api/bos/plan", methods=["POST"])
@login_required
def bos_plan_preview():
    """Build a read-only governed plan for the Unified Command Center."""
    organization_id = _organization_id()
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or payload.get("instruction") or "").strip()
    if not command:
        return jsonify({"success": False, "error": "command_required", "message": "A business command is required."}), 400
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        task_id = f"cc-{__import__('uuid').uuid4().hex[:16]}"
        project_snapshot = project_intelligence.snapshot(
            int(organization_id), getattr(current_user, "id", 0), project_id="kemet-ai"
        )
        plan = task_planner.plan(command, organization_id=int(organization_id), task_id=task_id)
        supplied_artifacts = payload.get("artifacts")
        artifact_preview = None
        if supplied_artifacts is not None:
            from app.core.execution.artifact_execution import artifact_execution
            artifact_preview = artifact_execution.preview(supplied_artifacts)
            plan = task_planner.bind_artifact_write(
                plan, artifacts=supplied_artifacts, preview_digest=artifact_preview["digest"]
            )
        youtube_manifest = str(payload.get("youtube_manifest") or "").strip()
        if youtube_manifest:
            plan = task_planner.bind_youtube_publish(plan, manifest=youtube_manifest)
        verified_rows = ConnectionLifecycleService.list_for_user(
            int(organization_id), getattr(current_user, "id", None)
        )
        verified = {row.provider_id for row in verified_rows if row.status == "verified"}
        routing = federation_routing_preview.preview(
            command, organization_id=int(organization_id), verified_provider_ids=verified
        )
        if routing.specialist and routing.specialist.get("provider_id") == "manus":
            plan = task_planner.bind_specialist(plan, provider_id="manus", action="manus.task.create")
        elif (
            routing.provider
            and plan.task_type in {"coding", "automation", "multimodal", "multi_task"}
            and not any(step.action == "termux_engineering" for step in plan.steps)
        ):
            plan = task_planner.bind_federated_execution(
                plan,
                provider_id=routing.provider.get("provider_id"),
                model_id=routing.provider.get("model_id"),
            )
        data_entitlement = DataEntitlement(
            provider_id="internal",
            dataset="business_context",
            organization_id=int(organization_id),
            allowed_operations=("read",),
            model_use_allowed=True,
            export_allowed=False,
            training_allowed=False,
            citation_required=True,
        )
        data_policy = {
            "version": data_boundary.VERSION,
            "provider_id": data_entitlement.provider_id,
            "dataset": data_entitlement.dataset,
            "operation": "read",
            "entitlement_fingerprint": data_entitlement.fingerprint(),
            "raw_data_exposed": False,
        }
        context = PlanContext(
            organization_id=int(organization_id),
            user_id=getattr(current_user, "id", None),
            metadata={
                "surface": "unified_command_center",
                "routing": routing.as_dict(),
                "data_policy": data_policy,
                "project_intelligence": {
                    "version": project_snapshot.version,
                    "context_hash": project_snapshot.context_hash,
                },
            },
        )
        binding = bind_plan_context(plan, context)
        assessment = assess_plan_risk(plan)
        capability_context = capability_federation.snapshot(configured_only=False)
        context.metadata["capability_federation"] = {
            "version": capability_context["version"],
            "fingerprint": capability_context["fingerprint"],
        }
        evidence_context = execution_evidence_fabric.context_package(
            task_id=task_id,
            organization_id=int(organization_id),
            policy=data_policy,
            routing=routing.as_dict(),
            project_context_hash=project_snapshot.context_hash,
        )
        evidence_context["capability_federation"] = {
            "version": capability_context["version"],
            "fingerprint": capability_context["fingerprint"],
        }
        if artifact_preview:
            evidence_context["artifact_preview"] = {
                "digest": artifact_preview["digest"],
                "files": artifact_preview["files"],
            }
        package = build_approval_package(
            plan, binding, assessment,
            evidence_context_hash=evidence_context["digest"],
        )
        outcome_contract = outcome_control.contract(
            decision={
                "decision_id": f"decision-{task_id}-{package.package_hash[:12]}",
                "task_id": task_id,
                "organization_id": int(organization_id),
                "digest": package.package_hash,
            },
            expected_metrics=[],
        )
        compiled = task_planner.compile(plan)
        first = plan.steps[0] if plan.steps else None
        selected_visual = payload.get("visual_direction")
        production_state = None
        if selected_visual:
            selected_id = str(selected_visual.get("id") or "").strip() if isinstance(selected_visual, dict) else ""
            allowed = {item["id"] for item in visual_direction_service.suggest(command, plan.task_type)}
            if selected_id not in allowed:
                return jsonify({"success": False, "error": "invalid_visual_direction", "executed": False}), 400
            direction = dict(visual_direction_service.CATALOG[selected_id])
            direction.update({"id": selected_id, "selected_by": "human", "selection_stage": "planning"})
            production_state = cinematic_production_os.build_state(
                organization_id=int(organization_id),
                project_id="kemet-ai",
                stage="intent_visual_direction",
                intent={"task_type": plan.task_type, "command": command},
                visual_direction=direction,
                canonical_refs={"planning_task_id": plan.task_id, "plan_hash": package.plan_hash},
            )
        capability_by_task = {
            "coding": "coding",
            "research": "research",
            "multimodal": "image_generation",
            "automation": "analytics",
            "multi_task": "research",
        }
        tool_recommendations = tool_intelligence_registry.recommend(
            capability_by_task.get(plan.task_type, "text_generation"),
            organization_id=int(organization_id),
        )
        expected = {
            "coding": "A bounded implementation plan ready for review.",
            "research": "A structured analysis and comparison of the requested subject.",
            "automation": "A governed automation prepared for explicit human approval.",
            "multimodal": "A structured analysis of the supplied media task.",
            "multi_task": "A sequenced plan covering the requested objectives.",
        }.get(plan.task_type, "A governed business analysis and next-step plan.")
        planning_projection = None
        if production_state:
            planning_projection = cinematic_production_os.compile_planning_projection(
                state=production_state,
                scenes=[], shots=[], assets=[], constraints=[],
            )
        return jsonify({
            "success": True,
            "version": "2.1",
            "task_id": plan.task_id,
            "intent": plan.task_type,
            "action": first.action if first else "business_insights",
            "confidence": plan.confidence,
            "risk": assessment.level,
            "risk_score": assessment.score,
            "requires_approval": bool(assessment.approval_required or plan.requires_approval),
            "expected_result": expected,
            "approval_reason": "Human approval is required before any high-impact or external operation." if (assessment.approval_required or plan.requires_approval) else "Read-only planning; no business action is executed.",
            "task_plan": plan.as_dict(),
            "risk_assessment": assessment.as_dict(),
            "approval_package": package.as_dict(),
            "evidence_context": evidence_context,
            "outcome_contract": outcome_contract,
            "artifact_preview": artifact_preview,
            "context": binding,
            "routing": routing.as_dict(),
            "tool_intelligence": tool_recommendations,
            "automation_plan": compiled["automation_plan"],
            "production_state": production_state,
            "visual_direction": production_state.get("visual_direction") if production_state else None,
            "planning_projection": planning_projection,
            "production_graph": planning_projection.get("graph") if planning_projection else None,
            "production_specification": planning_projection.get("specification") if planning_projection else None,
            "executed": False,
            "database_mutation": False,
            "external_call": False,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({
            "success": False,
            "error": "planning_unavailable",
            "message": "Kemet could not safely build this plan. No action was executed.",
            "executed": False,
        }), 500


@command_center_bp.route("/api/bos/decide-plan", methods=["POST"])
@command_center_bp.route("/api/bos/execute-approved", methods=["POST"])
@login_required
def bos_execute_approved():
    """Execute an approved command through the governed canonical or specialist runtime."""
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required", "executed": False}), 400
    if getattr(current_user, "role", None) != "admin":
        return jsonify({"success": False, "error": "admin_approval_required", "executed": False}), 403
    payload = request.get_json(silent=True) or {}
    command = str(payload.get("command") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    package_hash = str(payload.get("approval_package_hash") or "").strip()
    approved = bool(payload.get("approved", False))
    reason = str(payload.get("reason") or "").strip()
    if not command or not task_id or not package_hash:
        return jsonify({"success": False, "error": "approval_binding_required", "executed": False}), 400
    try:
        project_snapshot = project_intelligence.snapshot(
            int(organization_id), getattr(current_user, "id", 0), project_id="kemet-ai"
        )
        plan = task_planner.plan(command, organization_id=int(organization_id), task_id=task_id)
        supplied_artifacts = payload.get("artifacts")
        artifact_preview = None
        if supplied_artifacts is not None:
            from app.core.execution.artifact_execution import artifact_execution
            artifact_preview = artifact_execution.preview(supplied_artifacts)
            plan = task_planner.bind_artifact_write(
                plan, artifacts=supplied_artifacts, preview_digest=artifact_preview["digest"]
            )
        youtube_manifest = str(payload.get("youtube_manifest") or "").strip()
        if youtube_manifest:
            plan = task_planner.bind_youtube_publish(plan, manifest=youtube_manifest)
        verified_rows = ConnectionLifecycleService.list_for_user(
            int(organization_id), getattr(current_user, "id", None)
        )
        verified = {row.provider_id for row in verified_rows if row.status == "verified"}
        routing = federation_routing_preview.preview(
            command, organization_id=int(organization_id), verified_provider_ids=verified
        )
        if routing.specialist and routing.specialist.get("provider_id") == "manus":
            plan = task_planner.bind_specialist(plan, provider_id="manus", action="manus.task.create")
        elif (
            routing.provider
            and plan.task_type in {"coding", "automation", "multimodal", "multi_task"}
            and not any(step.action == "termux_engineering" for step in plan.steps)
        ):
            plan = task_planner.bind_federated_execution(
                plan,
                provider_id=routing.provider.get("provider_id"),
                model_id=routing.provider.get("model_id"),
            )
        data_entitlement = DataEntitlement(
            provider_id="internal",
            dataset="business_context",
            organization_id=int(organization_id),
            allowed_operations=("read",),
            model_use_allowed=True,
            export_allowed=False,
            training_allowed=False,
            citation_required=True,
        )
        data_policy = {
            "version": data_boundary.VERSION,
            "provider_id": data_entitlement.provider_id,
            "dataset": data_entitlement.dataset,
            "operation": "read",
            "entitlement_fingerprint": data_entitlement.fingerprint(),
            "raw_data_exposed": False,
        }
        context = PlanContext(
            organization_id=int(organization_id),
            user_id=getattr(current_user, "id", None),
            metadata={
                "surface": "unified_command_center",
                "routing": routing.as_dict(),
                "data_policy": data_policy,
                "project_intelligence": {
                    "version": project_snapshot.version,
                    "context_hash": project_snapshot.context_hash,
                },
            },
        )
        binding = bind_plan_context(plan, context)
        assessment = assess_plan_risk(plan)
        capability_context = capability_federation.snapshot(configured_only=False)
        context.metadata["capability_federation"] = {
            "version": capability_context["version"],
            "fingerprint": capability_context["fingerprint"],
        }
        evidence_context = execution_evidence_fabric.context_package(
            task_id=task_id,
            organization_id=int(organization_id),
            policy=data_policy,
            routing=routing.as_dict(),
            project_context_hash=project_snapshot.context_hash,
        )
        evidence_context["capability_federation"] = {
            "version": capability_context["version"],
            "fingerprint": capability_context["fingerprint"],
        }
        if artifact_preview:
            evidence_context["artifact_preview"] = {
                "digest": artifact_preview["digest"],
                "files": artifact_preview["files"],
            }
        package = build_approval_package(
            plan, binding, assessment,
            evidence_context_hash=evidence_context["digest"],
        )
        outcome_contract = outcome_control.contract(
            decision={
                "decision_id": f"decision-{task_id}-{package.package_hash[:12]}",
                "task_id": task_id,
                "organization_id": int(organization_id),
                "digest": package.package_hash,
            },
            expected_metrics=[],
        )
        if package.package_hash != package_hash:
            return jsonify({"success": False, "error": "approval_package_mismatch", "executed": False}), 409
        if not (assessment.approval_required or plan.requires_approval):
            return jsonify({"success": False, "error": "approval_not_required", "executed": False}), 409
        first = next((step for step in reversed(plan.steps) if step.requires_approval), None)
        if first is None:
            return jsonify({"success": False, "error": "execution_plan_empty", "executed": False}), 422
        approval = AutomationApproval(
            organization_id=int(organization_id),
            action_type=first.action if plan.steps else "business_insights",
            status="pending",
            reason=reason or "Human approval requested from Unified Command Center.",
            request_json=json.dumps({
                "command": command,
                "task_id": task_id,
                "action": first.action if plan.steps else "business_insights",
                "approval_package_hash": package.package_hash,
                "plan_hash": package.plan_hash,
                "routing": routing.as_dict(),
                "parameters": {"organization_id": int(organization_id)},
                "data": {"command": command, "task_id": task_id},
            }, ensure_ascii=False, default=str),
            requested_by=getattr(current_user, "id", None),
        )
        db.session.add(approval)
        db.session.commit()

        decision = decide_approval(
            package,
            int(current_user.id),
            approved,
            reason if not approved else "Approved from Unified Command Center.",
        )
        approval.decided_by = int(current_user.id)
        approval.decided_at = datetime.utcnow()
        approval.status = "approved" if approved else "rejected"
        approval.decision_json = json.dumps(
            {"decision": decision.as_dict(), "approval_package": package.as_dict()},
            ensure_ascii=False,
            default=str,
        )
        db.session.commit()
        if not approved:
            return jsonify({
                "success": True,
                "status": "rejected",
                "executed": False,
                "task_id": task_id,
                "approval_id": approval.id,
                "approval": decision.as_dict(),
                "evidence": {
                    "approval_decision": decision.decision_hash,
                    "execution": False,
                },
            }), 200
        handoff = create_gate_handoff(
            package,
            decision,
            action=first.action,
            execution_key=task_id,
        )
        if not verify_gate_handoff(
            handoff,
            organization_id=int(organization_id),
            plan_hash=package.plan_hash,
            action=first.action,
            execution_key=task_id,
        ):
            return jsonify({"success": False, "error": "central_gate_handoff_failed", "executed": False}), 403
        runtime_plan = {
            "request": "unified_command_center",
            "organization_id": int(organization_id),
            "user_id": getattr(current_user, "id", None),
            "action": first.action,
            "parameters": {
                "organization_id": int(organization_id),
                "prompt": command,
                "provider_id": routing.provider.get("provider_id") if routing.provider else None,
                "model_id": routing.provider.get("model_id") if routing.provider else None,
                "required_capabilities": list(routing.capabilities),
                "artifacts": supplied_artifacts if supplied_artifacts is not None else [],
                "preview_digest": artifact_preview["digest"] if artifact_preview else "",
                "manifest": youtube_manifest,
            },
            "data": {"command": command, "task_id": task_id},
            "plan_id": task_id,
            "approval_package_hash": package.package_hash,
            "approval_decision_hash": decision.decision_hash,
            "central_gate_handoff_hash": handoff.handoff_hash,
            "federation_routing": routing.as_dict(),
            "approved": True,
            "approver_id": int(current_user.id),
            "executed": False,
            "external_execution": False,
            "database_mutation": False,
            "provider_id": (
                routing.specialist.get("provider_id") if routing.specialist
                else (routing.provider.get("provider_id") if routing.provider else "kemet")
            ),
            "execution_key": task_id,
            "evidence_context_hash": evidence_context["digest"],
            "outcome_contract_digest": outcome_contract["digest"],
            "project_context_hash": project_snapshot.context_hash,
            "artifact_preview_digest": artifact_preview["digest"] if artifact_preview else "",
        }
        authorization = execution_authorization.create_authorization(runtime_plan, int(current_user.id))
        runtime_plan["plan_id"] = authorization["plan_id"]
        provider_id = (
            routing.specialist.get("provider_id") if routing.specialist
            else (routing.provider.get("provider_id") if routing.provider else "kemet")
        )
        envelope = execution_envelope.build(
            approval_package_hash=package.package_hash,
            decision_hash=decision.decision_hash,
            handoff_hash=handoff.handoff_hash,
            authorization=authorization,
            execution_key=task_id,
            provider_id=provider_id,
            action=first.action,
            evidence_context_hash=evidence_context["digest"],
            outcome_contract_digest=outcome_contract["digest"],
            artifact_preview_digest=artifact_preview["digest"] if artifact_preview else "",
        )
        if not execution_envelope.verify(
            envelope, authorization=authorization, execution_key=task_id,
            provider_id=provider_id, action=first.action,
            evidence_context_hash=evidence_context["digest"],
            outcome_contract_digest=outcome_contract["digest"],
            artifact_preview_digest=artifact_preview["digest"] if artifact_preview else None,
        ):
            return jsonify({"success": False, "error": "execution_envelope_failed", "executed": False}), 403
        runtime_plan["execution_envelope"] = envelope
        if routing.specialist and routing.specialist.get("provider_id") == "manus" and first.action == "manus.task.create":
            specialist_result = specialist_orchestrator.execute(
                prompt=command, plan=runtime_plan, authorization=authorization,
                organization_id=int(organization_id), user_id=int(current_user.id),
                task_id=task_id, verified_provider_ids=verified,
                preferred_provider="manus", capabilities=tuple(routing.capabilities),
                metadata={"trace_id": task_id, "correlation_id": task_id},
                execution_envelope_payload=envelope,
            )
            return jsonify({
                "success": specialist_result.success,
                "status": specialist_result.status,
                "federation": routing.as_dict(),
                "central_gate_handoff": handoff.as_dict(),
                "executed": specialist_result.executed,
                "external_execution": True,
                "task_id": task_id,
                "approval_id": approval.id,
                "approval": decision.as_dict(),
                "specialist": specialist_result.as_dict(),
                "authorization": {"plan_id": authorization.get("plan_id"), "plan_hash": authorization.get("plan_hash"), "approver_id": authorization.get("approver_id"), "expires_at": authorization.get("expires_at")},
                "execution_envelope": envelope,
            }), 200 if specialist_result.success else 422
        result = canonical_execution_runtime.execute(
            plan=runtime_plan,
            authorization=authorization,
            action_registry=governed_execution_service._registry(),
            user_id=getattr(current_user, "id", None),
            execution_envelope_payload=envelope,
        )
        evidence = execution_evidence_fabric.execution_record(
            action=first.action,
            plan_hash=authorization.get("plan_hash"),
            risk=assessment.as_dict(),
            result=result,
        )
        return jsonify({
            "success": bool(result.get("success")),
            "status": result.get("status"),
            "federation": routing.as_dict(),
            "central_gate_handoff": handoff.as_dict(),
            "executed": bool(result.get("executed")),
            "task_id": task_id,
            "approval_id": approval.id,
            "approval": decision.as_dict(),
            "authorization": {
                "plan_id": authorization.get("plan_id"),
                "plan_hash": authorization.get("plan_hash"),
                "approver_id": authorization.get("approver_id"),
                "expires_at": authorization.get("expires_at"),
            },
            "result": result,
            "evidence": evidence,
            "execution_envelope": envelope,
        }), 200 if result.get("success") else 422
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({
            "success": False,
            "error": "approved_execution_unavailable",
            "message": "Kemet stopped before unsafe execution.",
            "executed": False,
        }), 500


@command_center_bp.route("/api/agent-policy/<int:action_id>")
@login_required
def agent_policy(action_id):
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": False,
            "error": "organization_required",
        }), 400

    try:
        action = (
            AutomationAction.query
            .join(AutomationWorkflow)
            .filter(
                AutomationAction.id == action_id,
                AutomationWorkflow.organization_id == organization_id,
            )
            .first()
        )

        if action is None:
            return jsonify({
                "success": False,
                "error": "action_not_found",
            }), 404

        approval_required = getattr(
            action,
            "requires_approval",
            False,
        )

        enabled = getattr(
            action,
            "enabled",
            True,
        )

        policy = {
            "action_id": action.id,
            "action_type": getattr(
                action,
                "action_type",
                None,
            ),
            "enabled": enabled,
            "approval_required": approval_required,
            "execution_mode": (
                "approval_required"
                if approval_required
                else "authorized_execution"
            ),
            "governance": {
                "organization_scoped": True,
                "authorization_required": True,
                "canonical_runtime": True,
            },
        }

        return jsonify({
            "success": True,
            "data": policy,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_policy_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/agent-capabilities")
@login_required
def agent_capabilities():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        capabilities = []

        for workflow in workflows:
            for action in getattr(workflow, "actions", []) or []:
                capabilities.append({
                    "workflow_id": workflow.id,
                    "workflow_name": getattr(
                        workflow,
                        "name",
                        None,
                    ),
                    "action_id": getattr(
                        action,
                        "id",
                        None,
                    ),
                    "action_name": getattr(
                        action,
                        "name",
                        None,
                    ),
                    "action_type": getattr(
                        action,
                        "action_type",
                        None,
                    ),
                    "enabled": getattr(
                        action,
                        "enabled",
                        True,
                    ),
                    "approval_required": getattr(
                        action,
                        "requires_approval",
                        False,
                    ),
                })

        return jsonify({
            "success": True,
            "data": capabilities,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_capabilities_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/agents")
@login_required
def agents():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        workflows = (
            AutomationWorkflow.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        data = []

        for workflow in workflows:
            actions = []

            try:
                for action in getattr(workflow, "actions", []) or []:
                    actions.append({
                        "id": getattr(action, "id", None),
                        "name": getattr(action, "name", None),
                        "action_type": getattr(action, "action_type", None),
                    })
            except Exception:
                actions = []

            data.append({
                "id": workflow.id,
                "name": getattr(workflow, "name", None),
                "description": getattr(workflow, "description", None),
                "status": getattr(workflow, "status", None),
                "enabled": getattr(workflow, "enabled", True),
                "actions": actions,
            })

        return jsonify({
            "success": True,
            "data": data,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "agent_registry_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/approvals")
@login_required
def approvals():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": [],
        })

    try:
        rows = (
            AutomationApproval.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationApproval.id.desc())
            .limit(50)
            .all()
        )

        data = []

        for row in rows:
            request_data = {}
            if getattr(row, "request_json", None):
                try:
                    import json
                    request_data = json.loads(row.request_json)
                except Exception:
                    request_data = {}

            data.append({
                "id": row.id,
                "status": getattr(row, "status", None),
                "action": getattr(row, "action_type", None),
                "reason": getattr(row, "reason", None),
                "workflow_id": getattr(row, "workflow_id", None),
                "execution_id": getattr(row, "execution_id", None),
                "requested_by": getattr(row, "requested_by", None),
                "sla": approval_state(
                    row.created_at,
                    row.action_type,
                    row.reason or "",
                ),
                "parameters": request_data.get("parameters") or {},
                "data": request_data.get("data") or {},
                "created_at": (
                    row.created_at.isoformat()
                    if getattr(row, "created_at", None)
                    else None
                ),
                "updated_at": (
                    row.updated_at.isoformat()
                    if getattr(row, "updated_at", None)
                    else None
                ),
            })

        return jsonify({
            "success": True,
            "data": data,
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "approval_data_unavailable",
            "message": str(exc),
        }), 500

@command_center_bp.route("/api/governance")
@login_required
def governance():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": {
                "organization_id": None,
                "policies": [],
                "approvals": [],
                "executions": [],
                "audit": [],
            },
        })

    try:
        actions = (
            AutomationAction.query
            .join(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == organization_id,
            )
            .order_by(AutomationAction.id.asc())
            .limit(50)
            .all()
        )

        approvals = (
            AutomationApproval.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationApproval.id.desc())
            .limit(20)
            .all()
        )

        executions = (
            AutomationExecution.query
            .join(AutomationWorkflow)
            .filter(
                AutomationWorkflow.organization_id == organization_id,
            )
            .order_by(AutomationExecution.id.desc())
            .limit(20)
            .all()
        )

        audit = (
            AuditRecord.query
            .filter_by(organization_id=organization_id)
            .order_by(AuditRecord.id.desc())
            .limit(30)
            .all()
        )

        return jsonify({
            "success": True,
            "data": {
                "organization_id": organization_id,
                "policies": [
                    {
                        "action_id": action.id,
                        "action_type": getattr(
                            action, "action_type", None
                        ),
                        "enabled": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            ) != "blocked"
                        ),
                        "approval_required": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            ) == "approval_required"
                        ),
                        "execution_mode": (
                            governed_execution_service._policy(
                                getattr(action, "action_type", "")
                            )
                        ),
                    }
                    for action in actions
                ],
                "approvals": [
                    {
                        "id": row.id,
                        "action": getattr(
                            row, "action_type", None
                        ),
                        "status": getattr(row, "status", None),
                        "created_at": (
                            row.created_at.isoformat()
                            if getattr(row, "created_at", None)
                            else None
                        ),
                    }
                    for row in approvals
                ],
                "executions": [
                    {
                        "id": row.id,
                        "workflow_id": getattr(
                            row, "workflow_id", None
                        ),
                        "status": getattr(row, "status", None),
                        "created_at": (
                            row.created_at.isoformat()
                            if getattr(row, "created_at", None)
                            else None
                        ),
                        "completed_at": (
                            row.completed_at.isoformat()
                            if getattr(row, "completed_at", None)
                            else None
                        ),
                    }
                    for row in executions
                ],
                "audit": [
                    {
                        "id": row.id,
                        "event_type": row.event_type,
                        "action": row.action,
                        "status": row.status,
                        "actor_type": row.actor_type,
                        "created_at": (
                            row.created_at.isoformat()
                            if row.created_at
                            else None
                        ),
                    }
                    for row in audit
                ],
            },
        })

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": "governance_data_unavailable",
            "message": str(exc),
        }), 500




@command_center_bp.route("/api/bos/task-status/<path:execution_key>")
@login_required
def bos_task_status(execution_key):
    """Read-only external task status; refresh never creates a new execution."""
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 403
    refresh = str(request.args.get("refresh", "0")).lower() in {"1", "true", "yes"}
    try:
        task = external_task_control_plane.get(
            organization_id=int(organization_id), execution_key=execution_key, refresh=refresh
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    return jsonify({
        "success": True,
        "task": task,
        "refresh_requested": refresh,
        "governance": {"read_only": True, "external_execution": False},
        "control_plane": {"version": external_task_control_plane.VERSION, "refresh_is_read_only": True},
    }), 200


@command_center_bp.route("/api/overview")
@login_required
def overview():
    organization_id = _organization_id()

    if organization_id is None:
        return jsonify({
            "success": True,
            "data": {
                "active_agents": 0,
                "pending_approvals": 0,
                "automations": 0,
                "tickets": 0,
                "payments": 0,
                "subscriptions": 0,
                "ai_usage": 0,
                "organization_id": None,
            },
        })

    approval_query = AutomationApproval.query.filter_by(
        organization_id=organization_id
    )

    execution_query = AutomationExecution.query.filter_by(
        organization_id=organization_id
    )

    workflow_query = AutomationWorkflow.query.filter_by(
        organization_id=organization_id
    )

    ticket_query = Ticket.query.filter_by(
        organization_id=organization_id
    )

    payment_query = Payment.query.filter_by(
        organization_id=organization_id
    )

    subscription_query = Subscription.query.filter_by(
        organization_id=organization_id
    )

    usage_query = AIUsage.query.filter_by(
        organization_id=organization_id
    )

    pending_approvals = 0

    try:
        pending_approvals = _count(
            approval_query.filter(
                AutomationApproval.status == "waiting_approval"
            )
        )
    except Exception:
        try:
            pending_approvals = _count(
                approval_query.filter(
                    AutomationApproval.status == "pending"
                )
            )
        except Exception:
            pending_approvals = 0

    automations = _count(execution_query)

    try:
        automations = _count(
            execution_query.filter(
                AutomationExecution.status.in_([
                    "completed",
                    "running",
                    "waiting_approval",
                    "failed",
                ])
            )
        )
    except Exception:
        pass

    data = {
        "active_agents": 0,
        "pending_approvals": pending_approvals,
        "automations": automations,
        "tickets": _count(ticket_query),
        "payments": _count(payment_query),
        "subscriptions": _count(subscription_query),
        "ai_usage": _count(usage_query),
        "workflows": _count(workflow_query),
        "organization_id": organization_id,
    }

    return jsonify({
        "success": True,
        "data": data,
    })


@command_center_bp.get("/api/bos/outcome/<path:task_id>")
@login_required
def bos_outcome_status(task_id):
    """Return the immutable outcome contract bound to a command execution key."""
    organization_id = _organization_id()
    if not organization_id or not task_id:
        return jsonify({"success": False, "error": "outcome_identity_required"}), 400
    return jsonify({
        "success": True,
        "task_id": task_id,
        "outcome": {
            "status": "measurement_pending",
            "measurement_policy": "observational_only",
            "human_review_required": True,
            "auto_execute": False,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        },
    }), 200


@command_center_bp.get("/api/bos/social-readiness")
@login_required
def bos_social_readiness():
    """Return tenant-scoped readiness for the unified social distribution layer."""
    from app.services.social_channel_readiness_service import social_channel_readiness_service
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    snapshot = social_channel_readiness_service.snapshot(int(organization_id))
    return jsonify({"success": True, "social_readiness": snapshot})


@command_center_bp.post("/api/bos/production-backlot/job-preview")
@login_required
def bos_production_backlot_job_preview():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    episode_package = payload.get("episode_package")
    voice_contract = payload.get("voice_contract")
    quality_gates = payload.get("quality_gates")
    if not isinstance(episode_package, dict) or not isinstance(voice_contract, dict):
        return jsonify({"success": False, "error": "production_contracts_required", "executed": False}), 400
    if not isinstance(quality_gates, list) or not quality_gates:
        return jsonify({"success": False, "error": "quality_gates_required", "executed": False}), 400
    try:
        from app.services.mendes.mendes_production_job_store import mendes_production_job_store
        from app.services.production_backlot_service import production_backlot_service
        job = mendes_production_job_store.create(
            int(organization_id),
            episode_package,
            voice_contract,
            quality_gates,
            approval_state=str(payload.get("approval_state") or "pending"),
            asset_refs=payload.get("asset_refs"),
            evidence_refs=payload.get("evidence_refs"),
            idempotency_key=payload.get("idempotency_key"),
        )
        snapshot = production_backlot_service.snapshot(
            int(organization_id),
            title=str(payload.get("title") or "Hikayat Mendes"),
            job=job,
        )
        return jsonify({"success": True, "executed": False, "production_job": job, "production_backlot": snapshot})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({"success": False, "error": "production_job_preview_unavailable", "executed": False}), 500


@command_center_bp.get("/api/bos/mendes-governed-pilot")
@login_required
def bos_mendes_governed_pilot():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        result = mendes_governed_pilot_service.assemble(int(organization_id))
        return jsonify(result), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "mendes_governed_pilot_unavailable"}), 503


@command_center_bp.post("/api/bos/mendes-controlled-production/execute")
@login_required
def bos_mendes_controlled_production_execute():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    approval = payload.get("approval") is True
    try:
        from app.services.mendes.mendes_controlled_production_service import mendes_controlled_production_service
        result = mendes_controlled_production_service.execute(int(organization_id), approval)
        return jsonify(result), 200 if result.get("success") else 422
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "external_execution": False}), 422
    except Exception:
        return jsonify({"success": False, "error": "mendes_controlled_production_unavailable", "external_execution": False}), 503


@command_center_bp.get("/api/bos/content-final-approval")
@login_required
def bos_content_final_approval():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.final_content_approval_service import final_content_approval_service
        result = final_content_approval_service.build(organization_id=int(organization_id))
        return jsonify(result), 200 if result.get("success") else 422
    except Exception:
        current_app.logger.exception("content_final_approval_unavailable")
        return jsonify({"success": False, "error": "content_final_approval_unavailable", "execution_authority": False}), 503


@command_center_bp.get("/api/bos/content-approval-status")
@login_required
def bos_content_approval_status():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.models.mendes_production_job import MendesProductionJobRecord
        record = (MendesProductionJobRecord.query
                  .filter_by(organization_id=int(organization_id), state="VERIFIED")
                  .order_by(MendesProductionJobRecord.id.desc()).first())
        if not record:
            return jsonify({"success": True, "status": "not_ready", "approval_packet": None, "execution_authority": False}), 200
        return jsonify({"success": True, "status": "review_required", "approval_packet": {
            "status": "PENDING_HUMAN_APPROVAL",
            "artifact_digest": next((x.get("sha256") for x in __import__("json").loads(record.asset_refs_json) if x.get("sha256")), None),
            "episode_package_digest": record.episode_package_digest,
            "job_id": record.job_id,
            "publication_requested": False,
            "external_publication": False,
            "execution_authority": False,
            "human_approval_required": True,
            "truth_boundary": "status_only; full packet is not reconstructed or auto-approved"
        }}) , 200
    except Exception:
        current_app.logger.exception("content_approval_status_unavailable")
        return jsonify({"success": False, "error": "content_approval_status_unavailable", "execution_authority": False}), 503


@command_center_bp.get("/api/bos/mendes-episode-readiness/<job_id>")
@login_required
def bos_mendes_episode_readiness(job_id):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        job = mendes_production_job_store.get(int(organization_id), job_id)
        pilot = mendes_pilot_episode_service.build(int(organization_id))["package"]
        readiness = mendes_episode_readiness_service.build(
            organization_id=int(organization_id), job=job, package=pilot
        )
        return jsonify({"success": True, "episode_readiness": readiness})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 422
    except Exception:
        return jsonify({"success": False, "error": "mendes_episode_readiness_unavailable"}), 503


@command_center_bp.get("/api/bos/production-job/<job_id>")
@login_required
def bos_production_job_get(job_id):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        from app.services.mendes.mendes_production_job_store import mendes_production_job_store
        job = mendes_production_job_store.get(int(organization_id), job_id)
        return jsonify({"success": True, "production_job": job}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404


@command_center_bp.post("/api/bos/production-job/<job_id>/transition")
@login_required
def bos_production_job_transition(job_id):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        from app.services.mendes.mendes_production_job_store import mendes_production_job_store
        job = mendes_production_job_store.transition(
            int(organization_id), job_id, str(payload.get("target_state") or ""),
            approval=payload.get("approval"), evidence=payload.get("evidence"),
        )
        return jsonify({"success": True, "executed": False, "production_job": job}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400


@command_center_bp.get("/api/bos/production-backlot")
@login_required
def bos_production_backlot():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.production_backlot_service import production_backlot_service
    title = request.args.get("title") or "Hikayat Mendes"
    try:
        job = None
        job_id = str(request.args.get("job_id") or "").strip()
        if job_id:
            from app.services.mendes.mendes_production_job_store import mendes_production_job_store
            job = mendes_production_job_store.get(int(organization_id), job_id)
        snapshot = production_backlot_service.snapshot(int(organization_id), title=title, job=job)
        return jsonify({"success": True, "production_backlot": snapshot})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:
        return jsonify({"success": False, "error": "production_backlot_unavailable"}), 500


@command_center_bp.get("/api/bos/growth-automation")
@login_required
def bos_growth_automation():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.growth_automation_service import growth_automation_service
    return jsonify({"success": True, "growth_automation": growth_automation_service.catalog(int(organization_id))}), 200


@command_center_bp.post("/api/bos/growth-automation/plan")
@login_required
def bos_growth_automation_plan():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    from app.services.growth_automation_service import growth_automation_service
    result = growth_automation_service.plan(
        int(organization_id),
        str(payload.get("playbook_id") or ""),
        target=payload.get("target"),
        evidence=payload.get("evidence"),
    )
    return jsonify(result), 200 if result.get("success") else 400


@command_center_bp.post("/api/bos/content-factory/plan")
@login_required
def bos_content_factory_plan():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        package = content_factory_service.build(
            organization_id=int(organization_id),
            title=str(payload.get("title") or ""),
            premise=str(payload.get("premise") or ""),
            audience=str(payload.get("audience") or "Arabic-speaking audience"),
            content_type=str(payload.get("content_type") or "story"),
            language=str(payload.get("language") or "ar-EG"),
            dialect=str(payload.get("dialect") or "eg"),
            production_profile=str(payload.get("production_profile") or payload.get("content_type") or "story"),
            platforms=payload.get("platforms"),
            duration_seconds=int(payload.get("duration_seconds") or 90),
            source_ids=payload.get("source_ids"),
            rights_status=str(payload.get("rights_status") or "original"),
            era_label=payload.get("era_label"),
            era_type=str(payload.get("era_type") or "inspired"),
            season_number=payload.get("season_number"),
            episode_number=payload.get("episode_number"),
            characters=payload.get("characters"),
            beats=payload.get("beats"),
            emotional_goal=str(payload.get("emotional_goal") or ""),
            cliffhanger=str(payload.get("cliffhanger") or ""),
        )
        return jsonify({"success": True, "content_package": package, "executed": False}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({"success": False, "error": "content_factory_unavailable", "executed": False}), 500


@command_center_bp.post("/api/bos/content-studio/approve")
@login_required
def bos_content_studio_approve():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        from app.services.content_social_governance_service import content_social_governance_service
        asset = content_social_governance_service.build_asset(
            organization_id=int(organization_id),
            content_id=str(payload.get("content_id") or ""),
            version=int(payload.get("version") or 0),
            content_type=str(payload.get("content_type") or "educational"),
            language=str(payload.get("language") or "ar-EG"),
            payload=payload.get("payload") or {},
            lifecycle_state="APPROVED",
        )
        approval = content_social_governance_service.create_approval(
            asset=asset, approver_id=str(getattr(current_user, "id", ""))
        )
        return jsonify({
            "success": True,
            "asset": asset,
            "approval": approval,
            "executed": False,
            "database_mutation": False,
            "external_execution": False,
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({"success": False, "error": "content_approval_unavailable", "executed": False}), 500


@command_center_bp.post("/api/bos/content-studio/publishing-intent")
@login_required
def bos_content_studio_publishing_intent():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    asset = payload.get("asset") or {}
    approval = payload.get("approval") or {}
    try:
        from app.services.content_social_governance_service import content_social_governance_service
        binding = content_social_governance_service.validate_approval_for_publish(asset=asset, approval=approval)
        if int(asset.get("organization_id") or 0) != int(organization_id):
            return jsonify({"success": False, "error": "tenant_mismatch", "binding": binding}), 409
        if not binding.get("valid"):
            return jsonify({"success": False, "error": "approval_binding_invalid", "binding": binding}), 409
        account_ref = str(payload.get("account_ref") or "").strip()
        if not account_ref or account_ref.endswith("-account"):
            return jsonify({
                "success": False,
                "error": "verified_target_account_required",
                "message": "A verified tenant-scoped social account reference is required before a publishing intent can be created.",
                "binding": binding,
                "executed": False,
            }), 409
        intent = content_social_governance_service.create_publishing_intent(
            asset=asset,
            platform=str(payload.get("platform") or ""),
            account_ref=account_ref,
            idempotency_key=str(payload.get("idempotency_key") or ""),
        )
        return jsonify({
            "success": True,
            "publishing_intent": intent,
            "binding": binding,
            "executed": False,
            "database_mutation": False,
            "external_execution": False,
            "next_step": "canonical_execution_requires_explicit_approval_and_verified_provider",
        }), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({"success": False, "error": "publishing_intent_unavailable", "executed": False}), 500


@command_center_bp.get("/api/bos/production-studio")
@login_required
def bos_production_studio():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.production_studio_service import production_studio_service
    return jsonify({
        "success": True,
        "production_studio": {
            "version": production_studio_service.VERSION,
            "stages": [stage.stage for stage in production_studio_service.STAGES],
            "governance": {"read_only": True, "human_approval_required": True, "canonical_runtime_only": True},
        },
    })


@command_center_bp.post("/api/bos/production-studio/plan")
@login_required
def bos_production_studio_plan():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        from app.services.production_studio_service import production_studio_service
        plan = production_studio_service.plan(
            organization_id=int(organization_id),
            title=str(payload.get("title") or ""),
            language=str(payload.get("language") or "ar-EG"),
            duration_seconds=int(payload.get("duration_seconds") or 90),
            platforms=payload.get("platforms"),
            reference_uri=payload.get("reference_uri"),
        )
        return jsonify({"success": True, "production_plan": plan, "executed": False}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({"success": False, "error": "production_planning_unavailable", "executed": False}), 500


@command_center_bp.get("/api/bos/social-connections")
@login_required
def bos_social_connections():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_connection_hub import social_connection_hub
    return jsonify(social_connection_hub.snapshot(int(organization_id), int(current_user.id)))


@command_center_bp.get("/api/bos/social-connections/<channel>/authorize")
@login_required
def bos_social_connection_authorize_get(channel):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_connection_hub import social_connection_hub
    result = social_connection_hub.authorize(int(organization_id), int(current_user.id), channel)
    if result.get("status") == "authorization_ready" and result.get("authorization_url"):
        return redirect(result["authorization_url"], code=302)
    return jsonify(result), 400


@command_center_bp.post("/api/bos/social-connections/<channel>/authorize")
@login_required
def bos_social_connection_authorize(channel):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_connection_hub import social_connection_hub
    result = social_connection_hub.authorize(int(organization_id), int(current_user.id), channel)
    return jsonify(result), 200 if result.get("status") == "authorization_ready" else 400


@command_center_bp.get("/api/bos/social-connections/<channel>/callback")
@login_required
def bos_social_connection_callback(channel):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    code = request.args.get("code", "").strip()
    state = request.args.get("state", "").strip()
    if not code or not state:
        return jsonify({"success": False, "error": "oauth_callback_invalid", "verified": False}), 400
    from app.services.social_connection_service import social_connection_service
    try:
        result = social_connection_service.callback(int(organization_id), int(current_user.id), channel, code, state)
        return jsonify({"success": True, "connection": result}), 200
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"success": False, "error": str(exc), "verified": False}), 400
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "error": "oauth_callback_failed", "verified": False}), 503


@command_center_bp.get("/api/bos/social-distribution")
@login_required
def bos_social_distribution():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_distribution_hub import social_distribution_hub
    return jsonify({"success": True, "social_distribution": social_distribution_hub.snapshot(int(organization_id))})


@command_center_bp.post("/api/bos/social-distribution/plan")
@login_required
def bos_social_distribution_plan():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    payload = request.get_json(silent=True) or {}
    try:
        from app.services.social_distribution_hub import social_distribution_hub
        plan = social_distribution_hub.plan(
            int(organization_id),
            asset_uri=str(payload.get("asset_uri") or "").strip(),
            title=payload.get("title"),
            caption=payload.get("caption"),
            platforms=payload.get("platforms"),
        )
        return jsonify({"success": True, "distribution_plan": plan, "executed": False}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400
    except Exception:
        return jsonify({
            "success": False,
            "error": "social_distribution_planning_unavailable",
            "executed": False,
        }), 500


@command_center_bp.get("/api/bos/social-channel-catalog")
@login_required
def bos_social_channel_catalog():
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.social_channel_catalog import social_channel_catalog
    return jsonify({"success": True, "social_channel_catalog": social_channel_catalog.snapshot(int(organization_id))})


@command_center_bp.get("/api/approvals/<int:approval_id>/review")
@login_required
def approval_review(approval_id):
    organization_id = _organization_id()
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    approval = (
        AutomationApproval.query
        .filter_by(id=int(approval_id), organization_id=int(organization_id))
        .first()
    )
    if approval is None:
        return jsonify({"success": False, "error": "approval_not_found"}), 404
    request_data = {}
    decision_data = {}
    try:
        request_data = json.loads(approval.request_json or "{}")
    except (TypeError, ValueError):
        request_data = {}
    try:
        decision_data = json.loads(approval.decision_json or "{}")
    except (TypeError, ValueError):
        decision_data = {}
    package = decision_data.get("approval_package") or {}
    if not package and isinstance(decision_data.get("decision"), dict):
        package = decision_data["decision"].get("approval_package") or {}
    authorization = decision_data.get("authorization") or {}
    plan = decision_data.get("plan") or {}
    return jsonify({
        "success": True,
        "review": {
            "approval_id": approval.id,
            "organization_id": int(approval.organization_id),
            "workflow_id": approval.workflow_id,
            "execution_id": approval.execution_id,
            "action": approval.action_type,
            "description": approval.reason,
            "approval_status": approval.status,
            "execution_status": None,
            "risk_level": package.get("risk_level") or "unknown",
            "risk_score": package.get("risk_score"),
            "approval_required": bool(package.get("approval_required", True)),
            "plan_hash": package.get("plan_hash") or plan.get("plan_hash"),
            "decision_hash": (decision_data.get("decision") or {}).get("decision_hash"),
            "execution_key": authorization.get("execution_key") or plan.get("execution_key"),
            "idempotency_key": plan.get("idempotency_key"),
            "evidence_reference": package.get("evidence_context_hash"),
            "expected_outcome": request_data.get("expected_result") or request_data.get("expected_outcome"),
            "authorization_status": "authorized" if authorization.get("authorized") else "not_authorized",
            "requires_human_approval": True,
            "external_side_effects": package.get("external_side_effects"),
            "database_mutation": package.get("database_mutation"),
            "affected_resources": package.get("affected_resources") or [],
            "evidence_requirements": package.get("evidence_requirements") or [],
            "package_hash": package.get("package_hash") or request_data.get("approval_package_hash"),
            "review_only": True,
        },
    }), 200


@command_center_bp.get("/api/bos/google-sheets")
@login_required
def bos_google_sheets_status():
    """Return a tenant-scoped Google Sheets connection status without exposing credentials."""
    organization_id = _organization_id()
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    rows = ConnectionLifecycleService.list_for_user(int(organization_id), int(user_id))
    matches = [row for row in rows if row.provider_id == "google_sheets"]
    return jsonify({
        "success": True,
        "provider": "google",
        "service": "sheets",
        "connection": ConnectionLifecycleService.as_public(matches[0]) if matches else None,
        "credentials_exposed": False,
        "execution_authority": False,
        "canonical_runtime_only": True,
    })


@command_center_bp.post("/api/bos/google-sheets/simulate")
@login_required
def bos_google_sheets_simulate():
    """Build a read-only Google Sheets write simulation; never calls Google."""
    organization_id = _organization_id()
    payload = request.get_json(silent=True) or {}
    if not organization_id:
        return jsonify({"success": False, "error": "organization_required"}), 400
    from app.services.google_sheets_connector_service import google_sheets_connector_service
    try:
        result = google_sheets_connector_service.simulate_write(
            int(organization_id),
            str(payload.get("action") or "google_sheets.write_range"),
            str(payload.get("spreadsheet_id") or ""),
            str(payload.get("range") or ""),
            payload.get("values"),
        )
        return jsonify({"success": True, "simulation": result, "executed": False, "external_call": False}), 200
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc), "executed": False}), 400


@command_center_bp.get("/google-sheets/connect")
@login_required
def google_sheets_connect_browser():
    organization_id = _organization_id(); user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id: return jsonify({"success": False, "error": "organization_required"}), 400
    write = str(request.args.get("mode") or "read").lower() == "write"
    connection = google_sheets_connector_service.authorization_start(int(organization_id), int(user_id), write=write)
    authorization_url = connection.get("authorization_url")
    if not authorization_url: return jsonify({"success": False, "connection": connection}), 503
    return redirect(authorization_url)


@command_center_bp.get("/api/google-sheets/connect")
@login_required
def google_sheets_connect():
    organization_id = _organization_id(); user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id: return jsonify({"success": False, "error": "organization_required"}), 400
    write = str(request.args.get("mode") or "read").lower() == "write"
    return jsonify({"success": True, "connection": google_sheets_connector_service.authorization_start(int(organization_id), int(user_id), write=write)})

@command_center_bp.get("/api/google-sheets/callback")
@login_required
def google_sheets_callback():
    organization_id = _organization_id(); user_id = getattr(current_user, "id", None)
    code = (request.args.get("code") or "").strip(); state = (request.args.get("state") or "").strip()
    if not organization_id or not user_id or not code or not state: return jsonify({"success": False, "error": "oauth_callback_required"}), 400
    try:
        result = google_sheets_connector_service.authorization_callback(int(organization_id), int(user_id), code, state)
        return jsonify({"success": True, "connection": result})
    except ValueError as exc: return jsonify({"success": False, "error": str(exc), "credentials_exposed": False}), 400
    except Exception: return jsonify({"success": False, "error": "google_oauth_callback_failed", "credentials_exposed": False}), 502

@command_center_bp.get("/api/google-sheets/status")
@login_required
def google_sheets_status():
    organization_id = _organization_id(); user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id: return jsonify({"success": False, "error": "organization_required"}), 400
    ref = social_credential_store.public_ref(int(organization_id), int(user_id), "google_sheets")
    return jsonify({"success": True, "provider": "google", "service": "sheets", "connected": bool(ref), "credential_ref": ref, "credentials_exposed": False})

@command_center_bp.post("/api/google-sheets/read")
@login_required
def google_sheets_read():
    organization_id = _organization_id(); user_id = getattr(current_user, "id", None); payload = request.get_json(silent=True) or {}
    if not organization_id or not user_id: return jsonify({"success": False, "error": "organization_required"}), 400
    try:
        access_token = google_sheets_connector_service.access_token(int(organization_id), int(user_id), write=False)
        result = google_sheets_connector_service.read_range(int(organization_id), str(payload.get("spreadsheet_id") or ""), str(payload.get("range") or ""), access_token)
        result.pop("values", None) if not bool(payload.get("include_values", False)) else None
        return jsonify({"success": True, "read": result, "credentials_exposed": False})
    except KeyError: return jsonify({"success": False, "error": "google_sheets_not_connected", "credentials_exposed": False}), 409
    except (ValueError, PermissionError) as exc: return jsonify({"success": False, "error": str(exc), "credentials_exposed": False}), 400
    except Exception: return jsonify({"success": False, "error": "google_sheets_read_failed", "credentials_exposed": False}), 502


# Phase 3 distribution routes are loaded after the command-center blueprint exists.
from app.routes import command_center_phase3_routes  # noqa: F401,E402
