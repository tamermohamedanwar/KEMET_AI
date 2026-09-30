from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class MendesAdaptationLineageService:
    VERSION = "1.0"
    PLATFORMS = ("youtube", "tiktok", "instagram", "facebook", "linkedin")

    def create_source(self, *, organization_id: int, asset_id: str, version: int,
                      digest: str, media_path: str) -> dict[str, Any]:
        self._validate(organization_id, asset_id, version, digest)
        return {
            "schema": "kemet.mendes.source_asset.v1",
            "organization_id": int(organization_id), "asset_id": str(asset_id),
            "version": int(version), "digest": str(digest), "media_path": str(media_path),
        }

    def create_adaptation(self, *, source: Mapping[str, Any], platform: str,
                          adaptation_version: int, payload: Mapping[str, Any]) -> dict[str, Any]:
        platform = str(platform or "").strip().lower()
        if platform not in self.PLATFORMS:
            raise ValueError("unsupported_platform")
        if int(adaptation_version or 0) <= 0:
            raise ValueError("adaptation_version_required")
        self._validate(source.get("organization_id"), source.get("asset_id"),
                       source.get("version"), source.get("digest"))
        adaptation_digest = self._digest({"source_digest": source["digest"],
                                          "platform": platform,
                                          "version": adaptation_version,
                                          "payload": dict(payload)})
        return {
            "schema": "kemet.mendes.adaptation.v1",
            "organization_id": int(source["organization_id"]),
            "source_asset_id": str(source["asset_id"]),
            "source_version": int(source["version"]),
            "source_digest": str(source["digest"]),
            "platform": platform,
            "adaptation_version": int(adaptation_version),
            "adaptation_digest": adaptation_digest,
            "payload": dict(payload),
            "publication_status": "NOT_REQUESTED",
            "external_execution": False,
        }

    def validate_lineage(self, *, source: Mapping[str, Any], adaptation: Mapping[str, Any],
                         organization_id: int) -> dict[str, Any]:
        checks = {
            "tenant": int(source.get("organization_id") or 0) == int(organization_id)
            and int(adaptation.get("organization_id") or 0) == int(organization_id),
            "source_id": str(adaptation.get("source_asset_id")) == str(source.get("asset_id")),
            "source_version": int(adaptation.get("source_version") or 0) == int(source.get("version") or 0),
            "source_digest": str(adaptation.get("source_digest")) == str(source.get("digest")),
            "adaptation_digest": bool(adaptation.get("adaptation_digest")),
            "platform": str(adaptation.get("platform")) in self.PLATFORMS,
            "not_published": adaptation.get("publication_status") == "NOT_REQUESTED",
        }
        return {"valid": all(checks.values()), "checks": checks,
                "external_execution": False, "authority": "none"}

    @staticmethod
    def _validate(organization_id: Any, asset_id: Any, version: Any, digest: Any) -> None:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(asset_id or "").strip():
            raise ValueError("asset_id_required")
        if int(version or 0) <= 0:
            raise ValueError("source_version_required")
        if len(str(digest or "")) != 64:
            raise ValueError("source_digest_required")

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


mendes_adaptation_lineage_service = MendesAdaptationLineageService()
