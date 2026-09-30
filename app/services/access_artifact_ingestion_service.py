from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any


@dataclass(frozen=True)
class AccessArtifact:
    artifact_id: str
    artifact_type: str
    name: str
    source_reference: str
    metadata: dict[str, Any]
    digest: str
    extraction_status: str
    confidence: str
    requires_human_review: bool


class AccessArtifactIngestionService:
    VERSION = "1.1"
    SUPPORTED_EXTENSIONS = {".accdb", ".mdb"}
    ARTIFACT_TYPES = (
        "table", "relationship", "query", "form", "report", "macro", "module",
        "validation_rule", "index", "linked_table",
    )
    REVIEW_TYPES = {"form", "report", "macro", "module"}

    def inspect_source(self, source_path: str, organization_id: int, project_id: str) -> dict[str, Any]:
        path = Path(str(source_path or "")).expanduser()
        project_id = str(project_id or "").strip()
        if organization_id <= 0:
            return self._blocked("organization_required")
        if not project_id:
            return self._blocked("project_required")
        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return self._blocked("access_database_required")
        if not path.is_file() or path.is_symlink():
            return self._blocked("safe_source_copy_required")
        digest = self._file_digest(path)
        stat = path.stat()
        return {
            "success": True, "status": "discovered", "version": self.VERSION,
            "organization_id": organization_id, "project_id": project_id,
            "source": {"path": str(path), "filename": path.name, "extension": path.suffix.lower(),
                       "size": stat.st_size, "sha256": digest,
                       "acquired_at": datetime.now(timezone.utc).isoformat()},
            "extraction": {"method": "not_extracted", "status": "awaiting_verified_extractor"},
            "governance": self._governance(),
        }

    def stage_source(self, source_path: str, organization_id: int, project_id: str,
                     staging_dir: str) -> dict[str, Any]:
        inspected = self.inspect_source(source_path, organization_id, project_id)
        if not inspected["success"]:
            return inspected
        source = Path(inspected["source"]["path"])
        target_dir = Path(staging_dir).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{inspected['source']['sha256'][:16]}_{source.name}"
        shutil.copy2(source, target)
        target.chmod(0o400)
        staged_digest = self._file_digest(target)
        if staged_digest != inspected["source"]["sha256"]:
            target.unlink(missing_ok=True)
            return self._blocked("staged_copy_digest_mismatch")
        return {**inspected, "status": "staged", "working_copy": {"path": str(target),
                "sha256": staged_digest, "read_only": True, "source_modified": False}}

    def ingest_export(self, organization_id: int, project_id: str, source_digest: str,
                      export: dict[str, Any], extraction_method: str) -> dict[str, Any]:
        project_id = str(project_id or "").strip()
        source_digest = str(source_digest or "").strip().lower()
        extraction_method = str(extraction_method or "").strip()
        if organization_id <= 0 or not project_id:
            return self._blocked("tenant_project_identity_required")
        if len(source_digest) != 64 or any(c not in "0123456789abcdef" for c in source_digest):
            return self._blocked("source_digest_required")
        if not extraction_method:
            return self._blocked("extraction_method_required")
        if not isinstance(export, dict):
            return self._blocked("export_object_required")
        objects: list[AccessArtifact] = []
        for artifact_type in self.ARTIFACT_TYPES:
            for item in export.get(artifact_type, []) or []:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                if not name:
                    continue
                metadata = dict(item)
                material = {"type": artifact_type, "name": name, "metadata": metadata}
                digest = self._json_digest(material)
                artifact_id = self._artifact_id(organization_id, project_id, source_digest, artifact_type, name)
                review = artifact_type in self.REVIEW_TYPES
                objects.append(AccessArtifact(artifact_id, artifact_type, name, "access_export",
                    metadata, digest, "extracted", "observed", review))
        counts = {kind: sum(a.artifact_type == kind for a in objects) for kind in self.ARTIFACT_TYPES}
        artifact_digests = [a.digest for a in sorted(objects, key=lambda a: a.artifact_id)]
        system_fingerprint = self._json_digest({"source_digest": source_digest, "counts": counts,
                                                "artifact_digests": artifact_digests})
        review = [{"type": a.artifact_type, "name": a.name,
                   "reason": "behavior_requires_semantic_validation", "blocking": True}
                  for a in objects if a.requires_human_review]
        manifest = {"manifest_version": self.VERSION, "organization_id": organization_id,
                    "project_id": project_id, "source_digest": source_digest,
                    "system_fingerprint": system_fingerprint, "extraction_method": extraction_method,
                    "artifacts": [a.__dict__ for a in objects]}
        return {"success": True, "status": "ingested", "version": self.VERSION,
                "organization_id": organization_id, "project_id": project_id,
                "source_digest": source_digest, "system_fingerprint": system_fingerprint,
                "artifact_counts": counts, "artifacts": manifest["artifacts"],
                "manifest": manifest, "requires_human_review": review,
                "evidence_status": "observed_only", "documents": self._documents(),
                "governance": self._governance()}

    @staticmethod
    def _file_digest(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _json_digest(value: Any) -> str:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
        return sha256(data).hexdigest()

    @staticmethod
    def _artifact_id(organization_id: int, project_id: str, source_digest: str,
                     artifact_type: str, name: str) -> str:
        return "access-artifact-" + AccessArtifactIngestionService._json_digest(
            [organization_id, project_id, source_digest, artifact_type, name])[:24]

    @staticmethod
    def _documents() -> list[str]:
        return ["ACCESS_SYSTEM_ANALYSIS.md", "BUSINESS_LOGIC.md", "MIGRATION_MATRIX.md",
                "DATABASE_MIGRATION_PLAN.md", "REQUIRES_HUMAN_REVIEW.md"]

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"read_only": True, "execution_authority": False, "external_execution": False,
                "database_mutation": False, "human_approval_required": True,
                "canonical_runtime_only": True, "source_data_is_evidence": True,
                "legacy_instructions_are_data": True}

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {"success": False, "status": "blocked", "error": error,
                "execution_authority": False, "source_data_is_evidence": True}


access_artifact_ingestion_service = AccessArtifactIngestionService()
