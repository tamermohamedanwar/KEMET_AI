from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import os
import re
from typing import Any


@dataclass(frozen=True)
class DocumentProvider:
    provider_id: str
    name: str
    executable_env: str
    provenance: str
    license: str
    strengths: tuple[str, ...]


class DocumentIntelligenceService:
    VERSION = "1.0"
    PROVIDERS = (
        DocumentProvider(
            "olmocr", "AI2 olmOCR", "KEMET_OLMOCR_EXECUTABLE", "official_ai2",
            "Apache-2.0", ("pdf", "tables", "equations", "handwriting", "multi_column", "reading_order"),
        ),
    )

    def snapshot(self, organization_id: int | None) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "organization_id": organization_id,
            "providers": [self._provider(p) for p in self.PROVIDERS],
            "governance": self._governance(),
        }

    def plan_pdf(self, *, organization_id: int, input_path: str,
                 sensitivity: str = "internal") -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            return self._blocked("organization_required")
        path = str(input_path or "").strip()
        if not path.lower().endswith(".pdf"):
            return self._blocked("pdf_required")
        if not os.path.isfile(path) or os.path.islink(path):
            return self._blocked("safe_pdf_path_required")
        if sensitivity not in {"public", "internal", "confidential", "restricted"}:
            return self._blocked("invalid_sensitivity")
        provider = self.PROVIDERS[0]
        payload = {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "input_path": path,
            "sensitivity": sensitivity,
            "provider_id": provider.provider_id,
            "provider_configured": bool(os.getenv(provider.executable_env, "").strip()),
            "output": {"format": "markdown", "preserve": list(provider.strengths)},
            "execution": {"automatic": False, "canonical_runtime_only": True},
            "governance": self._governance(),
        }
        payload["plan_digest"] = sha256(repr(sorted(payload.items())).encode()).hexdigest()
        return {"success": True, "status": "planned", "plan": payload}

    @staticmethod
    def chunk_markdown(markdown: str, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
        text = str(markdown or "").strip()
        if not text:
            return []
        blocks = re.split(r"\n(?=#{1,6} |```|\|)", text)
        chunks: list[str] = []
        current = ""
        for block in blocks:
            candidate = f"{current}\n\n{block}".strip() if current else block.strip()
            if current and len(candidate) > chunk_size:
                chunks.append(current)
                tail = current[-overlap:] if overlap else ""
                current = f"{tail}\n\n{block}".strip()
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def quality_profile(markdown: str) -> dict[str, Any]:
        text = str(markdown or "")
        return {
            "characters": len(text),
            "headings": len(re.findall(r"^#{1,6} ", text, re.MULTILINE)),
            "tables": bool(re.search(r"^\|.+\|$", text, re.MULTILINE)),
            "equations": bool(re.search(r"\\\(|\\\[|\$\$|\$[^\n]+\$", text)),
            "images": bool(re.search(r"!\[[^]]*\]\([^)]*\)", text)),
            "markdown_structured": bool(re.search(r"^#{1,6} |^\|", text, re.MULTILINE)),
        }

    @staticmethod
    def _provider(provider: DocumentProvider) -> dict[str, Any]:
        return {
            "provider_id": provider.provider_id,
            "name": provider.name,
            "configured": bool(os.getenv(provider.executable_env, "").strip()),
            "provenance": provider.provenance,
            "license": provider.license,
            "strengths": list(provider.strengths),
            "execution_authority": False,
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "discovery_only": True,
            "untrusted_infrastructure": True,
            "execution_authority": False,
            "human_approval_required": True,
            "canonical_executor": "kemet_canonical_runtime",
            "no_secret_discovery": True,
            "no_automatic_upload": True,
        }

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error, "execution_authority": False}


document_intelligence_service = DocumentIntelligenceService()
