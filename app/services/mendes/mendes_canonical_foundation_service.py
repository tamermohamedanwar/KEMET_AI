"""Canonical World and Character Bible contracts for Hikayat Mendes."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class MendesCanonicalFoundationService:
    VERSION = "1.0"
    WORLD_SCHEMA = "kemet.mendes.world_bible.v1"
    CHARACTER_SCHEMA = "kemet.mendes.character_bible.v1"
    WORLD_STATES = ("DRAFT", "REVIEW", "CANONICAL", "RETIRED")
    RIGHTS_STATES = ("UNKNOWN", "PENDING_REVIEW", "CLEARED", "RESTRICTED", "REJECTED", "EXPIRED")

    def build_world_bible(self, *, organization_id: int, world_id: str, version: int,
                          title: str, fields: Mapping[str, Any] | None = None,
                          status: str = "DRAFT") -> dict[str, Any]:
        self._org(organization_id)
        world_id = self._required(world_id, "world_id_required", 160)
        title = self._required(title, "world_title_required", 240)
        version = self._version(version)
        if status not in self.WORLD_STATES:
            raise ValueError("invalid_world_status")
        data = dict(fields or {})
        world = {
            "schema": self.WORLD_SCHEMA, "version": version,
            "organization_id": int(organization_id), "world_id": world_id,
            "title": title, "status": status,
            "geography": data.get("geography", {}), "history": data.get("history", []),
            "timeline": data.get("timeline", []), "rules": data.get("rules", []),
            "places": data.get("places", []), "cultures": data.get("cultures", []),
            "symbols": data.get("symbols", []), "artifacts": data.get("artifacts", []),
            "language": data.get("language", "ar-EG"), "terminology": data.get("terminology", {}),
            "visual_style": data.get("visual_style", {}), "narrative_style": data.get("narrative_style", {}),
            "values": data.get("values", []), "canon": data.get("canon", []),
            "non_canon": data.get("non_canon", []), "continuity_rules": data.get("continuity_rules", []),
            "prohibited_contradictions": data.get("prohibited_contradictions", []),
            "relationships": data.get("relationships", []), "evidence": data.get("evidence", []),
            "rights": self._rights(data.get("rights")),
            "provenance": data.get("provenance", []),
        }
        world["digest"] = self.digest(world)
        return world

    def build_character_bible(self, *, organization_id: int, world_id: str, character_id: str,
                              version: int, name: str, fields: Mapping[str, Any] | None = None,
                              status: str = "DRAFT") -> dict[str, Any]:
        self._org(organization_id)
        world_id = self._required(world_id, "world_id_required", 160)
        character_id = self._required(character_id, "character_id_required", 160)
        name = self._required(name, "character_name_required", 240)
        version = self._version(version)
        if status not in self.WORLD_STATES:
            raise ValueError("invalid_character_status")
        data = dict(fields or {})
        character = {
            "schema": self.CHARACTER_SCHEMA, "version": version,
            "organization_id": int(organization_id), "world_id": world_id,
            "character_id": character_id, "name": name, "status": status,
            "aliases": data.get("aliases", []), "identity": data.get("identity", {}),
            "visual_identity": data.get("visual_identity", {}), "visual_bible": data.get("visual_bible", {}),
            "personality": data.get("personality", {}), "voice_profile": data.get("voice_profile", {}),
            "backstory": data.get("backstory", ""), "relationships": data.get("relationships", []),
            "abilities": data.get("abilities", []), "limitations": data.get("limitations", []),
            "speech_style": data.get("speech_style", {}), "canonical_facts": data.get("canonical_facts", []),
            "appearances": data.get("appearances", []), "continuity": data.get("continuity", []),
            "rights": self._rights(data.get("rights")), "assets": data.get("assets", []),
            "provenance": data.get("provenance", []), "evidence": data.get("evidence", []),
        }
        character["digest"] = self.digest(character)
        return character

    @staticmethod
    def digest(payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _rights(cls, value: Any) -> dict[str, Any]:
        rights = dict(value or {}) if isinstance(value, Mapping) else {}
        status = str(rights.get("status") or "UNKNOWN").strip().upper()
        if status not in cls.RIGHTS_STATES:
            raise ValueError("invalid_rights_status")
        rights["status"] = status
        rights.setdefault("owner", None)
        rights.setdefault("source", None)
        rights.setdefault("provenance", [])
        rights.setdefault("license", None)
        rights.setdefault("restrictions", [])
        rights.setdefault("commercial_use", False)
        rights.setdefault("territory", None)
        rights.setdefault("duration", None)
        rights.setdefault("attribution", None)
        rights.setdefault("evidence", [])
        return rights

    @staticmethod
    def _required(value: Any, error: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(error)
        return text[:limit]

    @staticmethod
    def _version(value: Any) -> int:
        try:
            version = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_version") from exc
        if version <= 0:
            raise ValueError("invalid_version")
        return version

    @staticmethod
    def _org(value: Any) -> None:
        try:
            organization_id = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("organization_required") from exc
        if organization_id <= 0:
            raise ValueError("organization_required")


mendes_canonical_foundation_service = MendesCanonicalFoundationService()
