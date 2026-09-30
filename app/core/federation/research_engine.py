from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from typing import Any, Callable, Iterable

from app.core.federation.untrusted_content import quarantine, safe_research_metadata


class ResearchEngineError(ValueError):
    pass


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    locator: str
    title: str | None
    content: str
    confidence: float = 0.0
    metadata: dict[str, Any] | None = None


class ResearchEngine:
    VERSION = "2.0"
    MAX_QUESTION = 2000
    MAX_SOURCES = 12
    MAX_CLAIMS_PER_SOURCE = 8
    MAX_CLAIM_LENGTH = 420

    SOURCE_HINTS = {
        "reddit": ("reddit", "community", "customer voice", "reviews", "sentiment"),
        "youtube": ("youtube", "video", "creator", "tutorial"),
        "github": ("github", "repository", "repo", "developer", "code"),
        "twitter": ("twitter", "x", "social", "trend"),
        "web_search": ("research", "market", "competitor", "trend", "news", "compare"),
    }

    POSITIVE = {"increase", "increased", "up", "growth", "grow", "higher", "gain", "gained", "rise", "rising", "improve", "improved", "positive"}
    NEGATIVE = {"decrease", "decreased", "down", "decline", "declined", "lower", "loss", "lost", "fall", "falling", "negative", "risk"}

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    @classmethod
    def _digest(cls, value: Any) -> str:
        return sha256(cls._canonical(value).encode("utf-8")).hexdigest()

    @staticmethod
    def _clean(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()

    @classmethod
    def _content_hash(cls, content: str) -> str:
        return sha256(content.encode("utf-8", errors="replace")).hexdigest()

    def plan(self, question: str, sources: Iterable[str] | None = None) -> dict[str, Any]:
        question = self._clean(question)
        if not question:
            raise ResearchEngineError("research_question_required")
        if len(question) > self.MAX_QUESTION:
            raise ResearchEngineError("research_question_too_long")
        requested = [self._clean(x).lower() for x in (sources or []) if self._clean(x)]
        requested = list(dict.fromkeys(requested))
        invalid = [x for x in requested if x not in self.SOURCE_HINTS and x not in {"web"}]
        if invalid:
            raise ResearchEngineError("unsupported_research_source")
        if not requested:
            lowered = question.lower()
            scored = sorted(
                ((sum(token in lowered for token in hints), source_id) for source_id, hints in self.SOURCE_HINTS.items()),
                reverse=True,
            )
            requested = [source_id for score, source_id in scored if score > 0][:4]
            if not requested:
                requested = ["web_search", "reddit"]
        requested = requested[: self.MAX_SOURCES]
        return {
            "version": self.VERSION,
            "question": question,
            "sources": requested,
            "source_count": len(requested),
            "strategy": "multi_source_rank_deduplicate_claims_corroborate",
        }

    def _normalize_source(self, source: ResearchSource | dict[str, Any]) -> ResearchSource:
        if isinstance(source, ResearchSource):
            item = source
        else:
            item = ResearchSource(
                source_id=self._clean(source.get("source_id")),
                locator=self._clean(source.get("locator") or source.get("url")),
                title=self._clean(source.get("title")) or None,
                content=self._clean(source.get("content")),
                confidence=max(0.0, min(1.0, float(source.get("confidence", 0.0)))),
                metadata=source.get("metadata") if isinstance(source.get("metadata"), dict) else {},
            )
        if not item.source_id or not item.locator or not item.content:
            raise ResearchEngineError("invalid_research_source")
        quarantined = quarantine(item.content, source_id=item.source_id)
        metadata = dict(item.metadata or {})
        metadata.update(safe_research_metadata(quarantined))
        return ResearchSource(
            source_id=item.source_id,
            locator=item.locator,
            title=item.title,
            content=quarantined.content,
            confidence=item.confidence,
            metadata=metadata,
        )

    def normalize(self, sources: Iterable[ResearchSource | dict[str, Any]]) -> list[ResearchSource]:
        unique: dict[str, ResearchSource] = {}
        for raw in list(sources or [])[: self.MAX_SOURCES]:
            item = self._normalize_source(raw)
            key = self._content_hash(item.content)
            if key not in unique:
                unique[key] = item
        return list(unique.values())

    def _sentences(self, content: str) -> list[str]:
        chunks = re.split(r"(?<=[.!?。！？])\s+|\n+", content)
        result = []
        for chunk in chunks:
            value = self._clean(chunk)
            if len(value) < 30:
                continue
            result.append(value[: self.MAX_CLAIM_LENGTH])
            if len(result) >= self.MAX_CLAIMS_PER_SOURCE:
                break
        return result

    def extract_claims(self, source: ResearchSource) -> list[dict[str, Any]]:
        claims = []
        for index, text in enumerate(self._sentences(source.content), start=1):
            claims.append({
                "claim_id": self._digest({"source": source.locator, "index": index, "text": text})[:24],
                "text": text,
                "source_id": source.source_id,
                "locator": source.locator,
                "source_title": source.title,
                "confidence": round(source.confidence, 4),
                "content_hash": self._content_hash(source.content),
                "transformation": "sentence_extraction",
            })
        return claims

    @staticmethod
    def _claim_key(text: str) -> str:
        value = re.sub(r"[^a-z0-9% ]+", " ", text.lower())
        stop = {"the", "a", "an", "and", "or", "of", "to", "in", "for", "is", "are", "was", "were", "that"}
        direction = ResearchEngine.POSITIVE | ResearchEngine.NEGATIVE
        return " ".join(x for x in value.split() if x not in stop and x not in direction)[:240]

    def _polarity(self, text: str) -> int:
        words = set(re.findall(r"[a-z]+", text.lower()))
        positive = len(words & self.POSITIVE)
        negative = len(words & self.NEGATIVE)
        return 1 if positive > negative else -1 if negative > positive else 0

    def corroborate(self, claims: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            groups.setdefault(self._claim_key(claim["text"]), []).append(claim)
        corroborated = []
        contradictions = []
        for key, group in groups.items():
            if not key:
                continue
            source_ids = sorted({item["source_id"] for item in group})
            polarities = {self._polarity(item["text"]) for item in group}
            if len(source_ids) > 1 and len(polarities - {0}) == 1:
                corroborated.append({
                    "claim_key": key,
                    "source_count": len(source_ids),
                    "sources": source_ids,
                    "confidence": round(sum(item["confidence"] for item in group) / len(group), 4),
                    "status": "corroborated",
                })
            elif len(source_ids) > 1 and 1 in polarities and -1 in polarities:
                contradictions.append({
                    "claim_key": key,
                    "source_count": len(source_ids),
                    "sources": source_ids,
                    "status": "review_required",
                    "reason": "conflicting_polarity",
                })
        return {"corroborated": corroborated, "contradictions": contradictions}

    def rank_sources(self, sources: list[ResearchSource]) -> list[ResearchSource]:
        return sorted(sources, key=lambda x: (x.confidence, x.source_id, x.locator), reverse=True)

    def evidence_package(
        self,
        *,
        task_id: str,
        organization_id: int,
        question: str,
        plan: dict[str, Any],
        sources: list[ResearchSource],
        claims: list[dict[str, Any]],
        corroboration: dict[str, Any],
        policy_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        source_records = []
        for source in self.rank_sources(sources):
            source_records.append({
                "source_id": source.source_id,
                "locator": source.locator,
                "title": source.title,
                "confidence": round(source.confidence, 4),
                "content_hash": self._content_hash(source.content),
                "metadata": source.metadata or {},
                "trust": (source.metadata or {}).get("trust", "external_untrusted"),
                "execution_authority": False,
            })
        suspicious_sources = sum(
            bool((source.metadata or {}).get("instruction_attack_detected"))
            for source in sources
        )
        package = {
            "version": self.VERSION,
            "type": "research_evidence_package",
            "task_id": task_id,
            "organization_id": int(organization_id),
            "question": self._clean(question),
            "plan": plan,
            "policy_fingerprint": policy_fingerprint,
            "sources": source_records,
            "claims": claims,
            "corroboration": corroboration["corroborated"],
            "contradictions": corroboration["contradictions"],
            "governance": {
                "read_only": True,
                "untrusted_content_review_required": suspicious_sources > 0,
                "suspicious_source_count": suspicious_sources,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "citation_required": True,
            },
        }
        return {**package, "digest": self._digest(package)}

    def run(
        self,
        question: str,
        *,
        task_id: str,
        organization_id: int,
        sources: Iterable[ResearchSource | dict[str, Any]] | None = None,
        source_reader: Callable[[str, str], ResearchSource | dict[str, Any]] | None = None,
        source_ids: Iterable[str] | None = None,
        policy_fingerprint: str | None = None,
    ) -> dict[str, Any]:
        plan = self.plan(question, source_ids)
        resolved = list(sources or [])
        errors = []
        if source_reader:
            for source_id in plan["sources"]:
                try:
                    resolved.append(source_reader(source_id, plan["question"]))
                except Exception as exc:
                    errors.append({"source_id": source_id, "error": str(exc), "retryable": False})
        normalized = self.normalize(resolved)
        claims = []
        for source in normalized:
            claims.extend(self.extract_claims(source))
        corroboration = self.corroborate(claims)
        package = self.evidence_package(
            task_id=task_id, organization_id=organization_id, question=question,
            plan=plan, sources=normalized, claims=claims,
            corroboration=corroboration, policy_fingerprint=policy_fingerprint,
        )
        return {
            "engine": "kemet_research_engine",
            "version": self.VERSION,
            "status": "ok" if normalized else "no_evidence",
            "plan": plan,
            "sources": package["sources"],
            "claims": claims,
            "corroboration": corroboration["corroborated"],
            "contradictions": corroboration["contradictions"],
            "errors": errors,
            "evidence_package": package,
            "governance": package["governance"],
        }


    def synthesize(self, result: dict[str, Any]) -> dict[str, Any]:
        claims = list(result.get("claims") or [])
        corroborated = list(result.get("corroboration") or [])
        contradictions = list(result.get("contradictions") or [])
        sources = list(result.get("sources") or [])
        suspicious_sources = sum(
            bool((item.get("metadata") or {}).get("instruction_attack_detected"))
            for item in sources
        )
        confidence = 0.0
        if claims:
            confidence = sum(float(item.get("confidence", 0.0)) for item in claims) / len(claims)
        if corroborated:
            confidence = min(1.0, confidence + min(0.15, 0.03 * len(corroborated)))
        if contradictions:
            confidence = max(0.0, confidence - min(0.25, 0.08 * len(contradictions)))
        if not sources:
            status = "insufficient_evidence"
        elif contradictions or suspicious_sources:
            status = "review_required"
        elif corroborated:
            status = "evidence_supported"
        else:
            status = "evidence_available"
        return {
            "status": status,
            "confidence": round(confidence, 4),
            "source_count": len(sources),
            "claim_count": len(claims),
            "corroborated_count": len(corroborated),
            "contradiction_count": len(contradictions),
            "suspicious_source_count": suspicious_sources,
            "decision_readiness": "review" if contradictions or suspicious_sources or not sources else "ready_for_business_review",
            "recommendation_policy": "Do not treat unsupported or contradictory claims as facts.",
        }

research_engine = ResearchEngine()
