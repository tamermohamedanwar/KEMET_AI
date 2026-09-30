"""Immutable, machine-readable production causal trace for Production Intelligence.

This layer records provenance and evaluation lineage, not model chain-of-thought.
It is advisory/audit infrastructure only and never grants execution authority.
"""
from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping


class ProductionTraceIntegrity:
    SCHEMA = "kemet.production.trace_integrity.v1"
    EVENT_SCHEMA = "kemet.production.trace_event.v1"
    REQUIRED_STAGES = (
        "PLAN", "EVIDENCE", "EVALUATION", "QA", "REPAIR", "REPLAY",
        "PAIRED_EVALUATION", "POLICY_REVIEW", "IMPACT", "LEARNING",
    )

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        return sha256(raw).hexdigest()

    @classmethod
    def _finalize(cls, payload: Mapping[str, Any]) -> dict[str, Any]:
        out = dict(payload)
        out.pop("digest", None)
        out["digest"] = cls._digest(out)
        return out

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "canonical_state_mutation": False,
            "execution_authority": False,
            "external_execution": False,
            "policy_deployment": False,
            "human_approval_required": True,
            "planning_advisory_only": True,
            "mcp": False,
            "chain_of_thought_stored": False,
        }

    @classmethod
    def build(cls, *, organization_id: int, project_id: str,
              correlation_id: str, events: list[Mapping[str, Any]],
              source_digests: list[str] | None = None) -> dict[str, Any]:
        if not project_id or not correlation_id:
            raise ValueError("trace_binding_required")
        if not isinstance(events, list) or not events:
            raise ValueError("trace_events_required")

        normalized: list[dict[str, Any]] = []
        previous = None
        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                raise ValueError("trace_event_invalid")
            stage = str(event.get("stage") or "").upper()
            if stage not in cls.REQUIRED_STAGES:
                raise ValueError("trace_stage_invalid")
            evidence = sorted({str(x) for x in (event.get("evidence_digests") or []) if str(x)})
            if stage in {"EVIDENCE", "EVALUATION", "QA", "REPLAY", "PAIRED_EVALUATION", "IMPACT", "LEARNING"} and not evidence:
                raise ValueError("trace_evidence_required")
            item = {
                "sequence": index,
                "event_id": str(event.get("event_id") or f"{correlation_id}:{index}"),
                "stage": stage,
                "artifact_digest": str(event.get("artifact_digest") or ""),
                "evidence_digests": evidence,
                "decision": str(event.get("decision") or ""),
                "actor_type": str(event.get("actor_type") or "system"),
                "policy_version": str(event.get("policy_version") or ""),
                "approval_digest": str(event.get("approval_digest") or ""),
                "parent_event_digest": previous,
            }
            item["event_digest"] = cls._digest(item)
            previous = item["event_digest"]
            normalized.append(item)

        stages = [x["stage"] for x in normalized]
        if stages != sorted(stages, key=cls.REQUIRED_STAGES.index):
            raise ValueError("trace_stage_order_invalid")
        source = sorted({str(x) for x in (source_digests or []) if str(x)})
        return cls._finalize({
            "schema": cls.SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "correlation_id": str(correlation_id),
            "events": normalized,
            "source_digests": source,
            "terminal_event_digest": normalized[-1]["event_digest"],
            "immutable": True,
            "replayable": True,
            "governance": cls._governance(),
        })

    @classmethod
    def verify(cls, trace: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(trace, Mapping) or trace.get("schema") != cls.SCHEMA:
            raise ValueError("trace_schema_invalid")
        events = trace.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError("trace_events_required")
        previous = None
        for index, item in enumerate(events):
            if item.get("sequence") != index or item.get("parent_event_digest") != previous:
                raise ValueError("trace_chain_invalid")
            body = dict(item)
            digest = body.pop("event_digest", None)
            if digest != cls._digest(body):
                raise ValueError("trace_event_digest_invalid")
            previous = digest
        body = dict(trace)
        digest = body.pop("digest", None)
        if digest != cls._digest(body):
            raise ValueError("trace_digest_invalid")
        if trace.get("terminal_event_digest") != previous:
            raise ValueError("trace_terminal_digest_invalid")
        return {"verified": True, "digest": str(digest), "event_count": len(events), "chain_terminal_digest": previous}


production_trace_integrity = ProductionTraceIntegrity()
