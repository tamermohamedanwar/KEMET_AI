"""Arabic-first Prompt Intelligence contract and safe prompt-to-plan boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import re
from typing import Any, Mapping


class PromptIntelligenceError(ValueError):
    pass


@dataclass(frozen=True)
class PromptContract:
    prompt_id: str
    version: str
    organization_id: int
    language: str
    title: str
    prompt_text: str
    category: str
    provenance: str
    source_uri: str | None
    rights_status: str
    injection_signals: tuple[str, ...]
    digest: str
    execution_authority: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromptIntelligenceService:
    VERSION = "1.0"
    _INJECTION_PATTERNS = (
        r"ignore\s+(all|previous|prior)\s+instructions",
        r"system\s+message",
        r"developer\s+message",
        r"reveal\s+(the\s+)?(secret|token|password)",
        r"bypass\s+(security|approval|governance)",
        r"disable\s+(guardrails|safety|approval)",
    )

    def _signals(self, text: str) -> tuple[str, ...]:
        lowered = text.lower()
        return tuple(
            sorted({"prompt_injection_signal" for pattern in self._INJECTION_PATTERNS if re.search(pattern, lowered)})
        )

    def create(self, *, organization_id: int, prompt_id: str, title: str,
               prompt_text: str, category: str = "general", language: str = "ar",
               provenance: str = "user", source_uri: str | None = None,
               rights_status: str = "user_supplied") -> PromptContract:
        if int(organization_id) <= 0:
            raise PromptIntelligenceError("organization_required")
        if not str(prompt_id).strip() or not str(title).strip() or not str(prompt_text).strip():
            raise PromptIntelligenceError("prompt_identity_and_text_required")
        if rights_status not in {"user_supplied", "internal", "licensed", "verified_public_domain", "pending_review"}:
            raise PromptIntelligenceError("unsupported_rights_status")
        signals = self._signals(prompt_text)
        material = {
            "version": self.VERSION,
            "prompt_id": prompt_id,
            "organization_id": int(organization_id),
            "language": language,
            "title": title,
            "prompt_text": prompt_text,
            "category": category,
            "provenance": provenance,
            "source_uri": source_uri,
            "rights_status": rights_status,
            "injection_signals": signals,
        }
        digest = sha256(repr(sorted(material.items())).encode("utf-8")).hexdigest()
        return PromptContract(**material, digest=digest)

    def to_plan(self, contract: PromptContract, *, task_type: str = "general") -> dict[str, Any]:
        if contract.injection_signals:
            status = "blocked"
            reason = "prompt_injection_signal_detected"
        elif contract.rights_status == "pending_review":
            status = "blocked"
            reason = "prompt_rights_review_required"
        else:
            status = "proposed"
            reason = None
        return {
            "status": status,
            "reason": reason,
            "prompt_id": contract.prompt_id,
            "prompt_digest": contract.digest,
            "organization_id": contract.organization_id,
            "task_type": task_type,
            "plan": {"intent": contract.prompt_text, "steps": ["understand", "research", "plan", "simulate"]},
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "database_mutation": False,
                "human_approval_required": True,
                "canonical_runtime_only": True,
                "external_prompt_is_data_not_authority": True,
            },
        }


prompt_intelligence_service = PromptIntelligenceService()
