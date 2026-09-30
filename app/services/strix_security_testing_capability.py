"""Governed optional Strix security-testing capability."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class StrixCapabilityAssessment:
    tool_id: str
    capability: str
    status: str
    execution_authority: str
    risk_tier: str
    sandbox_required: bool
    allowed_targets: tuple[str, ...]
    outputs: tuple[str, ...]
    provenance: str
    license: str
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class StrixSecurityTestingCapability:
    VERSION = "1.0"
    TOOL_ID = "strix"
    CAPABILITY_ID = "validated_application_security_testing"
    RISK_TIER = "critical"
    EXECUTION_AUTHORITY = "none"
    SANDBOX_REQUIRED = True
    ALLOWED_TARGETS = ("source_tree", "local_service", "authorized_staging", "authorized_test_target")
    OUTPUTS = (
        "finding",
        "evidence",
        "proof_of_concept",
        "reproduction_steps",
        "remediation_guidance",
        "analysis_report",
    )
    PROVENANCE = "official_usestrix"
    LICENSE = "Apache-2.0"

    @classmethod
    def assess(
        cls,
        *,
        installed: bool = False,
        version: str | None = None,
        target_type: str = "source_tree",
        authorization_confirmed: bool = False,
    ) -> StrixCapabilityAssessment:
        if target_type not in cls.ALLOWED_TARGETS:
            status = "blocked_unsupported_target"
        elif not authorization_confirmed:
            status = "blocked_authorization_required"
        elif installed and version:
            status = "available_for_governed_security_testing"
        else:
            status = "optional_not_installed"
        material = {
            "tool_id": cls.TOOL_ID,
            "capability": cls.CAPABILITY_ID,
            "status": status,
            "execution_authority": cls.EXECUTION_AUTHORITY,
            "risk_tier": cls.RISK_TIER,
            "sandbox_required": cls.SANDBOX_REQUIRED,
            "allowed_targets": cls.ALLOWED_TARGETS,
            "outputs": cls.OUTPUTS,
            "provenance": cls.PROVENANCE,
            "license": cls.LICENSE,
        }
        digest = sha256(repr(sorted(material.items())).encode("utf-8")).hexdigest()
        return StrixCapabilityAssessment(**material, digest=digest)

    @classmethod
    def snapshot(cls) -> dict[str, Any]:
        assessment = cls.assess()
        return {
            "version": cls.VERSION,
            "tool_id": cls.TOOL_ID,
            "assessment": assessment.as_dict(),
            "governance": {
                "capability_id": cls.CAPABILITY_ID,
                "risk_tier": cls.RISK_TIER,
                "sandbox_required": cls.SANDBOX_REQUIRED,
                "optional": True,
                "read_only_to_kemet_runtime": True,
                "no_execution_authority": True,
                "authorization_required": True,
                "authorized_targets_only": True,
                "untrusted_targets_blocked": True,
                "canonical_runtime_required_for_any_consequential_action": True,
                "no_mandatory_runtime_dependency": True,
            },
        }


strix_security_testing_capability = StrixSecurityTestingCapability()
