import os

from flask import Blueprint, render_template, request, abort
import os
from flask_login import current_user, login_required

from app.services.ai_service import ask_ai

settings_bp = Blueprint("settings", __name__)


def _require_admin():
    if not current_user.is_authenticated:
        abort(401)
    if getattr(current_user, "role", "user") not in {"admin", "owner"}:
        abort(403)


@settings_bp.route("/settings")
@login_required
def settings():
    _require_admin()
    provider = os.getenv("AI_PROVIDER", "not configured")
    api_status = "Configured" if os.getenv("OPENROUTER_API_KEY") else "Missing"
    debug = os.getenv("DEBUG", "False")
    return render_template("settings.html", provider=provider, api_status=api_status, debug=debug)


@settings_bp.route("/settings/test-ai")
@login_required
def test_ai():
    _require_admin()
    if not os.getenv("OPENROUTER_API_KEY"):
        return "API Key is missing", 503
    try:
        response = ask_ai("Reply with OK")
        return "AI connection successful: " + str(response)[:100]
    except Exception:
        return "AI connection failed", 502


@settings_bp.route("/settings/save", methods=["POST"])
@login_required
def save_settings():
    _require_admin()
    provider = request.form.get("provider", "openrouter").strip().lower()
    if provider not in {"openrouter", "openai", "anthropic", "google", "groq", "mistral", "deepseek"}:
        abort(400)
    if request.form.get("api_key", "").strip():
        return "Secret credentials must be provisioned through the deployment secret manager; they are not written to application files.", 400
    return "Provider configuration validated. Credentials remain managed outside the application."
