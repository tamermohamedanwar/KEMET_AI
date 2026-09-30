from __future__ import annotations

from typing import Any

from app.core.external_task_lifecycle import ExternalTaskLifecycleError, external_task_lifecycle
from app.core.federation.specialist_registry import specialist_registry


class ExternalTaskControlPlane:
    VERSION = "1.1"

    def get(self, *, organization_id: int, execution_key: str, refresh: bool = False) -> dict[str, Any]:
        record = external_task_lifecycle.get(
            organization_id=int(organization_id), execution_key=str(execution_key)
        )
        if not record:
            raise ExternalTaskLifecycleError("external_task_not_found")
        if refresh and record["status"] not in external_task_lifecycle.TERMINAL:
            record = self.refresh(record=record)
        return self._normalize(record)

    def _normalize(self, record: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(record.get("metadata") or {})
        result = metadata.get("result")
        error = metadata.get("error")
        return {
            **record,
            "lifecycle": {
                "version": self.VERSION,
                "status": record["status"],
                "terminal": record["status"] in external_task_lifecycle.TERMINAL,
                "ambiguous": record["status"] == "ambiguous",
            },
            "result": result,
            "error": error,
            "evidence": {
                "execution_key": record["execution_key"],
                "plan_hash": record["plan_hash"],
                "provider_id": record["provider_id"],
                "external_task_id": record["external_task_id"],
                "last_seen_at": record.get("last_seen_at"),
            },
        }

    def reconcile_completion(
        self, *, organization_id: int, execution_key: str, provider_id: str,
        external_task_id: str, plan_hash: str, request_id: str | None = None,
        result: Any = None, error: Any = None, metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._normalize(external_task_lifecycle.reconcile_provider_completion(
            organization_id=organization_id, execution_key=execution_key,
            provider_id=provider_id, external_task_id=external_task_id,
            plan_hash=plan_hash, request_id=request_id, result=result, error=error,
            metadata=metadata, trace_id=execution_key, correlation_id=execution_key,
        ))

    def refresh(self, *, record: dict[str, Any]) -> dict[str, Any]:
        provider = specialist_registry.get(str(record["provider_id"]))
        inspect = getattr(provider, "inspect", None) if provider else None
        if not callable(inspect):
            return record
        try:
            snapshot = inspect(external_task_id=str(record["external_task_id"]))
        except Exception as exc:
            return self._normalize({
                **record,
                "metadata": {
                    **dict(record.get("metadata") or {}),
                    "refresh_error": type(exc).__name__,
                },
            })
        status = str(snapshot.get("status") or record["status"])
        mapped = {
            "running": "running",
            "stopped": "completed",
            "waiting": "submitted",
            "error": "failed",
            "pending": "submitted",
        }.get(status)
        if not mapped:
            return self._normalize(record)
        metadata = dict(snapshot.get("metadata") or {})
        provider_request_id = snapshot.get("request_id")
        if provider_request_id:
            metadata["provider_request_id"] = provider_request_id
        if mapped == "completed":
            return self.reconcile_completion(
                organization_id=int(record["organization_id"]),
                execution_key=str(record["execution_key"]),
                provider_id=str(record["provider_id"]),
                external_task_id=str(record["external_task_id"]),
                plan_hash=str(record["plan_hash"]),
                request_id=str(provider_request_id) if provider_request_id else None,
                result=snapshot.get("result"),
                error=snapshot.get("error"),
                metadata=metadata,
            )
        if mapped == "failed":
            if record["status"] in {"submitted", "running", "ambiguous"}:
                return self._normalize(external_task_lifecycle.reconcile_provider_completion(
                    organization_id=int(record["organization_id"]),
                    execution_key=str(record["execution_key"]),
                    provider_id=str(record["provider_id"]),
                    external_task_id=str(record["external_task_id"]),
                    plan_hash=str(record["plan_hash"]),
                    request_id=str(provider_request_id) if provider_request_id else None,
                    result=snapshot.get("result"), error=snapshot.get("error") or "provider_failed",
                    metadata=metadata,
                    trace_id=str(record["execution_key"]), correlation_id=str(record["execution_key"]),
                ))
            return self._normalize(record)
        return self._normalize(external_task_lifecycle.update_state(
            organization_id=int(record["organization_id"]),
            execution_key=str(record["execution_key"]), status=mapped,
            provider_id=str(record["provider_id"]),
            external_task_id=str(record["external_task_id"]),
            plan_hash=str(record["plan_hash"]), metadata=metadata,
            trace_id=str(record["execution_key"]), correlation_id=str(record["execution_key"]),
        ))


external_task_control_plane = ExternalTaskControlPlane()
