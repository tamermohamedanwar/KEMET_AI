from __future__ import annotations

import os
from typing import Any, Mapping

import requests

from app.core.execution.execution_boundary import execution_boundary
from app.core.egress_policy import validate_public_http_target
from app.core.governed_http import governed_request
from app.core.secret_boundary import redact
from app.core.federation.specialist_contracts import SpecialistAdapter, SpecialistRequest, SpecialistResponse
from app.core.external_task_lifecycle import external_task_lifecycle


class ManusAdapter(SpecialistAdapter):
    provider_id = "manus"
    execution_kind = "agent"
    capabilities = frozenset({"agentic", "research", "long_context", "tool_calling"})
    base_url = "https://api.manus.ai"
    CREATE_ACTION = "manus.task.create"

    def configured(self) -> bool:
        return bool(os.getenv("MANUS_API_KEY"))

    def inspect(self, *, external_task_id: str) -> dict[str, Any]:
        snapshot = self._task_detail(external_task_id=external_task_id)
        status = snapshot.get("status")
        result: Any = None
        if status == "stopped":
            result = self._latest_result(external_task_id=external_task_id)
        if result is not None:
            snapshot["result"] = result
        return snapshot

    def _task_detail(self, *, external_task_id: str) -> dict[str, Any]:
        if not self.configured():
            raise RuntimeError("MANUS_API_KEY is not configured")
        endpoint = validate_public_http_target(f"{self.base_url}/v2/task.detail", allow_hosts={"api.manus.ai"})
        response = governed_request("GET", 
            endpoint,
            headers={"x-manus-api-key": os.environ["MANUS_API_KEY"]},
            params={"task_id": str(external_task_id)},
            timeout=15,
            allow_redirects=False,
        )
        data = response.json()
        if not response.ok or not data.get("ok"):
            raise RuntimeError("Manus task inspection failed")
        task = data.get("task") or {}
        return {
            "status": task.get("status"),
            "request_id": data.get("request_id"),
            "metadata": {
                "task_title": task.get("task_title"),
                "task_url": task.get("task_url"),
                "status_detail": task.get("status_detail"),
            },
        }

    def _latest_result(self, *, external_task_id: str) -> Any:
        endpoint = validate_public_http_target(f"{self.base_url}/v2/task.listMessages", allow_hosts={"api.manus.ai"})
        response = governed_request("GET", 
            endpoint,
            headers={"x-manus-api-key": os.environ["MANUS_API_KEY"]},
            params={"task_id": str(external_task_id)},
            timeout=15,
            allow_redirects=False,
        )
        data = response.json()
        if not response.ok or not data.get("ok"):
            raise RuntimeError("Manus task messages retrieval failed")
        messages = data.get("messages") or []
        for message in reversed(messages):
            content = message.get("content")
            if content:
                return content
        return None

    def submit(
        self,
        request: SpecialistRequest,
        *,
        plan: Mapping[str, Any] | None = None,
        authorization: Mapping[str, Any] | None = None,
    ) -> SpecialistResponse:
        if plan is None or authorization is None:
            raise PermissionError("Manus submission requires governed authorization")
        gate = execution_boundary.require(dict(plan), dict(authorization), self.CREATE_ACTION)
        execution_key = str(plan.get("execution_key") or request.metadata.get("execution_key") or "")
        if not execution_key:
            raise PermissionError("Manus submission requires execution identity")
        effective_plan_hash = str(plan.get("plan_hash") or authorization.get("plan_hash") or "")
        if not effective_plan_hash:
            raise PermissionError("Manus submission requires plan identity")
        if not gate.get("allowed"):
            raise PermissionError(str(gate.get("error") or "governed_execution_denied"))
        reservation = external_task_lifecycle.begin_submission(
            organization_id=request.organization_id, provider_id=self.provider_id,
            execution_key=execution_key, plan_hash=effective_plan_hash, action=self.CREATE_ACTION,
            trace_id=str(request.metadata.get("trace_id") or "") or None,
            correlation_id=str(request.metadata.get("correlation_id") or "") or None,
        )
        if not reservation["created"]:
            existing = reservation["record"]
            if existing["status"] == "submitting":
                raise PermissionError("external_task_submission_in_progress")
            return SpecialistResponse(
                provider_id=self.provider_id, task_id=request.task_id, status=existing["status"],
                external_task_id=existing["external_task_id"], request_id=existing.get("request_id"),
                metadata=existing.get("metadata", {}),
            )
        if not self.configured():
            raise RuntimeError("MANUS_API_KEY is not configured")
        payload: dict[str, Any] = {
            "message": {"content": request.prompt},
            "share_visibility": "private",
        }
        if request.model:
            payload["agent_profile"] = request.model
        try:
            endpoint = validate_public_http_target(f"{self.base_url}/v2/task.create", allow_hosts={"api.manus.ai"})
            response = governed_request("POST", 
                endpoint,
                headers={"Content-Type": "application/json", "x-manus-api-key": os.environ["MANUS_API_KEY"]},
                json=payload,
                timeout=15,
                allow_redirects=False,
            )
        except Exception as exc:
            external_task_lifecycle.mark_ambiguous(
                organization_id=request.organization_id, execution_key=execution_key,
                reason=type(exc).__name__, trace_id=str(request.metadata.get("trace_id") or "") or None,
                correlation_id=str(request.metadata.get("correlation_id") or "") or None,
            )
            raise RuntimeError("Manus task submission status is ambiguous") from None
        data = response.json()
        if not response.ok or not data.get("ok"):
            raise RuntimeError("Manus task submission failed")
        external_task_id = data.get("task_id")
        if not external_task_id:
            raise RuntimeError("Manus response missing task identity")
        plan_hash = effective_plan_hash
        if not plan_hash:
            raise PermissionError("Manus submission requires plan identity")
        external_task_lifecycle.create_submission(
            organization_id=request.organization_id, provider_id=self.provider_id,
            external_task_id=str(external_task_id), execution_key=execution_key,
            plan_hash=plan_hash, action=self.CREATE_ACTION, request_id=data.get("request_id"),
            metadata=redact({"share_visibility": "private", "async": True,
                      "authorization_source": gate.get("verification", {}).get("authorization_source", "human")}),
            trace_id=str(request.metadata.get("trace_id") or "") or None,
            correlation_id=str(request.metadata.get("correlation_id") or "") or None,
        )
        return SpecialistResponse(
            provider_id=self.provider_id, task_id=request.task_id, status="submitted",
            external_task_id=str(external_task_id), request_id=data.get("request_id"),
            metadata={"share_visibility": "private", "async": True, "authorization_source": gate.get("verification", {}).get("authorization_source", "human")},
        )
