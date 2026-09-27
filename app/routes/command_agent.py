from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.core.agent_runtime import kemet_agent_runtime

command_agent_bp = Blueprint(
    "command_agent",
    __name__,
    url_prefix="/api",
)


@command_agent_bp.post("/command-agent")
@login_required
def command_agent():
    data = request.get_json(silent=True) or {}
    instruction = str(data.get("instruction", "")).strip()

    if not instruction:
        return jsonify({"ok": False, "error": "instruction_required"}), 400

    organization_id = getattr(current_user, "organization_id", None)
    user_id = getattr(current_user, "id", None)
    if not organization_id:
        return jsonify({"ok": False, "error": "organization_id_required"}), 403

    try:
        run = kemet_agent_runtime.ask(
            instruction,
            organization_id=int(organization_id),
            user_id=user_id,
        )
        run, decision = kemet_agent_runtime.reason(run)

        return jsonify({
            "ok": True,
            "engine": "kemet_agent_runtime",
            "run": {
                "run_id": run.run_id,
                "state": run.state,
                "instruction": run.instruction,
                "classification": run.classification,
                "plan": run.plan,
                "simulation": run.simulation,
                "decision": run.decision,
                "evidence": list(run.evidence),
                "outcome": run.outcome,
                "learning": run.learning,
                "next_action": run.next_action,
                "evidence_context_hash": run.evidence_context_hash,
            },
            "decision": decision.as_dict(),
            "execution": None,
            "approval_required": run.state == "approve",
            "executed": False,
            "external_execution_authority": False,
            "canonical_execution_runtime": True,
        }), 200

    except ValueError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), 400
    except Exception as exc:
        return jsonify({
            "ok": False,
            "error": "command_agent_failed",
            "message": str(exc),
        }), 502
