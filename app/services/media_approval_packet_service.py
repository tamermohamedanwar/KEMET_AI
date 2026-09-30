from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app import db
from app.models.automation import AutomationApproval
from app.core.approval_package import ApprovalPackage, build_approval_package
from app.core.central_gate_handoff import GateHandoff, create_gate_handoff
from app.core.approval_decision import ApprovalDecision
from app.core.evidence import execution_evidence_fabric
from app.core.plan_context import PlanContext, bind_plan_context
from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import PlannedStep, TaskPlan
from app.core.execution.authorization import execution_authorization


class MediaApprovalPacketService:
    VERSION = "1.0"
    SCHEMA = "kemet.media.approval_packet.v1"
    ACTION = "shortform_candidate_selection"

    def build(
        self,
        *,
        organization_id: int,
        task_id: str,
        transcription: Mapping[str, Any],
        shortform: Mapping[str, Any],
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if not transcription.get("transcript_digest"):
            raise ValueError("transcript_digest_required")
        shortform_plan = shortform.get("plan") if isinstance(shortform.get("plan"), Mapping) else shortform
        if not shortform_plan.get("plan_digest"):
            raise ValueError("shortform_plan_digest_required")
        if int(shortform_plan.get("organization_id") or 0) != org:
            raise ValueError("shortform_tenant_mismatch")
        segments = list(transcription.get("transcript") or [])
        candidates = list(shortform_plan.get("candidates") or [])
        if not segments:
            raise ValueError("timestamped_transcript_required")
        if not candidates:
            raise ValueError("shortform_candidates_required")

        plan = self._plan(org, task_id, shortform)
        context = PlanContext(
            organization_id=org,
            user_id=None,
            metadata={
                "surface": "media_approval",
                "capability": "kemet_native_shortform",
                "transcript_digest": str(transcription["transcript_digest"]),
                "shortform_plan_digest": str(shortform_plan["plan_digest"]),
            },
        )
        binding = bind_plan_context(plan, context)
        assessment = assess_plan_risk(plan)
        evidence = execution_evidence_fabric.context_package(
            task_id=task_id,
            organization_id=org,
            policy={
                "network": "disabled",
                "external_execution": False,
                "human_approval_required": True,
            },
            routing={"executor": "kemet_canonical_runtime", "capability": "kemet_native_shortform"},
            sources=[
                {"type": "transcript", "digest": transcription["transcript_digest"], "segments": len(segments)},
                {"type": "shortform_plan", "digest": shortform_plan["plan_digest"], "candidates": len(candidates)},
            ],
        )
        package = build_approval_package(
            plan,
            binding,
            assessment,
            evidence_context_hash=evidence["digest"],
        )
        packet = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "task_id": task_id,
            "transcription": {
                "status": transcription.get("status"),
                "digest": transcription["transcript_digest"],
                "segment_count": len(segments),
            },
            "shortform": {
                "status": shortform.get("status"),
                "digest": shortform_plan["plan_digest"],
                "candidate_count": len(candidates),
                "selected_candidates": candidates,
            },
            "approval_package": package.as_dict(),
            "evidence_context": evidence,
            "approval": {
                "status": "PENDING_HUMAN_APPROVAL",
                "requested": False,
            },
            "governance": self._governance(),
        }
        packet["packet_digest"] = self._digest(packet)
        return packet

    def request_human_approval(
        self,
        *,
        organization_id: int,
        task_id: str,
        packet: Mapping[str, Any],
        requested_by: int | None = None,
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if int(packet.get("organization_id") or 0) != org:
            raise ValueError("packet_tenant_mismatch")
        package = packet.get("approval_package") or {}
        package_hash = str(package.get("package_hash") or "").strip()
        packet_digest = str(packet.get("packet_digest") or "").strip()
        if not package_hash or not packet_digest:
            raise ValueError("approval_packet_integrity_required")
        existing = (
            AutomationApproval.query
            .filter_by(organization_id=org, action_type=self.ACTION, status="pending")
            .order_by(AutomationApproval.id.desc())
            .all()
        )
        for row in existing:
            try:
                request_data = json.loads(row.request_json or "{}")
            except Exception:
                request_data = {}
            if request_data.get("task_id") == task_id and request_data.get("packet_digest") == packet_digest:
                return self._approval_result(row, package_hash, packet_digest)

        row = AutomationApproval(
            organization_id=org,
            action_type=self.ACTION,
            status="pending",
            reason="Human approval required for transcript-derived shortform candidate selection.",
            request_json=json.dumps({
                "task_id": task_id,
                "packet_digest": packet_digest,
                "approval_package_hash": package_hash,
                "plan_hash": package.get("plan_hash"),
                "candidate_count": (packet.get("shortform") or {}).get("candidate_count", 0),
                "execution_authority": False,
                "external_execution": False,
                "external_publication": False,
                "auto_publish": False,
            }, ensure_ascii=False, default=str),
            requested_by=int(requested_by) if requested_by else None,
        )
        db.session.add(row)
        db.session.commit()
        return self._approval_result(row, package_hash, packet_digest)

    def create_gate_handoff(
        self,
        *,
        packet: Mapping[str, Any],
        decision: ApprovalDecision,
        execution_key: str,
    ) -> GateHandoff:
        if str(packet.get("schema") or "") != self.SCHEMA:
            raise ValueError("approval_packet_schema_required")
        package_data = packet.get("approval_package") or {}
        try:
            package = ApprovalPackage(
                organization_id=int(package_data["organization_id"]),
                plan_hash=str(package_data["plan_hash"]),
                context_fingerprint=str(package_data["context_fingerprint"]),
                risk_level=str(package_data["risk_level"]),
                risk_score=int(package_data["risk_score"]),
                approval_required=bool(package_data["approval_required"]),
                external_side_effects=bool(package_data["external_side_effects"]),
                database_mutation=bool(package_data["database_mutation"]),
                affected_resources=tuple(package_data.get("affected_resources") or ()),
                reasons=tuple(package_data.get("reasons") or ()),
                evidence_requirements=tuple(package_data.get("evidence_requirements") or ()),
                package_hash=str(package_data["package_hash"]),
                evidence_context_hash=str(package_data.get("evidence_context_hash") or ""),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("approval_package_invalid") from exc
        if int(packet.get("organization_id") or 0) != package.organization_id:
            raise ValueError("packet_tenant_mismatch")
        action = self.ACTION
        clean_key = str(execution_key or "").strip()
        if not clean_key:
            raise ValueError("gate_binding_required")
        return create_gate_handoff(
            package,
            decision,
            action=action,
            execution_key=clean_key,
        )

    @staticmethod
    def _plan(org: int, task_id: str, shortform: Mapping[str, Any]) -> TaskPlan:
        shortform_plan = shortform.get("plan") if isinstance(shortform.get("plan"), Mapping) else shortform
        step = PlannedStep(
            step_id="select_candidates",
            objective="Review transcript-derived shortform candidates before any render or publication",
            action=MediaApprovalPacketService.ACTION,
            risk="high",
            requires_approval=True,
            capabilities=frozenset({"content_review", "media_analysis"}),
            parameters={
                "shortform_plan_digest": str(shortform_plan["plan_digest"]),
                "candidate_count": len(shortform_plan.get("candidates") or []),
            },
        )
        payload = {
            "task_id": task_id,
            "organization_id": org,
            "task_type": "media_shortform",
            "risk": "high",
            "steps": [{
                "step_id": step.step_id,
                "objective": step.objective,
                "action": step.action,
                "risk": step.risk,
                "requires_approval": step.requires_approval,
                "depends_on": list(step.depends_on),
                "capabilities": sorted(step.capabilities),
                "parameters": step.parameters,
            }],
        }
        canonical = {
            "task_id": task_id,
            "organization_id": org,
            "task_type": "media_shortform",
            "risk": "high",
            "confidence": 1.0,
            "steps": [{
                "step_id": step.step_id,
                "objective": step.objective,
                "action": step.action,
                "risk": step.risk,
                "requires_approval": step.requires_approval,
                "depends_on": list(step.depends_on),
                "capabilities": sorted(step.capabilities),
                "parameters": step.parameters,
            }],
            "requires_approval": True,
        }
        digest = execution_authorization.plan_hash(canonical)
        return TaskPlan(
            task_id=task_id,
            organization_id=org,
            task_type="media_shortform",
            risk="high",
            confidence=1.0,
            steps=(step,),
            requires_approval=True,
            plan_hash=digest,
        )
    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "human_approval_required": True,
            "execution_authority": False,
            "external_execution": False,
            "external_publication": False,
            "auto_publish": False,
            "network": "disabled",
            "canonical_runtime": "kemet_canonical_runtime",
            "mcp": False,
        }

    @staticmethod
    def _approval_result(row: AutomationApproval, package_hash: str, packet_digest: str) -> dict[str, Any]:
        return {
            "success": True,
            "status": "pending",
            "approval_id": row.id,
            "task_id": json.loads(row.request_json or "{}").get("task_id"),
            "approval_package_hash": package_hash,
            "packet_digest": packet_digest,
            "execution_authority": False,
            "external_execution": False,
            "external_publication": False,
        }

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


media_approval_packet_service = MediaApprovalPacketService()
