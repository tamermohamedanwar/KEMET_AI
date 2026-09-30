import hashlib
import json
from datetime import datetime, timezone


class MLDatasetAuthorizationService:
    VERSION = "1.0"
    SCHEMA = "kemet.ml.dataset_authorization.v1"
    EXECUTION_AUTHORITY = "none"

    ALLOWED_USES = ("evaluation", "benchmarking", "research")
    SENSITIVITY = ("public", "internal", "confidential", "restricted")
    STATUSES = ("pending_review", "authorized", "revoked", "expired", "rejected")

    @staticmethod
    def _digest(payload):
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def authorize(self, *, organization_id, dataset_id, owner, purpose,
                  allowed_use, sensitivity_classification, source,
                  dataset_sha256, authorization_reference,
                  retention_policy="documented", human_review_status="pending"):
        if not isinstance(organization_id, int) or organization_id <= 0:
            raise ValueError("invalid_organization_id")
        required = {
            "dataset_id": dataset_id, "owner": owner, "purpose": purpose,
            "source": source, "dataset_sha256": dataset_sha256,
            "authorization_reference": authorization_reference,
        }
        if any(not isinstance(v, str) or not v.strip() for v in required.values()):
            raise ValueError("missing_required_authorization_field")
        if allowed_use not in self.ALLOWED_USES:
            raise ValueError("unsupported_allowed_use")
        if sensitivity_classification not in self.SENSITIVITY:
            raise ValueError("unsupported_sensitivity_classification")
        if len(dataset_sha256) != 64:
            raise ValueError("invalid_dataset_digest")
        status = "authorized" if human_review_status == "approved" else "pending_review"
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": organization_id, "dataset_id": dataset_id,
            "owner": owner, "purpose": purpose, "allowed_use": allowed_use,
            "sensitivity_classification": sensitivity_classification,
            "source": source, "dataset_sha256": dataset_sha256,
            "authorization_reference": authorization_reference,
            "retention_policy": retention_policy,
            "human_review_status": human_review_status, "status": status,
            "authorized_at": datetime.now(timezone.utc).isoformat() if status == "authorized" else None,
            "governance": {
                "advisory": True, "read_only": True,
                "execution_authority": self.EXECUTION_AUTHORITY,
                "ml_training_authority": False, "deployment_authority": False,
                "human_review_required": True,
            },
        }
        payload["digest"] = self._digest(payload)
        return payload

    @staticmethod
    def can_enter_evaluation(record, organization_id=None):
        return bool(
            isinstance(record, dict)
            and record.get("status") == "authorized"
            and record.get("human_review_status") == "approved"
            and record.get("organization_id")
            and (organization_id is None or record.get("organization_id") == organization_id)
            and record.get("dataset_sha256")
            and record.get("authorization_reference")
        )
