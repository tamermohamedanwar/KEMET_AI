import os
from flask import Blueprint, render_template, request
from app.services.ai_service import ask_ai

settings_bp = Blueprint("settings", __name__)

@settings_bp.route("/settings")
def settings():
    provider = os.getenv("AI_PROVIDER", "not configured")
    api_status = "Configured" if os.getenv("OPENROUTER_API_KEY") else "Missing"
    debug = os.getenv("DEBUG", "False")

    return render_template(
        "settings.html",
        provider=provider,
        api_status=api_status,
        debug=debug
    )


@settings_bp.route("/settings/test-ai")
def test_ai():
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return "API Key is missing"

    try:
        response = ask_ai("Reply with OK")
        return "AI connection successful: " + str(response)[:100]
    except Exception as e:
        return "AI connection failed: " + str(e)


@settings_bp.route("/settings/save", methods=["POST"])
def save_settings():
    provider = request.form.get("provider", "openrouter")
    api_key = request.form.get("api_key", "")

    from pathlib import Path

    env_file = Path(__file__).resolve().parents[2] / ".env.local"

    with open(env_file, "w") as f:
        f.write(f"AI_PROVIDER={provider}\n")
        if api_key:
            f.write(f"OPENROUTER_API_KEY={api_key}\n")

    return "Settings saved successfully"
