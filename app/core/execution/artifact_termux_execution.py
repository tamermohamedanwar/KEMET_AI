from __future__ import annotations

import os
from typing import Any

import requests


class ArtifactTermuxExecutionError(RuntimeError):
    pass


class ArtifactTermuxExecutionService:
    VERSION = "1.0"

    def __init__(self):
        self.bridge_url = os.getenv(
            "KEMET_BRIDGE_URL", "http://127.0.0.1:8770"
        ).rstrip("/")
        self.token = os.getenv("KEMET_AGENT_TOKEN", "").strip()

    def execute(
        self,
        *,
        artifacts: list[dict[str, Any]],
        plan: dict[str, Any],
        authorization: dict[str, Any],
        action: str,
        preview_digest: str,
    ) -> dict[str, Any]:
        if action != "artifact_write":
            raise ArtifactTermuxExecutionError("artifact_action_binding_invalid")
        if not isinstance(artifacts, list) or not artifacts:
            raise ArtifactTermuxExecutionError("artifact_binding_required")
        if not preview_digest:
            raise ArtifactTermuxExecutionError("artifact_preview_binding_required")
        if not isinstance(plan, dict) or not isinstance(authorization, dict):
            raise ArtifactTermuxExecutionError("artifact_execution_binding_required")
        if not self.token:
            raise ArtifactTermuxExecutionError("termux_bridge_token_missing")
        response = requests.post(
            f"{self.bridge_url}/termux/artifact",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            json={
                "artifacts": artifacts,
                "plan": plan,
                "authorization": authorization,
                "action": action,
                "preview_digest": preview_digest,
            },
            timeout=130,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise ArtifactTermuxExecutionError("termux_invalid_response") from exc
        if response.status_code >= 400 or not payload.get("ok"):
            raise ArtifactTermuxExecutionError(
                str(payload.get("error") or "artifact_execution_failed")
            )
        return payload


artifact_termux_execution = ArtifactTermuxExecutionService()
