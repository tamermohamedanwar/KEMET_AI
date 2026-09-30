from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


VALID_RISKS = frozenset({"low", "medium", "high", "critical"})
VALID_STATUSES = frozenset({"proposed", "approved", "published", "retired"})
TRUSTED_PROVENANCE = frozenset({"internal", "verified_vendor", "verified_repository"})


class SkillAdmissionError(PermissionError):
    pass


@dataclass(frozen=True)
class SkillManifest:
    skill_id: str
    version: str
    provenance: str
    owner: str
    domain: str
    triggers: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    allowed_tools: tuple[str, ...] = ()
    risk_level: str = "low"
    approval_policy: str = "auto_safe"
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    security_scan: str = "pending"
    prompt_injection_review: str = "pending"
    sandbox: bool = True
    signed: bool = False
    digest: str = ""
    execution_authority: bool = False
    status: str = "proposed"

    def canonical(self) -> dict[str, Any]:
        payload = asdict(self)
        payload.pop("digest", None)
        payload.pop("execution_authority", None)
        return payload


class SkillAdmissionService:
    VERSION = "1.0"

    @staticmethod
    def digest(manifest: SkillManifest) -> str:
        raw = json.dumps(manifest.canonical(), sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate(self, manifest: SkillManifest) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        for field_name in ("skill_id", "version", "provenance", "owner", "domain"):
            if not str(getattr(manifest, field_name, "")).strip():
                errors.append(f"{field_name}_required")
        if manifest.provenance not in TRUSTED_PROVENANCE:
            errors.append("provenance_not_trusted")
        if manifest.risk_level not in VALID_RISKS:
            errors.append("invalid_risk_level")
        if manifest.status not in VALID_STATUSES:
            errors.append("invalid_status")
        if manifest.execution_authority:
            errors.append("skill_execution_authority_forbidden")
        if any(not str(tool).strip() or tool.strip() == "*" for tool in manifest.allowed_tools):
            errors.append("wildcard_or_empty_tool_permission")
        if manifest.security_scan != "passed":
            errors.append("security_scan_required")
        if manifest.prompt_injection_review != "passed":
            errors.append("prompt_injection_review_required")
        if not manifest.signed:
            errors.append("signed_manifest_required")
        if not manifest.digest:
            errors.append("manifest_digest_required")
        elif manifest.digest != self.digest(manifest):
            errors.append("manifest_digest_mismatch")
        if manifest.provenance != "internal" and not manifest.sandbox:
            errors.append("untrusted_skill_requires_sandbox")
        if manifest.risk_level in {"high", "critical"} and manifest.approval_policy not in {"human", "human_critical", "blocked"}:
            errors.append("high_impact_skill_requires_human_policy")
        if manifest.status == "published" and errors:
            warnings.append("published_skill_invalid_and_must_not_activate")
        return {"valid": not errors, "errors": errors, "warnings": warnings}

    def admit(self, manifest: SkillManifest) -> dict[str, Any]:
        validation = self.validate(manifest)
        if not validation["valid"]:
            raise SkillAdmissionError("skill_admission_denied:" + ",".join(validation["errors"]))
        return {
            "admitted": True,
            "status": "admitted",
            "admission_version": self.VERSION,
            "skill_id": manifest.skill_id,
            "version": manifest.version,
            "digest": manifest.digest,
            "execution_authority": False,
            "validation": validation,
        }


skill_admission_service = SkillAdmissionService()
