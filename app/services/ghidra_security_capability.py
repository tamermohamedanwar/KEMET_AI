"""Governed optional Ghidra security-analysis capability."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any


@dataclass(frozen=True)
class GhidraCapabilityAssessment:
    tool_id: str
    capability: str
    status: str
    execution_authority: str
    risk_tier: str
    sandbox_required: bool
    allowed_inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    provenance: str
    license: str
    digest: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class GhidraSecurityCapability:
    VERSION = "1.1"
    TOOL_ID = "ghidra"
    CAPABILITY_ID = "binary_analysis"
    RISK_TIER = "high"
    EXECUTION_AUTHORITY = "none"
    SANDBOX_REQUIRED = True
    ALLOWED_INPUTS = ("binary", "executable", "shared_library", "apk")
    PROVENANCE = "official_nsa_ghidra"
    LICENSE = "Apache-2.0"

    @classmethod
    def assess(cls, *, installed: bool = False, version: str | None = None,
               input_type: str = "binary") -> GhidraCapabilityAssessment:
        allowed_inputs = cls.ALLOWED_INPUTS
        outputs = ("disassembly", "decompilation", "call_graph", "analysis_report", "evidence")
        status = "available_for_governed_analysis" if installed and version else "optional_not_installed"
        if input_type not in allowed_inputs:
            status = "blocked_unsupported_input"
        material = {
            "tool_id": cls.TOOL_ID, "capability": cls.CAPABILITY_ID,
            "status": status, "execution_authority": cls.EXECUTION_AUTHORITY,
            "risk_tier": cls.RISK_TIER, "sandbox_required": cls.SANDBOX_REQUIRED,
            "allowed_inputs": allowed_inputs, "outputs": outputs,
            "provenance": cls.PROVENANCE, "license": cls.LICENSE,
        }
        digest = sha256(repr(sorted(material.items())).encode("utf-8")).hexdigest()
        return GhidraCapabilityAssessment(**material, digest=digest)

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
                "read_only_analysis": True,
                "no_execution_authority": True,
                "sandbox_required_for_untrusted_artifacts": True,
                "canonical_runtime_required_for_consequential_actions": True,
                "no_mandatory_runtime_dependency": True,
            },
        }


ghidra_security_capability = GhidraSecurityCapability()
