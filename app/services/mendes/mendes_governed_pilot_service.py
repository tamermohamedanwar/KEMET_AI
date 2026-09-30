from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service
from app.services.mendes.mendes_production_job_service import mendes_production_job_service
from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
from app.services.production_backlot_service import production_backlot_service


class MendesGovernedPilotService:
    VERSION = "1.0"

    def assemble(self, organization_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        pilot = mendes_pilot_episode_service.build(org)
        package = pilot["package"]
        job = mendes_production_job_service.create(
            org,
            package,
            package["voice_contract"],
            package["quality_gates"],
            approval_state="pending",
            workflow_purpose="production",
        )
        readiness = mendes_episode_readiness_service.build(
            organization_id=org,
            job=job,
            package=package,
        )
        backlot = production_backlot_service.snapshot(org, title=package["series"], job=job)
        publication = mendes_publication_contract_service._blocked("publication_approval_required")
        package_view = {
            "world": package["world"],
            "series": package["series"],
            "episode": package["episode"],
            "script": package["script"],
            "scenes": package["scenes"],
            "production": package["production"],
            "quality_gates": readiness["quality_gates"],
            "rights_review": readiness["rights_review"],
            "historical_review": readiness["historical_review"],
            "policy_review": readiness["policy_review"],
            "distribution": readiness["platform_readiness"],
            "measurement": package["outcome"],
        }
        result = {
            "success": True,
            "status": "HUMAN_APPROVAL_REQUIRED",
            "version": self.VERSION,
            "organization_id": org,
            "workflow": [
                "story_bible", "continuity", "script", "production_backlot",
                "quality_rights_policy", "distribution_package", "measurement", "human_approval",
            ],
            "package": package_view,
            "episode_package_digest": package["package_digest"],
            "production_job": job,
            "readiness": readiness,
            "production_backlot": backlot,
            "publication": publication,
            "governance": {
                "human_approval_required": True,
                "external_execution": False,
                "auto_publish": False,
                "execution_authority": False,
                "canonical_runtime_only": True,
                "credentials_exposed": False,
                "mcp": False,
            },
        }
        result["pilot_digest"] = self._digest(result)
        return result

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(raw.encode()).hexdigest()


mendes_governed_pilot_service = MendesGovernedPilotService()
