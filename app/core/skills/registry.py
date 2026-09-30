from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from flask import has_app_context

from app import db
from app.core.skills.admission import SkillAdmissionService, SkillManifest


@dataclass
class SkillRegistry:
    _versions: dict[tuple[str, str], SkillManifest] = field(default_factory=dict)
    _active: dict[str, str] = field(default_factory=dict)
    _approvals: set[tuple[str, str]] = field(default_factory=set)
    admission: SkillAdmissionService = field(default_factory=SkillAdmissionService)

    VERSION = "1.1"

    def _durable(self):
        return has_app_context()

    def _record(self, manifest: SkillManifest):
        from app.models.skill_registry import SkillVersionRecord
        row = SkillVersionRecord.query.filter_by(skill_id=manifest.skill_id, version=manifest.version).first()
        return row

    def _load(self, skill_id: str, version: str | None = None) -> SkillManifest | None:
        from app.models.skill_registry import SkillVersionRecord
        row = None
        if version:
            row = SkillVersionRecord.query.filter_by(skill_id=skill_id, version=version).first()
        else:
            row = SkillVersionRecord.query.filter_by(skill_id=skill_id, active=True).order_by(SkillVersionRecord.id.desc()).first()
        if row is None:
            return None
        try:
            data = json.loads(row.manifest_json)
            return SkillManifest(**data)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def register(self, manifest: SkillManifest) -> dict:
        validation = self.admission.validate(manifest)
        if not validation["valid"]:
            self._audit("skill_validation_failed", manifest, "rejected", {"errors": validation["errors"]})
            return {"registered": False, "errors": validation["errors"]}
        key = (manifest.skill_id, manifest.version)
        if self._durable():
            existing = self._record(manifest)
            if existing is not None:
                if existing.digest != manifest.digest:
                    self._audit("skill_version_conflict", manifest, "rejected")
                    return {"registered": False, "errors": ["skill_version_conflict"]}
                return {"registered": True, "skill_id": manifest.skill_id, "version": manifest.version, "digest": manifest.digest, "idempotent": True}
            row = self._row_from_manifest(manifest)
            db.session.add(row)
            db.session.commit()
        else:
            existing = self._versions.get(key)
            if existing is not None and existing.digest != manifest.digest:
                self._audit("skill_version_conflict", manifest, "rejected")
                return {"registered": False, "errors": ["skill_version_conflict"]}
            self._versions[key] = manifest
        self._audit("skill_registered", manifest, "recorded")
        return {"registered": True, "skill_id": manifest.skill_id, "version": manifest.version, "digest": manifest.digest}

    def _row_from_manifest(self, manifest: SkillManifest):
        from app.models.skill_registry import SkillVersionRecord
        now = datetime.utcnow()
        return SkillVersionRecord(
            skill_id=manifest.skill_id,
            version=manifest.version,
            digest=manifest.digest,
            manifest_json=json.dumps(manifest.canonical() | {"digest": manifest.digest, "execution_authority": False}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            status=manifest.status,
            active=False,
            admission_version=self.admission.VERSION,
            created_at=now,
            updated_at=now,
        )

    def get(self, skill_id: str, version: str | None = None) -> SkillManifest | None:
        if self._durable():
            return self._load(skill_id, version)
        selected = version or self._active.get(skill_id)
        return self._versions.get((skill_id, selected)) if selected else None

    def versions(self, skill_id: str) -> tuple[SkillManifest, ...]:
        if self._durable():
            from app.models.skill_registry import SkillVersionRecord
            rows = SkillVersionRecord.query.filter_by(skill_id=skill_id).order_by(SkillVersionRecord.version.asc()).all()
            result = []
            for row in rows:
                manifest = self._load(skill_id, row.version)
                if manifest is not None:
                    result.append(manifest)
            return tuple(result)
        return tuple(sorted((m for (sid, _), m in self._versions.items() if sid == skill_id), key=lambda m: m.version))

    def approve(self, skill_id: str, version: str, approver: str) -> dict:
        if not str(approver or "").strip():
            return {"approved": False, "error": "approver_required"}
        manifest = self.get(skill_id, version)
        if manifest is None:
            return {"approved": False, "error": "skill_version_not_found"}
        validation = self.admission.validate(manifest)
        if not validation["valid"]:
            self._audit("skill_validation_failed", manifest, "rejected", {"errors": validation["errors"]})
            return {"approved": False, "error": "skill_validation_failed", "validation": validation}
        now = datetime.utcnow()
        if self._durable():
            row = self._record(manifest)
            if row is None:
                return {"approved": False, "error": "skill_version_not_found"}
            if row.status == "retired":
                row.status = "approved"
                row.retired_at = None
            row.approved_by = str(approver)
            row.approved_at = now
            row.updated_at = now
            db.session.commit()
        else:
            self._approvals.add((skill_id, version))
        self._audit("skill_approved", manifest, "recorded", {"approver": str(approver)})
        return {"approved": True, "skill_id": skill_id, "version": version, "approver": str(approver)}

    def publish(self, skill_id: str, version: str) -> dict:
        manifest = self.get(skill_id, version)
        if manifest is None:
            return {"published": False, "error": "skill_version_not_found"}
        validation = self.admission.validate(manifest)
        if not validation["valid"]:
            self._audit("skill_validation_failed", manifest, "rejected", {"errors": validation["errors"]})
            return {"published": False, "error": "skill_validation_failed", "validation": validation}
        if self._durable():
            from app.models.skill_registry import SkillVersionRecord
            row = self._record(manifest)
            if row is None or row.status == "retired" or not row.approved_at:
                return {"published": False, "error": "skill_approval_required"}
            SkillVersionRecord.query.filter_by(skill_id=skill_id, active=True).update({"active": False, "updated_at": datetime.utcnow()})
            row.active = True
            row.status = "published"
            row.published_at = datetime.utcnow()
            row.retired_at = None
            row.updated_at = datetime.utcnow()
            db.session.commit()
        else:
            if (skill_id, version) not in self._approvals:
                return {"published": False, "error": "skill_approval_required"}
            self._active[skill_id] = version
        self._audit("skill_published", manifest, "recorded")
        return {"published": True, "skill_id": skill_id, "version": version, "execution_authority": False}

    def retire(self, skill_id: str, version: str) -> dict:
        manifest = self.get(skill_id, version)
        if self._durable():
            if manifest is None:
                return {"retired": False, "error": "skill_version_not_found"}
            row = self._record(manifest)
            row.active = False
            row.status = "retired"
            row.retired_at = datetime.utcnow()
            row.approved_by = None
            row.approved_at = None
            row.updated_at = datetime.utcnow()
            db.session.commit()
        else:
            if self._active.get(skill_id) == version:
                del self._active[skill_id]
            self._approvals.discard((skill_id, version))
        self._audit("skill_retired", manifest, "recorded")
        return {"retired": True, "skill_id": skill_id, "version": version}

    def health(self) -> dict:
        issues = []
        if self._durable():
            from app.models.skill_registry import SkillVersionRecord
            rows = SkillVersionRecord.query.order_by(SkillVersionRecord.id.asc()).all()
            active = {}
            for row in rows:
                if row.active:
                    active[row.skill_id] = active.get(row.skill_id, 0) + 1
                try:
                    data = json.loads(row.manifest_json)
                    manifest = SkillManifest(**data)
                    validation = self.admission.validate(manifest)
                    if manifest.digest != row.digest or not validation["valid"] or manifest.execution_authority:
                        issues.append({"skill_id": row.skill_id, "version": row.version, "error": "skill_persistence_integrity_failed"})
                except Exception:
                    issues.append({"skill_id": row.skill_id, "version": row.version, "error": "skill_manifest_unreadable"})
            for skill_id, count in active.items():
                if count > 1:
                    issues.append({"skill_id": skill_id, "error": "multiple_active_versions"})
            return {"ok": not issues, "versions": len(rows), "active_skills": len(active), "issues": issues}
        return {"ok": True, "versions": len(self._versions), "active_skills": len(self._active), "issues": []}

    def verify_persistence(self) -> dict:
        return self.health()

    def _audit(self, event_type, manifest, status, metadata=None):
        if not self._durable():
            return
        from app.core.security_events import record_security_event
        record_security_event(
            event_type,
            status=status,
            severity="high" if status == "rejected" else "info",
            action="skill_registry",
            actor_type="system",
            metadata={"skill_id": getattr(manifest, "skill_id", None), "version": getattr(manifest, "version", None), "digest": getattr(manifest, "digest", None), **(metadata or {})},
            commit=True,
        )

    def clear(self) -> None:
        self._versions.clear()
        self._active.clear()
        self._approvals.clear()


skill_registry = SkillRegistry()
