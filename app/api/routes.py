
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from app.models.chat import ChatMessage
from app.models.conversation import Conversation

api = Blueprint("api", __name__)


@api.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "Kemet AI",
        "version": "1.0.0"
    })


@api.route("/api/ready", methods=["GET"])
def readiness():
    from app.services.production_readiness import production_readiness
    result = production_readiness.check()
    return jsonify(result), 200 if result.get("success") else 503


@api.route("/api/history", methods=["GET"])
@login_required
def history():

    messages = (
        ChatMessage.query.filter_by(user_id=current_user.id)
        .join(Conversation, ChatMessage.conversation_id == Conversation.id)
        .filter(Conversation.organization_id == current_user.organization_id)
        .order_by(ChatMessage.id.desc())
        .limit(20)
        .all()
    )

    return jsonify([
        {
            "id": m.id,
            "question": m.question,
            "answer": m.answer,
            "created_at": str(m.created_at)
        }
        for m in messages
    ])

# === KEMET_API_EXECUTION_V1 ===

@api.route("/api/execute", methods=["POST"])
@login_required
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


# === KEMET_DOCUMENT_AUTOMATION_SERVICE_V1 ===
@api.route("/api/document-automation/process", methods=["POST"])
@login_required
def document_automation_process():
    from pathlib import Path
    from uuid import uuid4
    from werkzeug.utils import secure_filename
    from app.services.document_automation import process_files_v4, export_delivery_package_v4

    files = [f for f in request.files.getlist("files") if f and f.filename]
    if not files:
        return jsonify({"ok": False, "error": "files_required"}), 400
    if len(files) > 20:
        return jsonify({"ok": False, "error": "max_20_files_per_job"}), 400

    job_id = uuid4().hex
    root = Path("instance") / "document_jobs" / str(current_user.organization_id) / job_id
    input_dir, output_dir = root / "input", root / "delivery"
    input_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for uploaded in files:
        name = secure_filename(uploaded.filename or "")
        if not name:
            continue
        target = input_dir / name
        uploaded.save(target)
        saved.append(str(target))
    if not saved:
        return jsonify({"ok": False, "error": "valid_files_required"}), 400

    payload = process_files_v4(saved)
    outputs = export_delivery_package_v4(payload, str(output_dir))
    return jsonify({
        "ok": True,
        "job_id": job_id,
        "product": "Kemet Document Intelligence",
        "status": payload.get("readiness_gate", {}).get("status", "REVIEW_REQUIRED"),
        "summary": payload.get("summary", {}),
        "quality": payload.get("quality", {}),
        "outputs": {name: str(Path(path).relative_to(Path("instance"))) for name, path in outputs.items()},
        "human_review_authoritative": True,
    }), 200


@api.route("/api/document-automation/download/<job_id>/<filename>", methods=["GET"])
@login_required
def document_automation_download(job_id, filename):
    from pathlib import Path
    from flask import send_file
    from werkzeug.utils import secure_filename

    safe_job = secure_filename(job_id)
    safe_name = secure_filename(filename)
    if safe_job != job_id or not safe_job or safe_name != filename or not safe_name:
        return jsonify({"ok": False, "error": "invalid_path"}), 400
    root = (Path("instance") / "document_jobs" / str(current_user.organization_id) / safe_job / "delivery").resolve()
    target = (root / safe_name).resolve()
    if target.parent != root or not target.is_file():
        return jsonify({"ok": False, "error": "file_not_found"}), 404
    return send_file(target, as_attachment=True, download_name=safe_name)


@api.route("/api/document-automation/job/<job_id>", methods=["GET"])
@login_required
def document_automation_job(job_id):
    from pathlib import Path
    from werkzeug.utils import secure_filename

    safe_job = secure_filename(job_id)
    if safe_job != job_id or not safe_job:
        return jsonify({"ok": False, "error": "invalid_job_id"}), 400
    root = (Path("instance") / "document_jobs" / str(current_user.organization_id) / safe_job).resolve()
    delivery = (root / "delivery").resolve()
    if delivery.parent != root or not delivery.is_dir():
        return jsonify({"ok": False, "error": "job_not_found"}), 404
    files = sorted(p.name for p in delivery.iterdir() if p.is_file())
    return jsonify({
        "ok": True,
        "job_id": safe_job,
        "product": "Kemet Document Intelligence",
        "status": "DELIVERED" if files else "PROCESSING",
        "files": files,
        "downloads": {name: f"/api/document-automation/download/{safe_job}/{name}" for name in files},
        "human_review_authoritative": True,
    }), 200


# === KEMET_TELEGRAM_COMMERCIAL_INTAKE_V1 ===
@api.route("/api/telegram/webhook", methods=["POST"])
def telegram_webhook():
    import os
    from app.services.channel_webhook_service import channel_webhook_service
    from app.services.revenue_pipeline_service import revenue_pipeline_service

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not channel_webhook_service.verify_telegram(secret_token=secret):
        return jsonify({"ok": False, "error": "telegram_webhook_unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    extracted = channel_webhook_service.extract_telegram(payload)
    if not extracted["external_message_id"] or not extracted["external_user_id"] or not extracted["conversation_id"]:
        return jsonify({"ok": True, "status": "ignored", "reason": "identity_missing"}), 200

    organization_raw = os.getenv("KEMET_TELEGRAM_ORGANIZATION_ID", "").strip()
    try:
        organization_id = int(organization_raw)
    except (TypeError, ValueError):
        organization_id = 0
    if organization_id <= 0:
        return jsonify({"ok": False, "error": "telegram_organization_not_configured"}), 503

    identity = channel_webhook_service.extract_telegram_commercial_identity(extracted["text"])
    if not identity["email"] or not identity["company_name"]:
        return jsonify({
            "ok": True,
            "status": "qualification_required",
            "required": ["company_name", "email"],
            "example": "Company: Example Co | Email: customer@example.com",
        }), 200

    result = revenue_pipeline_service.intake_telegram_prospect(
        organization_id=organization_id,
        telegram_user_id=extracted["external_user_id"],
        telegram_chat_id=extracted["conversation_id"],
        telegram_message_id=extracted["external_message_id"],
        company_name=identity["company_name"],
        email=identity["email"],
        message=extracted["text"],
    )
    return jsonify({"ok": True, "status": "inquiry_created", "pipeline": result}), 200
