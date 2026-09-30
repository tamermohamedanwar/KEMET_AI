from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.evidence_backed_context_service import evidence_backed_context_service
from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine
from app.services.next_episode_learning_service import next_episode_learning_service


class MendesEpisodePackageService:
    VERSION = "1.0"

    def build_package(
        self,
        *,
        organization_id: int,
        episode: Mapping[str, Any],
        observed: Mapping[str, Any],
        research_query: str,
        task_id: str,
        season_number: int,
        episode_number: int,
        era_label: str,
        era_type: str,
        characters: list[Mapping[str, Any]] | None = None,
        continuity_events: list[str] | None = None,
        thread_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(episode, Mapping):
            raise ValueError("episode_required")
        if not str(research_query or "").strip():
            raise ValueError("research_query_required")
        if not str(task_id or "").strip():
            raise ValueError("task_id_required")

        learning = next_episode_learning_service.build_recommendation(
            organization_id=int(organization_id), episode=episode, observed=observed
        )
        context = evidence_backed_context_service.build(
            organization_id=int(organization_id),
            query=str(research_query).strip(),
            task_id=str(task_id).strip(),
            limit=5,
            policy={"purpose": "mendes_episode_research", "historical_accuracy": "required"},
            source_metadata={"workflow": "mendes_episode_package", "source_episode": episode.get("episode_id")},
        )
        source_ids = [
            str(item["content_digest"])
            for item in context.get("sources", [])
            if item.get("usable_for_governance")
        ]
        if context.get("retrieval", {}).get("prompt_injection_signals", 0):
            return self._blocked("untrusted_research_content_detected", learning, context)

        next_title = str(learning["next_episode"]["title"])
        planned = hikayat_mendes_story_engine.plan_episode(
            organization_id=int(organization_id),
            season_number=int(season_number),
            episode_number=int(episode_number),
            title=next_title,
            premise=str(episode.get("premise") or next_title),
            era_label=str(era_label),
            era_type=str(era_type),
            characters=characters,
            continuity_events=continuity_events,
            thread_ids=thread_ids,
            beats={"hook": "Open with the strongest verified story question."},
            emotional_goal="Build curiosity and emotional payoff without sacrificing historical labeling.",
            cliffhanger="Leave one clearly tracked narrative question unresolved.",
        )
        package = {
            "success": True,
            "status": "planned",
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "source_episode": episode.get("episode_id") or episode.get("title"),
            "learning": learning,
            "research_context": context,
            "episode_plan": planned,
            "source_ids": source_ids,
            "script_status": "not_generated",
            "approval_status": "not_requested",
            "voice_status": "not_planned",
            "production_status": "not_started",
            "publication_status": "not_submitted",
            "measurement_status": "not_started",
            "governance": {
                "read_only": True,
                "advisory": True,
                "execution_authority": False,
                "external_execution": False,
                "database_mutation": False,
                "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime",
            },
        }
        package["package_digest"] = hashlib.sha256(
            json.dumps(package, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")).encode()
        ).hexdigest()
        return package

    @staticmethod
    def _blocked(error: str, learning: Mapping[str, Any], context: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "learning": dict(learning),
            "research_context": dict(context),
            "execution_authority": False,
            "human_approval_required": True,
        }


mendes_episode_package_service = MendesEpisodePackageService()
