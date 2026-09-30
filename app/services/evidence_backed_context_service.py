from __future__ import annotations

import hashlib
import re
from typing import Any

from app.core.evidence.fabric import execution_evidence_fabric
from app.rag.rag_service import rag_service


class EvidenceBackedContextService:
    """Build tenant-scoped context from retrieved evidence without execution authority."""

    VERSION = "1.0"
    MAX_QUERY = 4000
    MAX_RESULTS = 10
    MAX_EXCERPT = 4000
    _SECRET_KEYS = ("token", "secret", "password", "api_key", "authorization", "cookie")
    _INJECTION_PATTERNS = (
        r"ignore\s+(all|any|previous|prior)\s+instructions",
        r"system\s+message",
        r"developer\s+message",
        r"reveal\s+(the\s+)?(system|developer)\s+prompt",
        r"bypass\s+(security|governance|approval)",
        r"disable\s+(safety|security|approval)",
    )

    @classmethod
    def _safe_metadata(cls, value: dict[str, Any] | None) -> dict[str, Any]:
        value = value or {}
        return {
            str(k): v for k, v in value.items()
            if not any(secret in str(k).lower() for secret in cls._SECRET_KEYS)
        }

    @classmethod
    def _content_flags(cls, content: str) -> list[str]:
        lowered = content.lower()
        return ["prompt_injection_signal"] if any(re.search(p, lowered) for p in cls._INJECTION_PATTERNS) else []

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        import json
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def build(self, *, organization_id: int, query: str, task_id: str,
              limit: int = 5, policy: dict[str, Any] | None = None,
              routing: dict[str, Any] | None = None,
              project_context_hash: str | None = None,
              source_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_id_required")
        query = str(query or "").strip()
        task_id = str(task_id or "").strip()
        if not query:
            raise ValueError("query_required")
        if not task_id:
            raise ValueError("task_id_required")
        if len(query) > self.MAX_QUERY:
            raise ValueError("query_too_large")

        safe_limit = max(1, min(int(limit), self.MAX_RESULTS))
        results = rag_service.retriever.search(
            query, limit=safe_limit, organization_id=int(organization_id)
        )
        sources = []
        injection_count = 0
        for filename, index, content in results:
            content = str(content or "")
            flags = self._content_flags(content)
            if flags:
                injection_count += 1
            sources.append({
                "source_type": "document_chunk",
                "filename": str(filename),
                "chunk_index": int(index),
                "excerpt": content[: self.MAX_EXCERPT],
                "content_digest": self._digest({"filename": filename, "chunk_index": index, "content": content}),
                "trust": "untrusted_retrieved_content",
                "flags": flags,
                "usable_for_governance": not bool(flags),
            })

        usable = [item for item in sources if item["usable_for_governance"]]
        package = execution_evidence_fabric.context_package(
            task_id=task_id,
            organization_id=int(organization_id),
            policy=self._safe_metadata(policy),
            routing=self._safe_metadata(routing),
            sources=usable,
            project_context_hash=project_context_hash,
        )
        package["source_metadata"] = self._safe_metadata(source_metadata)
        package["query_digest"] = self._digest({"organization_id": int(organization_id), "query": query})
        package["retrieval"] = {
            "requested": safe_limit,
            "returned": len(sources),
            "usable": len(usable),
            "excluded": len(sources) - len(usable),
            "prompt_injection_signals": injection_count,
            "fallback_retrieval": False,
        }
        package["governance"] = {
            "read_only": True,
            "advisory": True,
            "external_execution": False,
            "database_mutation": False,
            "auto_execute": False,
            "human_approval_required": True,
            "canonical_executor": "kemet",
            "untrusted_content_isolated": True,
        }
        package["digest"] = execution_evidence_fabric.digest({k: v for k, v in package.items() if k != "digest"})
        return package


evidence_backed_context_service = EvidenceBackedContextService()
