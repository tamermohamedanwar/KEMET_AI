from __future__ import annotations

import json
from hashlib import sha256
from typing import Any
from urllib.parse import urlparse


class DesignIntelligenceReferenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.design_intelligence_reference.v1"
    SOURCE_KIND = "external_reference"
    ALLOWED_HOSTS = {
        "inspomcp.dev",
        "www.inspomcp.dev",
        "github.com",
        "pair.withgoogle.com",
        "www.w3.org",
    }
    MACROSTRUCTURES = (
        "bento_grid",
        "specimen",
        "manifesto",
        "letter",
        "editorial",
        "dashboard",
        "commerce",
        "landing_page",
        "portfolio",
    )
    GOVERNANCE = {
        "reference_only": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_apply": False,
        "human_review_required": True,
        "canonical_runtime_only": True,
        "tenant_scoped": True,
        "untrusted_external_content": True,
        "mcp_dependency": False,
        "fail_closed": True,
    }

    @staticmethod
    def _digest(value: Any) -> str:
        canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _validate_source(cls, source_url: str) -> bool:
        parsed = urlparse(str(source_url or ""))
        return parsed.scheme == "https" and parsed.hostname in cls.ALLOWED_HOSTS and not parsed.username

    @staticmethod
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, (list, tuple)):
            return []
        return sorted({str(item).strip() for item in value if str(item).strip()})

    def build_reference_evidence(
        self,
        organization_id: int,
        source_url: str,
        title: str,
        evidence_type: str = "screen_reference",
        macrostructure: str | None = None,
        design_tokens: dict[str, Any] | None = None,
        observations: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if not self._validate_source(source_url):
            return self._blocked(org, "untrusted_reference_source")
        macro = str(macrostructure or "").strip().lower() or None
        if macro and macro not in self.MACROSTRUCTURES:
            return self._blocked(org, "unknown_macrostructure")
        evidence = {
            "source_kind": self.SOURCE_KIND,
            "source_url": source_url,
            "title": str(title or "").strip(),
            "evidence_type": str(evidence_type or "screen_reference"),
            "macrostructure": macro,
            "design_tokens": design_tokens or {},
            "observations": self._clean_list(observations),
            "provenance": provenance or {},
            "copy_code": False,
            "derived_from_reference": True,
        }
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "status": "READY_FOR_REVIEW",
            "organization_id": org,
            "evidence": evidence,
            "evidence_digest": self._digest(evidence),
            "governance": dict(self.GOVERNANCE),
        }

    def _blocked(self, organization_id: int, error: str) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "status": "BLOCKED",
            "organization_id": organization_id,
            "error": error,
            "governance": dict(self.GOVERNANCE),
        }

    def build_design_contract(
        self,
        organization_id: int,
        business_objective: str,
        ux_constraints: dict[str, Any] | None = None,
        references: list[dict[str, Any]] | None = None,
        accessibility: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        objective = str(business_objective or "").strip()
        if not objective:
            return self._blocked(org, "business_objective_required")
        refs = references or []
        for ref in refs:
            if not self._validate_source(ref.get("source_url")):
                return self._blocked(org, "untrusted_reference_source")
        constraints = ux_constraints or {}
        accessibility_contract = {
            "standard": "WCAG 2.2",
            "keyboard_access": True,
            "focus_visible": True,
            "semantic_structure": True,
            "contrast_required": True,
            **(accessibility or {}),
        }
        macrostructures = self._clean_list(ref.get("macrostructure") for ref in refs if ref.get("macrostructure"))
        contract = {
            "business_objective": objective,
            "ux_constraints": constraints,
            "reference_evidence": [
                {
                    "source_url": ref.get("source_url"),
                    "title": ref.get("title"),
                    "evidence_digest": ref.get("evidence_digest"),
                    "macrostructure": ref.get("macrostructure"),
                    "observations": self._clean_list(ref.get("observations")),
                }
                for ref in refs
            ],
            "design_intent": {
                "primary_outcome": "task_clarity",
                "interaction_model": "progressive_disclosure",
                "visual_hierarchy": "objective_first",
                "responsive": True,
                "rtl_ready": True,
                "macrostructure_candidates": macrostructures,
            },
            "accessibility": accessibility_contract,
            "implementation_rules": {
                "reference_is_evidence_not_template": True,
                "do_not_copy_third_party_code": True,
                "preserve_kemet_design_language": True,
                "no_external_side_effect": True,
                "human_review_required": True,
            },
        }
        return {
            "schema": "kemet.design_contract.v1",
            "version": "1.0",
            "status": "READY_FOR_REVIEW",
            "organization_id": org,
            "contract": contract,
            "contract_digest": self._digest(contract),
            "governance": dict(self.GOVERNANCE),
        }

    def strategist_preview(
        self,
        organization_id: int,
        business_objective: str,
        ux_constraints: dict[str, Any] | None = None,
        references: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        contract = self.build_design_contract(
            organization_id,
            business_objective,
            ux_constraints=ux_constraints,
            references=references,
        )
        if contract.get("status") == "BLOCKED":
            return contract
        return {
            "schema": "kemet.ai_design_strategist_preview.v1",
            "version": "1.0",
            "status": "REVIEW_REQUIRED",
            "organization_id": organization_id,
            "role": {
                "id": "ai_design_strategist",
                "name": "AI Design Strategist",
                "authority": "advisory_only",
            },
            "input_contract": [
                "business_objective",
                "ux_constraints",
                "design_references",
            ],
            "output_contract": "kemet.design_contract.v1",
            "design_contract": contract,
            "next_step": "kemet_review",
            "execution_authority": False,
            "external_execution": False,
            "mcp": False,
        }


design_intelligence_reference = DesignIntelligenceReferenceService()
