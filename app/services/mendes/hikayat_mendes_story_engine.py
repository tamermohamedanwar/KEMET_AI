from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class StoryCharacter:
    character_id: str
    name: str
    role: str
    traits: tuple[str, ...] = ()
    family_id: str | None = None
    status: str = "alive"
    visual_identity: str | None = None
    voice_profile: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "character_id": self.character_id, "name": self.name, "role": self.role,
            "traits": list(self.traits), "family_id": self.family_id, "status": self.status,
            "visual_identity": self.visual_identity, "voice_profile": self.voice_profile,
        }


class HikayatMendesStoryEngine:
    VERSION = "2.1"
    MAX_TEXT = 5000
    ERA_TYPES = ("documented", "inspired", "fictional")
    CANON_STATUSES = ("proposed", "canonical", "retired")
    EVENT_TYPES = ("fact", "relationship", "character_state", "location", "artifact", "mystery", "consequence")
    BEATS = ("hook", "setup", "inciting_incident", "escalation", "reversal", "climax", "cliffhanger")

    def build_universe(self, *, organization_id: int, title: str = "Hikayat Mendes", language: str = "ar-EG") -> dict[str, Any]:
        self._organization(organization_id)
        return {
            "success": True, "engine": "hikayat_mendes_story_universe", "version": self.VERSION,
            "status": "draft", "organization_id": int(organization_id),
            "title": self._text(title, "title_required", 200), "universe_name": "عالم منديس",
            "language": self._text(language, "language_required", 20), "story_bible": self._story_bible(),
            "canon": {"historical_truth": "documented", "inspired_reconstruction": "inspired", "fiction": "fictional"},
            "entities": {"characters": [], "families": [], "locations": [], "artifacts": [], "mysteries": []},
            "timeline": [], "continuity_ledger": [], "narrative_threads": [], "episodes": [], "seasons": [],
            "governance": self._governance(),
        }

    def build_character(self, *, character_id: str, name: str, role: str, traits: list[str] | None = None,
                        family_id: str | None = None, status: str = "alive", visual_identity: str | None = None,
                        voice_profile: str | None = None) -> dict[str, Any]:
        return self._character({"character_id": character_id, "name": name, "role": role,
            "traits": traits or [], "family_id": family_id, "status": status,
            "visual_identity": visual_identity, "voice_profile": voice_profile}).as_dict()

    def plan_episode(self, *, organization_id: int, season_number: int, episode_number: int,
                     title: str, premise: str, era_label: str, era_type: str,
                     characters: list[Mapping[str, Any]] | None = None,
                     continuity_events: list[str] | None = None, cliffhanger: str = "",
                     beats: Mapping[str, str] | None = None, emotional_goal: str = "",
                     thread_ids: list[str] | None = None) -> dict[str, Any]:
        self._organization(organization_id)
        if int(season_number) <= 0 or int(episode_number) <= 0:
            raise ValueError("invalid_episode_number")
        if era_type not in self.ERA_TYPES:
            raise ValueError("invalid_era_type")
        episode_id = f"s{int(season_number)}e{int(episode_number)}"
        normalized_beats = {key: str((beats or {}).get(key) or "").strip()[:1200] for key in self.BEATS}
        normalized_beats["cliffhanger"] = self._text(cliffhanger, "cliffhanger_required", 1200)
        return {
            "success": True, "status": "planned", "organization_id": int(organization_id), "episode_id": episode_id,
            "episode": {"season": int(season_number), "episode": int(episode_number),
                "title": self._text(title, "title_required", 200), "premise": self._text(premise, "premise_required", 2000),
                "era": {"label": self._text(era_label, "era_required", 120), "type": era_type},
                "characters": [dict(item) for item in (characters or []) if isinstance(item, Mapping)],
                "continuity_inputs": [str(x)[:500] for x in (continuity_events or [])],
                "narrative_threads": [str(x)[:160] for x in (thread_ids or [])], "beats": normalized_beats,
                "emotional_goal": str(emotional_goal or "").strip()[:500], "cliffhanger": normalized_beats["cliffhanger"],
                "historical_label_required": True, "originality_required": True, "rights_required": True},
            "continuity_check_required": True, "historical_label_required": True, "governance": self._governance(),
        }

    def record_event(self, *, organization_id: int, event_type: str, description: str,
                     era_label: str, era_type: str, episode_id: str | None = None,
                     entity_ids: list[str] | None = None, canon_status: str = "proposed",
                     before_state: Mapping[str, Any] | None = None, after_state: Mapping[str, Any] | None = None,
                     source_ids: list[str] | None = None) -> dict[str, Any]:
        self._organization(organization_id)
        if event_type not in self.EVENT_TYPES or era_type not in self.ERA_TYPES:
            raise ValueError("invalid_event_type")
        if canon_status not in self.CANON_STATUSES:
            raise ValueError("invalid_canon_status")
        return {"event_id": uuid4().hex, "organization_id": int(organization_id), "event_type": event_type,
            "description": self._text(description, "event_description_required", self.MAX_TEXT),
            "era": {"label": self._text(era_label, "era_required", 120), "type": era_type},
            "episode_id": str(episode_id or "")[:160], "entity_ids": [str(x)[:160] for x in (entity_ids or [])],
            "before_state": dict(before_state or {}), "after_state": dict(after_state or {}),
            "source_ids": [str(x)[:160] for x in (source_ids or [])], "canon_status": canon_status, "immutable": True,
        }

    def continuity_report(self, *, prior_events: list[Mapping[str, Any]], proposed_events: list[Mapping[str, Any]]) -> dict[str, Any]:
        prior = [dict(x) for x in prior_events if isinstance(x, Mapping)]
        proposed = [dict(x) for x in proposed_events if isinstance(x, Mapping)]
        conflicts: list[dict[str, Any]] = []
        seen = {(str(e.get("event_type")), str(e.get("description"))) for e in prior}
        for event in proposed:
            key = (str(event.get("event_type")), str(event.get("description")))
            if key in seen:
                conflicts.append({"type": "duplicate_event", "event": event})
            before = event.get("before_state") or {}
            after = event.get("after_state") or {}
            if before and after and before == after:
                conflicts.append({"type": "no_state_change", "event": event})
        return {"status": "clear" if not conflicts else "review_required", "conflicts": conflicts,
                "prior_event_count": len(prior), "proposed_event_count": len(proposed),
                "checks": {"duplicate_events": True, "state_change": True, "advisory_only": True},
                "advisory_only": True, "governance": self._governance()}

    @staticmethod
    def _story_bible() -> dict[str, Any]:
        return {
            "audience_promise": "emotion_first_historical_storytelling",
            "default_duration_seconds": 90, "target_duration_range": [60, 120],
            "language": "Egyptian Arabic", "visual_identity": "original_consistent_cartoon_world",
            "historical_boundaries": {"documented": "cite_or_trace", "inspired": "label_as_reconstruction", "fictional": "label_as_story"},
            "continuity_rules": ["characters_have_state", "events_have_immutable_ids", "consequences_persist", "unresolved_threads_must_be_tracked"],
            "episode_rules": ["distinct_narrative_value", "strong_hook", "natural_cliffhanger", "no_mass_produced_repetition"],
        }

    @staticmethod
    def _character(payload: Mapping[str, Any]) -> StoryCharacter:
        character_id = str(payload.get("character_id") or "").strip()
        name = str(payload.get("name") or "").strip()
        role = str(payload.get("role") or "").strip()
        if not character_id or not name or not role:
            raise ValueError("character_identity_required")
        status = str(payload.get("status") or "alive").strip().lower()
        if status not in {"alive", "dead", "unknown", "retired"}:
            raise ValueError("invalid_character_status")
        traits = tuple(dict.fromkeys(str(x).strip()[:100] for x in (payload.get("traits") or []) if str(x).strip()))
        return StoryCharacter(character_id=character_id[:160], name=name[:200], role=role[:200], traits=traits,
            family_id=str(payload.get("family_id") or "")[:160] or None, status=status,
            visual_identity=str(payload.get("visual_identity") or "")[:500] or None,
            voice_profile=str(payload.get("voice_profile") or "")[:500] or None)

    @staticmethod
    def _text(value: Any, error: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(error)
        return text[:limit]

    @staticmethod
    def _organization(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "read_only": True, "execution_authority": False,
                "external_execution": False, "database_mutation": False, "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime"}


hikayat_mendes_story_engine = HikayatMendesStoryEngine()
