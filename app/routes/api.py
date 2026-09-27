from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.core.rate_limit import limiter
from app.services.chat_service import ChatService
from app.automation.engine import engine

api = Blueprint("api", __name__)


@api.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Kemet_AI"
    })


@api.route("/ready", methods=["GET"])
def readiness():
    from app.services.production_readiness import production_readiness
    result = production_readiness.check()
    return jsonify(result), 200 if result.get("success") else 503


@api.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json()

    message = data.get("message", "")
    conversation_id = data.get("conversation_id")

    service = ChatService()

    automation_results = engine.execute(
        event="message_received",
        organization_id=current_user.organization_id,
        data={
            "message": message,
            "user_id": current_user.id,
            "conversation_id": conversation_id
        }
    )

    reply, new_conversation_id = service.generate_reply(
        message=message,
        user_id=current_user.id,
        organization_id=current_user.organization_id,
        conversation_id=conversation_id
    )

    return jsonify({
        "reply": reply,
        "conversation_id": new_conversation_id
    })


# === KEMET_API_EXECUTION_V1 ===

@api.route("/execute", methods=["POST"])
@login_required
@limiter.limit("30 per minute", methods=["POST"])
def execute():
    import os
    import requests
    from dotenv import load_dotenv

    load_dotenv(".env.agent", override=False)

    data = request.get_json(silent=True) or {}

    action = str(data.get("action") or "").strip()
    payload = data.get("payload") or {}

    allowed = {
        "health",
        "compile",
        "git_status",
        "test_health",
        "list_files",
        "read_file",
        "search_code",
        "write_file",
    }

    if action not in allowed:
        return jsonify({
            "ok": False,
            "error": "execution_action_not_allowed",
            "allowed": sorted(allowed),
        }), 403

    token = os.getenv("KEMET_AGENT_TOKEN", "")

    if not token:
        return jsonify({
            "ok": False,
            "error": "agent_token_missing",
        }), 503

    try:
        response = requests.post(
            "http://127.0.0.1:8770/execute",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "action": action,
                "payload": payload,
            },
            timeout=120,
        )

        try:
            result = response.json()
        except Exception:
            result = {
                "ok": False,
                "error": "invalid_bridge_response",
                "raw": response.text,
            }

        return jsonify(result), response.status_code

    except requests.RequestException as exc:
        return jsonify({
            "ok": False,
            "error": "bridge_connection_failed",
            "detail": str(exc),
        }), 502


# === KEMET_COMMERCIAL_API_V1 ===
@api.route("/v1/keys", methods=["POST"])
@login_required
@limiter.limit("10 per hour", methods=["POST"])
def create_commercial_api_key():
    data=request.get_json(silent=True) or {}
    scopes=data.get("scopes")
    if scopes is not None and not isinstance(scopes,list):
        return jsonify({"ok":False,"error":"scopes_must_be_list"}),400
    organization_id=getattr(current_user,"organization_id",None)
    if not organization_id: return jsonify({"ok":False,"error":"organization_required"}),403
    key,raw=create_api_key(organization_id=organization_id,name=str(data.get("name") or "Kemet API key"),scopes=scopes or ["document_intelligence"])
    return jsonify({"ok":True,"api_key":raw,"key_prefix":key.key_prefix,"warning":"Store this key securely. It will not be shown again.","organization_id":key.organization_id,"scopes":sorted(set(scopes or ["document_intelligence"]))}),201

@api.route("/v1/keys", methods=["GET"])
@login_required
def list_commercial_api_keys():
    import json
    from app.models.api_key import ApiKey
    org=getattr(current_user,"organization_id",None)
    keys=ApiKey.query.filter_by(organization_id=org).order_by(ApiKey.id.desc()).all()
    return jsonify({"ok":True,"keys":[{"id":k.id,"name":k.name,"key_prefix":k.key_prefix,"status":k.status,"requests_count":k.requests_count,"last_used_at":k.last_used_at.isoformat() if k.last_used_at else None,"created_at":k.created_at.isoformat() if k.created_at else None,"scopes":json.loads(k.scopes_json or "[]")} for k in keys]})

@api.route("/v1/keys/<int:key_id>/revoke", methods=["POST"])
@login_required
def revoke_commercial_api_key(key_id):
    from app.models.api_key import ApiKey
    org=getattr(current_user,"organization_id",None)
    key=ApiKey.query.filter_by(id=key_id,organization_id=org).first()
    if not key: return jsonify({"ok":False,"error":"api_key_not_found"}),404
    revoke_api_key(key); return jsonify({"ok":True,"status":"revoked","key_id":key.id})

@api.route("/v1/document-intelligence/capability", methods=["GET"])
@limiter.limit("60 per minute", methods=["GET"])
@require_api_key("document_intelligence")
def document_intelligence_capability():
    from app.services.document_intelligence_service import document_intelligence_service
    snapshot=document_intelligence_service.snapshot(g.kemet_organization_id)
    return jsonify({"ok":True,"product":"Kemet Document Intelligence API","status":"capability_verified","organization_id":g.kemet_organization_id,"capability":snapshot,"commercial_boundary":{"api_access":True,"document_extraction_execution":False,"reason":"Document provider execution remains governance-gated until verified in the canonical runtime."}})
