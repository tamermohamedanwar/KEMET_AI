"""Fail-closed assessment contract for untrusted browser/data automation tools."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class ExternalToolAssessment:
    tool_id: str
    version: str
    provenance: str
    source_uri: str | None
    license_status: str
    permissions: tuple[str, ...]
    host_access: tuple[str, ...]
    credential_access: bool
    browser_automation: bool
    external_side_effects: bool
    assessment_status: str
    allowed_capabilities: tuple[str, ...]
    blocked_capabilities: tuple[str, ...]
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExternalToolAssessmentService:
    VERSION = "1.0"
    _LICENSE_OK = {"verified", "vendor_terms_reviewed"}

    def assess(self, *, tool_id: str, provenance: str, source_uri: str | None,
               license_status: str, permissions: tuple[str, ...] = (),
               host_access: tuple[str, ...] = (), credential_access: bool = False,
               browser_automation: bool = False, external_side_effects: bool = False,
               requested_capabilities: tuple[str, ...] = ()) -> ExternalToolAssessment:
        allowed = []
        blocked = []
        for capability in requested_capabilities:
            if capability in {"discovery", "research", "lead_evidence"} and license_status in self._LICENSE_OK:
                allowed.append(capability)
            else:
                blocked.append(capability)
        status = "approved_read_only" if not blocked and license_status in self._LICENSE_OK else "review_required"
        if external_side_effects or credential_access:
            status = "review_required"
        material = {
            "version": self.VERSION, "tool_id": tool_id, "provenance": provenance,
            "source_uri": source_uri, "license_status": license_status,
            "permissions": tuple(sorted(permissions)), "host_access": tuple(sorted(host_access)),
            "credential_access": credential_access, "browser_automation": browser_automation,
            "external_side_effects": external_side_effects,
            "assessment_status": status, "allowed_capabilities": tuple(sorted(allowed)),
            "blocked_capabilities": tuple(sorted(blocked)),
        }
        digest = sha256(repr(sorted(material.items())).encode("utf-8")).hexdigest()
        return ExternalToolAssessment(**material, digest=digest)


external_tool_assessment_service = ExternalToolAssessmentService()
