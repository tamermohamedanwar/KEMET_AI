from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service
from app.services.content_outcome_orchestrator import content_outcome_orchestrator
from app.services.workforce_outcome_learning import workforce_outcome_learning
from app.services.next_episode_learning_service import next_episode_learning_service


class MendesOutcomePilotService:
    VERSION = "1.0"
    SCHEMA = "kemet.mendes_outcome_pilot.v1"
    GOVERNANCE = {
        "tenant_scoped": True,
        "planning_only": True,
        "read_only": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_publish": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "causal_claim": False,
        "synthetic_outcome": False,
        "mcp": False,
        "fail_closed": True,
    }

    def _digest(self, value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def prepare(self, organization_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        pilot = mendes_pilot_episode_service.build(org)
        package = pilot["package"]
        outcome_plan = content_outcome_orchestrator.build_plan(
            organization_id=org,
            episode=package["episode"],
            platforms=package["episode"].get("platforms") or ("youtube", "tiktok", "instagram", "facebook"),
            duration_seconds=90,
            language="ar-EG",
        )
        workforce = workforce_outcome_learning.learning_snapshot(org, period="30d")
        baseline = next_episode_learning_service.build_recommendation(
            organization_id=org,
            episode=package["episode"],
            observed={"metrics": {}},
        )
        packet = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "status": "APPROVAL_READY",
            "prepared_at": datetime.utcnow().isoformat(),
            "episode": {
                "episode_id": package["episode"].get("episode_id"),
                "title": package["episode"].get("title"),
                "series": package.get("series"),
                "world": package.get("world"),
                "classification": package["script"].get("classification"),
                "script_digest": package.get("script_digest"),
                "package_digest": package.get("package_digest"),
            },
            "production": {
                "scene_count": len(package.get("scenes") or []),
                "duration_seconds": 90,
                "quality_gates": package.get("quality_gates", []),
                "voice_contract_digest": (package.get("voice_contract") or {}).get("contract_digest"),
            },
            "distribution": outcome_plan["distribution"],
            "measurement": outcome_plan["measurement"],
            "commercial": outcome_plan["commerce"],
            "learning": {
                "workforce_snapshot_digest": workforce.get("snapshot_digest"),
                "baseline": baseline,
                "observed_outcome": None,
                "qualified_views": None,
                "revenue": None,
                "revenue_per_1000_qualified_views": None,
                "truth_boundary": "No audience, platform, qualified-view, conversion, or revenue outcome is inferred before authoritative measurement.",
            },
            "approval": {
                "required": True,
                "state": "pending",
                "external_publication": "not_requested",
                "approval_binding": ["package_digest", "script_digest", "voice_contract_digest", "quality_gates", "distribution", "measurement"],
            },
            "governance": dict(self.GOVERNANCE),
        }
        packet["packet_digest"] = self._digest(packet)
        return {"success": True, "status": "APPROVAL_READY", "packet": packet,
                "governance": dict(self.GOVERNANCE)}

    def evaluate_authoritative_outcome(self, organization_id: int, packet: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0 or not isinstance(packet, dict) or not isinstance(results, dict):
            return self._blocked("organization_packet_and_results_required")
        if packet.get("organization_id") != org:
            return self._blocked("tenant_mismatch")
        planned = packet.get("episode") or {}
        if not planned.get("package_digest"):
            return self._blocked("package_digest_required")
        evaluated = content_outcome_orchestrator.evaluate_results(
            planned={"content_id": packet["episode"]["package_digest"], "organization_id": org, "story": planned},
            results=results,
        )
        return {"success": True, "status": "OUTCOME_OBSERVED", "organization_id": org,
                "evaluation": evaluated, "execution": False, "governance": dict(self.GOVERNANCE)}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "BLOCKED", "error": error,
                "governance": dict(MendesOutcomePilotService.GOVERNANCE)}


mendes_outcome_pilot_service = MendesOutcomePilotService()
