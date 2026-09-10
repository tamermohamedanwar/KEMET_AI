from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AutomationEvent:
    event_id: str
    organization_id: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "internal"
    occurred_at: str = ""
    correlation_id: str | None = None

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TriggerDefinition:
    trigger_id: str
    organization_id: int
    event_type: str
    workflow_id: str
    enabled: bool = True
    conditions: dict[str, Any] = field(default_factory=dict)
    priority: int = 100

    def canonical(self) -> dict[str, Any]:
        return asdict(self)


class EventTriggerPlane:
    """Normalize, deduplicate, match and authorize event-driven automation intents."""

    VERSION = "1.0"

    def __init__(self) -> None:
        self._triggers: dict[tuple[int, str], TriggerDefinition] = {}
        self._seen: set[tuple[int, str]] = set()

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _fingerprint(organization_id: int, event_type: str, payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            {"organization_id": organization_id, "event_type": event_type, "payload": payload},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def register(self, trigger: TriggerDefinition) -> dict[str, Any]:
        if trigger.organization_id <= 0:
            return {"registered": False, "errors": ["organization_id_required"]}
        if not trigger.trigger_id.strip() or not trigger.event_type.strip():
            return {"registered": False, "errors": ["trigger_identity_required"]}
        if not trigger.workflow_id.strip():
            return {"registered": False, "errors": ["workflow_id_required"]}
        if trigger.priority < 0:
            return {"registered": False, "errors": ["invalid_priority"]}
        key = (trigger.organization_id, trigger.trigger_id)
        self._triggers[key] = trigger
        return {"registered": True, "trigger_id": trigger.trigger_id}

    def unregister(self, organization_id: int, trigger_id: str) -> bool:
        return self._triggers.pop((int(organization_id), self._clean(trigger_id)), None) is not None

    def normalize(
        self,
        *,
        organization_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        source: str = "internal",
        correlation_id: str | None = None,
        occurred_at: str | None = None,
    ) -> AutomationEvent:
        org_id = int(organization_id)
        event_name = self._clean(event_type)
        if org_id <= 0:
            raise ValueError("organization_id_required")
        if not event_name:
            raise ValueError("event_type_required")
        data = dict(payload or {})
        fingerprint = event_id or self._fingerprint(org_id, event_name, data)
        return AutomationEvent(
            event_id=self._clean(fingerprint),
            organization_id=org_id,
            event_type=event_name,
            payload=data,
            source=self._clean(source) or "internal",
            occurred_at=occurred_at or datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
        )

    @staticmethod
    def _matches(trigger: TriggerDefinition, event: AutomationEvent) -> bool:
        if not trigger.enabled or trigger.event_type != event.event_type:
            return False
        for key, expected in trigger.conditions.items():
            if event.payload.get(key) != expected:
                return False
        return True

    def ingest(self, event: AutomationEvent) -> dict[str, Any]:
        dedupe_key = (event.organization_id, event.event_id)
        if dedupe_key in self._seen:
            return {
                "accepted": False,
                "status": "deduplicated",
                "event": event.canonical(),
                "intents": [],
            }

        self._seen.add(dedupe_key)
        matches = [
            trigger
            for (org_id, _), trigger in self._triggers.items()
            if org_id == event.organization_id and self._matches(trigger, event)
        ]
        matches.sort(key=lambda item: (item.priority, item.trigger_id))
        intents = [
            {
                "intent_id": hashlib.sha256(
                    f"{event.event_id}:{trigger.trigger_id}".encode("utf-8")
                ).hexdigest(),
                "organization_id": event.organization_id,
                "event_id": event.event_id,
                "event_type": event.event_type,
                "workflow_id": trigger.workflow_id,
                "trigger_id": trigger.trigger_id,
                "priority": trigger.priority,
                "status": "ready_for_planning",
                "execution": {
                    "executed": False,
                    "external_execution": False,
                    "database_mutation": False,
                    "approval_required": False,
                },
            }
            for trigger in matches
        ]
        return {
            "accepted": True,
            "status": "matched" if intents else "accepted_no_match",
            "event": event.canonical(),
            "intents": intents,
        }

    def publish(
        self,
        *,
        organization_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        event_id: str | None = None,
        source: str = "internal",
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        event = self.normalize(
            organization_id=organization_id,
            event_type=event_type,
            payload=payload,
            event_id=event_id,
            source=source,
            correlation_id=correlation_id,
        )
        return self.ingest(event)

    def list_for_organization(self, organization_id: int) -> list[dict[str, Any]]:
        return [
            trigger.canonical()
            for (org_id, _), trigger in self._triggers.items()
            if org_id == int(organization_id)
        ]

    def clear(self) -> None:
        self._triggers.clear()
        self._seen.clear()


# Process-local registry; durable persistence belongs to the workflow/event store layer.
event_trigger_plane = EventTriggerPlane()
