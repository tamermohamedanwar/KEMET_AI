from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
from typing import Any

from .context_gateway import FederationContextGateway


@dataclass(frozen=True)
class ProjectIntelligenceSnapshot:
    version: str
    organization_id: int
    user_id: int
    project_id: str
    current_state: dict[str, Any]
    continuity: dict[str, Any]
    context_hash: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "current_state": self.current_state,
            "continuity": self.continuity,
            "context_hash": self.context_hash,
        }


class ProjectIntelligenceService:
    VERSION = "1.0"
    MAX_CHECKPOINTS = 12

    def __init__(self, gateway: FederationContextGateway | None = None):
        self.gateway = gateway or FederationContextGateway()

    def snapshot(
        self,
        organization_id: int,
        user_id: int,
        *,
        project_id: str = "kemet-ai",
        termux: dict[str, Any] | None = None,
    ) -> ProjectIntelligenceSnapshot:
        context = self.gateway.snapshot(
            organization_id, user_id, project_id=project_id, termux=termux or {}
        )
        continuity = {
            "conversation_count": len(context.conversations),
            "recent_conversations": list(context.conversations[:10]),
            "termux": context.termux,
        }
        state = self._handoff_state()
        payload = {
            "project_id": project_id,
            "current_state": state,
            "continuity": continuity,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        return ProjectIntelligenceSnapshot(
            version=self.VERSION,
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            current_state=state,
            continuity=continuity,
            context_hash=digest,
        )

    @staticmethod
    def _handoff_state() -> dict[str, Any]:
        root = Path(__file__).resolve().parents[3]
        handoff = root / "HANDOFF.md"
        if not handoff.exists():
            return {"available": False, "source": "project_handoff"}
        text = handoff.read_text(encoding="utf-8", errors="replace")
        headings = re.findall(r"^## Checkpoint — (.+)$", text, re.MULTILINE)
        gap_match = re.search(r"## Recovered Gap Register.*?(?=\n## |\Z)", text, re.DOTALL)
        gaps = []
        if gap_match:
            gaps = [
                line[2:].strip()
                for line in gap_match.group(0).splitlines()
                if line.startswith("- ")
            ][:20]
        return {
            "available": True,
            "source": "project_handoff",
            "checkpoint_count": len(headings),
            "latest_checkpoints": headings[-ProjectIntelligenceService.MAX_CHECKPOINTS :],
            "recovered_gaps": gaps,
        }


project_intelligence = ProjectIntelligenceService()
