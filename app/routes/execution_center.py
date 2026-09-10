import os
from pathlib import Path

import requests
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

execution_bp = Blueprint("execution_center", __name__)

BRIDGE_URL = os.getenv(
    "KEMET_BRIDGE_URL",
    "http://127.0.0.1:8770"
)


def load_token():
    token = os.getenv("KEMET_AGENT_TOKEN", "").strip()

    if token:
        return token

    env_file = (
        Path.home()
        / "products"
        / "Kemet_AI"
        / ".env.agent"
    )

    if env_file.exists():
        for line in env_file.read_text(
            errors="ignore"
        ).splitlines():

            line = line.strip()

            if line.startswith("KEMET_AGENT_TOKEN="):
                return (
                    line.split("=", 1)[1]
                    .strip()
                    .strip('"')
                    .strip("'")
                )

    return ""


def bridge_headers():
    return {
        "Authorization": f"Bearer {load_token()}",
        "Content-Type": "application/json",
    }


def admin_required(error="admin_required"):
    if getattr(current_user, "role", None) != "admin":
        return jsonify({
            "ok": False,
            "error": error,
        }), 403

    return None


@execution_bp.get("/execution-center")
@login_required
def execution_center():
    return render_template("execution_center.html")


@execution_bp.post("/api/execution/plan")
@login_required
def execution_plan():

    data = request.get_json(silent=True) or {}

    instruction = str(
        data.get("instruction", "")
    ).strip()

    if not instruction:
        return jsonify({
            "ok": False,
            "error": "instruction_required"
        }), 400

    try:
        response = requests.post(
            f"{BRIDGE_URL}/execution/plan",
            headers=bridge_headers(),
            json={"instruction": instruction},
            timeout=20,
        )

        return jsonify(response.json()), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502


@execution_bp.post("/api/execution/approve")
@login_required
def execution_approve():

    denied = admin_required(
        "admin_approval_required"
    )

    if denied:
        return denied

    data = request.get_json(silent=True) or {}

    plan = data.get("plan")

    if not isinstance(plan, dict):
        return jsonify({
            "ok": False,
            "error": "execution_plan_required"
        }), 400

    try:
        response = requests.post(
            f"{BRIDGE_URL}/execution/approve",
            headers=bridge_headers(),
            json={
                "plan": plan,
                "approved": True,
                "approver_id": current_user.id,
            },
            timeout=20,
        )

        return jsonify(response.json()), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502


@execution_bp.post("/api/execution/run")
@login_required
def execution_run():

    denied = admin_required(
        "admin_execution_required"
    )

    if denied:
        return denied

    data = request.get_json(silent=True) or {}

    plan = data.get("plan")
    authorization = data.get("authorization")
    action = str(
        data.get("action") or ""
    ).strip()

    if not isinstance(plan, dict):
        return jsonify({
            "ok": False,
            "error": "execution_plan_required"
        }), 400

    if not isinstance(authorization, dict):
        return jsonify({
            "ok": False,
            "error": "execution_authorization_required"
        }), 403

    if not action:
        action = str(
            plan.get("action")
            or plan.get("command")
            or ""
        ).strip()

    if not action:
        return jsonify({
            "ok": False,
            "error": "execution_action_required"
        }), 403

    try:
        response = requests.post(
            f"{BRIDGE_URL}/execution/run",
            headers=bridge_headers(),
            json={
                "plan": plan,
                "authorization": authorization,
                "action": action,
            },
            timeout=130,
        )

        return jsonify(response.json()), response.status_code

    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": str(exc)
        }), 502
