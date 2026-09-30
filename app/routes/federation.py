from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.core.federation.context_gateway import FederationContextGateway
from app.core.federation.context_models import ContextEnvelope
from app.core.federation.collaboration_session import CollaborationSessionService
from app.core.federation.model_handoff import create_handoff, verify_handoff, ModelHandoff
from app.core.federation.provider_connections import ProviderConnectionRegistry
from app.core.federation.connection_lifecycle import ConnectionLifecycleService
from app.core.ai_federation import ai_federation
from app.models.provider_connection import ProviderConnectionRecord
from app.core.federation.external_intelligence import external_intelligence
from app.core.federation.research_engine import research_engine, ResearchSource
from app.core.federation.research_workflows import research_workflows
from app.core.federation.capability_federation import capability_federation
from app.core.evidence import execution_evidence_fabric

connection_registry = ProviderConnectionRegistry()

federation_bp = Blueprint("federation", __name__, url_prefix="/api/federation")
gateway = FederationContextGateway()


def _scope():
    organization_id = getattr(current_user, "organization_id", None)
    user_id = getattr(current_user, "id", None)
    if not organization_id or not user_id:
        return None
    return int(organization_id), int(user_id)


@federation_bp.post("/context/ingest")
@login_required
def ingest_context():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    envelope = ContextEnvelope(
        provider_id=str(data.get("provider_id", "")),
        external_conversation_id=str(data.get("external_conversation_id", "")),
        organization_id=scope[0],
        user_id=scope[1],
        project_id=str(data.get("project_id") or "kemet-ai"),
        task_id=data.get("task_id"),
        role=str(data.get("role") or "participant"),
        summary=str(data.get("summary") or ""),
        decisions=tuple(str(x) for x in (data.get("decisions") or [])),
        artifacts=tuple(x for x in (data.get("artifacts") or []) if isinstance(x, dict)),
        source_metadata=data.get("source_metadata") if isinstance(data.get("source_metadata"), dict) else {},
    )
    try:
        return jsonify({"success": True, **gateway.ingest(envelope)})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@federation_bp.get("/context/snapshot")
@login_required
def context_snapshot():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    snap = gateway.snapshot(scope[0], scope[1], request.args.get("project_id") or "kemet-ai", request.args.get("task_id"))
    return jsonify({"success": True, "snapshot": snap.as_dict(), "context_hash": snap.fingerprint()})


@federation_bp.post("/session")
@login_required
def upsert_session():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    try:
        row = CollaborationSessionService.upsert(
            scope[0], scope[1], str(data.get("session_id", "")),
            str(data.get("project_id") or "kemet-ai"), data.get("task_id"),
            [str(x) for x in (data.get("providers") or [])],
            data.get("state") if isinstance(data.get("state"), dict) else {},
        )
        return jsonify({"success": True, "session_id": row.session_id, "context_hash": row.context_hash})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@federation_bp.post("/handoff")
@login_required
def handoff():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    target = str(data.get("target_provider", ""))
    source = str(data.get("source_provider", "kemet"))
    task_id = str(data.get("task_id", ""))
    context = data.get("context") if isinstance(data.get("context"), dict) else {}
    if not target or not task_id:
        return jsonify({"success": False, "error": "target_provider_and_task_id_required"}), 400
    item = create_handoff(
        organization_id=scope[0], user_id=scope[1], source_provider=source,
        target_provider=target, task_id=task_id, context=context,
        requested_role=str(data.get("requested_role") or "specialist"),
    )
    return jsonify({"success": True, "handoff": item.as_dict()})


@federation_bp.post("/handoff/verify")
@login_required
def verify_handoff_route():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    try:
        item = ModelHandoff(**data)
        valid = verify_handoff(item, organization_id=scope[0], user_id=scope[1], target_provider=data.get("target_provider"))
    except (TypeError, ValueError):
        valid = False
    return jsonify({"success": True, "valid": valid}), (200 if valid else 400)


@federation_bp.get("/connections")
@login_required
def provider_connections():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    items = [item.as_dict() for item in connection_registry.all(*scope)]
    return jsonify({"success": True, "version": connection_registry.VERSION, "connections": items})


@federation_bp.get("/connections/<provider_id>")
@login_required
def provider_connection(provider_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    item = connection_registry.capabilities(provider_id, *scope)
    return jsonify({"success": True, "connection": item.as_dict()}), (200 if item.status != "unsupported" else 404)


@federation_bp.post("/connections/<provider_id>/handoff")
@login_required
def provider_handoff(provider_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    try:
        item = connection_registry.register_handoff(provider_id, *scope, metadata=data.get("metadata"))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 404
    return jsonify({"success": True, "connection": item.as_dict()})


@federation_bp.post("/connections/<provider_id>/register")
@login_required
def register_connection(provider_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    try:
        row = ConnectionLifecycleService.register(
            scope[0], scope[1], provider_id,
            mode=str(data.get("mode") or "api"),
            scopes=[str(x) for x in (data.get("scopes") or [])],
            metadata=data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
            credential_ref=str(data.get("credential_ref")) if data.get("credential_ref") else None,
            provider_account_ref=str(data.get("provider_account_ref")) if data.get("provider_account_ref") else None,
            provider_project_ref=str(data.get("provider_project_ref")) if data.get("provider_project_ref") else None,
        )
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "connection": ConnectionLifecycleService.as_public(row)})


@federation_bp.post("/connections/<provider_id>/verify")
@login_required
def verify_connection(provider_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    row = ProviderConnectionRecord.query.filter_by(
        organization_id=scope[0], user_id=scope[1], provider_id=provider_id
    ).order_by(ProviderConnectionRecord.id.desc()).first()
    data = request.get_json(silent=True) or {}
    if not row:
        try:
            row = ConnectionLifecycleService.register(scope[0], scope[1], provider_id, mode="api")
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
    result = ConnectionLifecycleService.verify(row, live=bool(data.get("live")))
    return jsonify({"success": True, "verification": result, "connection": ConnectionLifecycleService.as_public(row)})


@federation_bp.post("/connections/<provider_id>/revoke")
@login_required
def revoke_connection(provider_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    row = ProviderConnectionRecord.query.filter_by(
        organization_id=scope[0], user_id=scope[1], provider_id=provider_id
    ).first()
    if not row:
        return jsonify({"success": False, "error": "connection_not_found"}), 404
    ConnectionLifecycleService.revoke(row)
    return jsonify({"success": True, "connection": ConnectionLifecycleService.as_public(row)})



@federation_bp.get("/connections/status")
@login_required
def provider_connection_status():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    organization_id, user_id = scope
    durable = {
        row.provider_id: ConnectionLifecycleService.as_public(row)
        for row in ConnectionLifecycleService.list_for_user(organization_id, user_id)
    }
    items = []
    for profile in ai_federation.all():
        live = durable.get(profile.provider_id)
        registry_item = connection_registry.capabilities(provider_id=profile.provider_id,
                                                          organization_id=organization_id,
                                                          user_id=user_id)
        status = live["status"] if live else registry_item.status
        items.append({
            "provider_id": profile.provider_id,
            "display_name": profile.display_name,
            "status": status,
            "mode": live["mode"] if live else registry_item.mode,
            "capabilities": sorted(profile.capabilities),
            "configured": profile.is_configured(),
            "verified": status == "verified",
            "execution_ready": bool(profile.execution_ready and status == "verified"),
            "connection_id": live["id"] if live else None,
            "last_verified_at": live["last_verified_at"] if live else None,
        })
    return jsonify({"success": True, "version": "2.0", "organization_id": organization_id,
                    "providers": items})


@federation_bp.get("/routing/preview")
@login_required
def routing_preview():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    prompt = str(request.args.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"success": False, "error": "prompt_required"}), 400
    durable = ConnectionLifecycleService.list_for_user(scope[0], scope[1])
    verified = {row.provider_id for row in durable if row.status == "verified"}
    from app.core.federation.routing_preview import federation_routing_preview
    try:
        result = federation_routing_preview.preview(prompt, organization_id=scope[0],
                                                     verified_provider_ids=verified)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    return jsonify({"success": True, "version": federation_routing_preview.VERSION,
                    "preview": result.as_dict(), "executed": False,
                    "database_mutation": False, "external_call": False})


@federation_bp.get("/sources")
@login_required
def external_sources():
    return jsonify({"success": True, "version": external_intelligence.VERSION, "sources": external_intelligence.catalog()})


@federation_bp.post("/intelligence/read")
@login_required
def external_intelligence_read():
    data = request.get_json(silent=True) or {}
    source_id = str(data.get("source_id") or "").strip()
    url = str(data.get("url") or "").strip() or None
    query = str(data.get("query") or "").strip() or None
    if not source_id:
        return jsonify({"success": False, "error": "source_id_required"}), 400
    try:
        evidence = external_intelligence.read(source_id, url=url, query=query)
        organization_id, user_id = _scope() or (0, 0)
        task_id = str(data.get("task_id") or f"intel-{source_id}")
        package = execution_evidence_fabric.source_package(
            task_id=task_id, organization_id=int(organization_id), evidences=[evidence.as_dict()]
        )
        return jsonify({
            "success": True,
            "evidence": evidence.as_dict(),
            "evidence_package": package,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        })
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"success": False, "error": str(exc), "retryable": False}), 503


@federation_bp.get("/research/workflows")
@login_required
def research_workflow_catalog():
    return jsonify({"success": True, "version": research_workflows.VERSION, "workflows": research_workflows.catalog()})


@federation_bp.post("/research/workflows/<workflow_id>/prepare")
@login_required
def research_workflow_prepare(workflow_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "research_question_required"}), 400
    try:
        result = research_workflows.prepare(workflow_id, question)
        return jsonify({"success": True, "organization_id": scope[0], **result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@federation_bp.post("/research")
@login_required
def research():
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()
    task_id = str(data.get("task_id") or "").strip() or "research"
    source_ids = data.get("sources") if isinstance(data.get("sources"), list) else None
    if not question:
        return jsonify({"success": False, "error": "research_question_required"}), 400

    def read_source(source_id: str, query: str):
        evidence = external_intelligence.read(source_id, query=query)
        return ResearchSource(
            source_id=evidence.source_id,
            locator=evidence.locator,
            title=evidence.title,
            content=evidence.content,
            confidence=evidence.confidence,
            metadata={**evidence.metadata, "retrieval": "external_intelligence"},
        )

    policy = {
        "operation": "read",
        "purpose": "research",
        "model_use_allowed": True,
        "export_allowed": False,
        "training_allowed": False,
        "citation_required": True,
    }
    policy_fingerprint = execution_evidence_fabric.digest(policy)
    try:
        result = research_engine.run(
            question, task_id=task_id, organization_id=scope[0],
            source_reader=read_source, source_ids=source_ids,
            policy_fingerprint=policy_fingerprint,
        )
        return jsonify({"success": True, **result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400



@federation_bp.post("/research/workflows/<workflow_id>/run")
@login_required
def research_workflow_run(workflow_id: str):
    scope = _scope()
    if not scope:
        return jsonify({"success": False, "error": "organization_required"}), 400
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()
    task_id = str(data.get("task_id") or "").strip() or f"research-{workflow_id}"
    if not question:
        return jsonify({"success": False, "error": "research_question_required"}), 400

    def read_source(source_id: str, query: str):
        evidence = external_intelligence.read(source_id, query=query)
        return ResearchSource(
            source_id=evidence.source_id,
            locator=evidence.locator,
            title=evidence.title,
            content=evidence.content,
            confidence=evidence.confidence,
            metadata={**evidence.metadata, "retrieval": "external_intelligence"},
        )

    policy = {
        "operation": "read",
        "purpose": "research_workflow",
        "model_use_allowed": True,
        "export_allowed": False,
        "training_allowed": False,
        "citation_required": True,
    }
    policy_fingerprint = execution_evidence_fabric.digest(policy)
    try:
        result = research_workflows.run(
            workflow_id, question, task_id=task_id,
            organization_id=scope[0], source_reader=read_source,
            policy_fingerprint=policy_fingerprint,
            project_context_hash=str(data.get("project_context_hash") or ""),
            plan_hash=str(data.get("plan_hash") or ""),
        )
        return jsonify({"success": True, "organization_id": scope[0], **result})
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400


@federation_bp.get("/capabilities")
@login_required
def federation_capabilities():
    """Read-only capability federation snapshot for the Unified Command Center."""
    return jsonify({
        "success": True,
        "capability_federation": capability_federation.snapshot(configured_only=False),
        "governance": {
            "read_only": True,
            "external_execution": False,
            "database_mutation": False,
        },
    }), 200
