from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Iterable


@dataclass(frozen=True)
class CanonicalJob:
    source: str
    source_job_id: str
    title: str
    employer: str
    location: str = ""
    url: str = ""
    description: str = ""
    published_at: str = ""
    evidence_hash: str = ""


class JobSourceGateway:
    """Source-neutral job intake; extraction/publishing remain governed by Kemet Core."""

    VERSION = "1.0"

    def normalize(self, *, source: str, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in records:
            title = str(raw.get("title") or "").strip()
            employer = str(raw.get("employer") or raw.get("company") or "").strip()
            source_id = str(raw.get("source_job_id") or raw.get("id") or "").strip()
            if not title or not source_id:
                continue
            payload = {k: str(v or "").strip() for k, v in raw.items() if k not in {"evidence_hash"}}
            evidence_hash = sha256(repr(sorted(payload.items())).encode()).hexdigest()
            job = CanonicalJob(str(source).strip()[:120], source_id[:200], title[:300], employer[:200],
                               str(raw.get("location") or "").strip()[:200], str(raw.get("url") or "").strip()[:1000],
                               str(raw.get("description") or "").strip()[:10000], str(raw.get("published_at") or "").strip(), evidence_hash)
            normalized.append(asdict(job))
        return normalized

    def deduplicate(self, jobs: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for job in jobs:
            key = f"{job.get('source')}|{job.get('source_job_id')}|{job.get('url')}".lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(dict(job))
        return result

    def intake_preview(self, *, source: str, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
        jobs = self.deduplicate(self.normalize(source=source, records=records))
        return {"success": True, "version": self.VERSION, "status": "preview", "count": len(jobs),
                "jobs": jobs, "published": False, "external_execution": False, "human_review_required": True}


job_source_gateway = JobSourceGateway()
