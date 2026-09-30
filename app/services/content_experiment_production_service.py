from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class ContentExperimentProductionService:
    VERSION = "1.0"
    SCHEMA = "kemet.content_experiment_production.v1"

    def build_brief(self, *, experiment: Mapping[str, Any],
                    pilot_package: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(experiment, Mapping) or not experiment.get("experiment_digest"):
            raise ValueError("experiment_required")
        if not isinstance(pilot_package, Mapping) or not pilot_package.get("package_digest"):
            raise ValueError("pilot_package_required")
        org = int(experiment.get("organization_id") or 0)
        if org <= 0 or int(pilot_package.get("organization_id") or 0) != org:
            raise ValueError("tenant_mismatch")
        episode = pilot_package.get("episode") or {}
        scenes = list(pilot_package.get("scenes") or [])
        script = pilot_package.get("script") or {}
        if not episode.get("episode_id") or not scenes or not script.get("title"):
            raise ValueError("production_material_incomplete")
        brief = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": org,
            "experiment_digest": str(experiment["experiment_digest"]),
            "pilot_package_digest": str(pilot_package["package_digest"]),
            "content_id": str(experiment.get("content_id") or episode.get("episode_id")),
            "episode_id": str(episode["episode_id"]),
            "production_brief": {
                "title": str(episode.get("title") or script.get("title")),
                "language": "ar-EG",
                "duration_seconds": 90,
                "format": "short_video",
                "audience": experiment.get("audience"),
                "hook": (experiment.get("creative") or {}).get("hook"),
                "story": (experiment.get("creative") or {}).get("story"),
                "cta": (experiment.get("creative") or {}).get("cta"),
                "telegram_cta": (experiment.get("creative") or {}).get("telegram_cta"),
                "scenes": [
                    {"sequence": i, "description": str(s.get("description") or ""),
                     "dialogue": str(s.get("dialogue") or ""),
                     "duration_seconds": int(s.get("duration_seconds") or 0),
                     "visual_prompt": str(s.get("visual_prompt") or ""),
                     "characters": list(s.get("characters") or [])}
                    for i, s in enumerate(scenes, 1)
                ],
            },
            "rights": {
                "content_classification": script.get("classification"),
                "historical_claim": script.get("historical_claim"),
                "rights_status": script.get("rights_status"),
                "voice_clone": (pilot_package.get("voice_contract") or {}).get("voice_clone"),
                "voice_provider": (pilot_package.get("voice_contract") or {}).get("provider"),
            },
            "gates": {
                "quality": "REVIEW_REQUIRED",
                "rights": "REVIEW_REQUIRED",
                "voice": "REVIEW_REQUIRED",
                "human_approval": "PENDING",
                "publication": "NOT_REQUESTED",
            },
            "execution": {
                "local_artifact_allowed_after_approval": True,
                "external_publication": False,
                "auto_publish": False,
                "execution_authority": False,
            },
            "governance": {
                "read_only": True,
                "human_approval_required": True,
                "canonical_runtime_only": True,
            },
        }
        brief["production_digest"] = self._digest(brief)
        return brief

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


content_experiment_production_service = ContentExperimentProductionService()
