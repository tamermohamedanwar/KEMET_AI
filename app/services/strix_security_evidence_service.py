"""Evidence bridge for governed Strix findings."""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Mapping

from app.core.evidence.fabric import execution_evidence_fabric
from app.services.kemet_provenance_lineage_service import kemet_provenance_lineage_service


class StrixSecurityEvidenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.security.strix_finding.v1"
    REQUIRED_FIELDS = ("finding_id", "target_id", "severity", "status")
    ALLOWED_STATUS = ("observed", "reproduced", "remediated", "retest_failed", "retest_passed")
    TRANSITIONS = {
        "observed": ("reproduced", "remediated"),
        "reproduced": ("remediated", "retest_failed", "retest_passed"),
        "remediated": ("retest_failed", "retest_passed"),
        "retest_failed": ("remediated", "retest_passed"),
        "retest_passed": (),
    }

    def validate_transition(self, *, current_status: str, next_status: str) -> bool:
        current = str(current_status or "").strip()
        nxt = str(next_status or "").strip()
        if current not in self.ALLOWED_STATUS or nxt not in self.ALLOWED_STATUS:
            raise ValueError("unsupported_finding_status")
        if nxt not in self.TRANSITIONS[current]:
            raise ValueError("invalid_finding_transition")
        return True

    def build_validation_record(self, *, organization_id: int, trace_id: str,
                                finding_id: str, target_id: str, target_digest: str,
                                current_status: str, next_status: str,
                                validation_evidence: Mapping[str, Any]) -> dict[str, Any]:
        organization_id = int(organization_id or 0)
        if organization_id <= 0:
            raise ValueError("organization_required")
        self.validate_transition(current_status=current_status, next_status=next_status)
        if not str(finding_id or "").strip() or not str(target_id or "").strip():
            raise ValueError("finding_identity_required")
        target_digest = str(target_digest or "").strip()
        if len(target_digest) != 64:
            raise ValueError("target_digest_required")
        evidence = dict(validation_evidence or {})
        if evidence.get("authorized") is not True:
            raise ValueError("validation_authorization_required")
        if int(evidence.get("organization_id") or 0) != organization_id:
            raise ValueError("authorization_tenant_mismatch")
        record = {
            "schema": "kemet.security.strix_validation.v1",
            "version": self.VERSION,
            "organization_id": organization_id,
            "trace_id": str(trace_id),
            "finding_id": str(finding_id),
            "target_id": str(target_id),
            "target_digest": target_digest,
            "from_status": str(current_status),
            "to_status": str(next_status),
            "validation": evidence,
            "governance": {
                "execution_authority": "none",
                "external_targeting": False,
                "human_approval_required_for_consequential_action": True,
            },
        }
        record["digest"] = execution_evidence_fabric.digest(record)
        return record

    def record_finding(self, *, organization_id: int, trace_id: str,
                       finding: Mapping[str, Any], target_digest: str,
                       authorization_evidence: Mapping[str, Any]) -> dict[str, Any]:
        organization_id = int(organization_id or 0)
        if organization_id <= 0:
            raise ValueError("organization_required")
        payload = dict(finding)
        missing = [field for field in self.REQUIRED_FIELDS if not str(payload.get(field) or "").strip()]
        if missing:
            raise ValueError("finding_required_fields_missing")
        if str(payload.get("status")) not in self.ALLOWED_STATUS:
            raise ValueError("unsupported_finding_status")
        target_digest = str(target_digest or "").strip()
        if len(target_digest) != 64:
            raise ValueError("target_digest_required")
        authorization = dict(authorization_evidence or {})
        if authorization.get("authorized") is not True:
            raise ValueError("target_authorization_required")
        if int(authorization.get("organization_id") or 0) != organization_id:
            raise ValueError("authorization_tenant_mismatch")
        evidence = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": organization_id,
            "finding": payload,
            "target": {"digest": target_digest, "id": str(payload["target_id"])},
            "authorization": {
                "authorized": True,
                "organization_id": organization_id,
                "authorization_id": str(authorization.get("authorization_id") or ""),
            },
            "governance": {
                "read_only_to_kemet_runtime": True,
                "execution_authority": "none",
                "external_targeting": False,
                "human_approval_required_for_consequential_action": True,
            },
        }
        evidence["digest"] = execution_evidence_fabric.digest(evidence)
        lineage = kemet_provenance_lineage_service.build_chain(
            organization_id=organization_id,
            trace_id=str(trace_id),
            nodes=[{
                "type": "source",
                "id": str(payload["finding_id"]),
                "organization_id": organization_id,
                "version": 1,
                "digest": sha256(target_digest.encode("utf-8")).hexdigest(),
                "metadata": {"tool": "strix", "evidence_digest": evidence["digest"]},
            }],
        )
        evidence["provenance"] = {"schema": lineage["schema"], "digest": lineage["digest"], "node_count": 1}
        evidence["digest"] = execution_evidence_fabric.digest({k: v for k, v in evidence.items() if k != "digest"})
        return evidence


strix_security_evidence_service = StrixSecurityEvidenceService()
