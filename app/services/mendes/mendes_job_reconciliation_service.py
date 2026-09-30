from __future__ import annotations

from typing import Any

from app.models.mendes_production_job import MendesProductionJobRecord, MendesProductionJobTransition


class MendesJobReconciliationService:
    VERSION = "1.0"

    def report(self, organization_id: int, episode_package_digest: str) -> dict[str, Any]:
        rows = MendesProductionJobRecord.query.filter_by(
            organization_id=int(organization_id), episode_package_digest=str(episode_package_digest)
        ).order_by(MendesProductionJobRecord.created_at.asc()).all()
        jobs = []
        for row in rows:
            transitions = MendesProductionJobTransition.query.filter_by(
                organization_id=int(organization_id), job_id=row.job_id
            ).count()
            purpose = "readiness" if ":readiness-" in row.idempotency_key or "-readiness-" in row.idempotency_key else "production"
            jobs.append({
                "job_id": row.job_id,
                "idempotency_key": row.idempotency_key,
                "workflow_purpose": purpose,
                "state": row.state,
                "approval_state": row.approval_state,
                "transition_count": transitions,
                "job_digest": row.job_digest,
            })
        production = [j for j in jobs if j["workflow_purpose"] == "production"]
        readiness = [j for j in jobs if j["workflow_purpose"] == "readiness"]
        true_duplicates = len(production) > 1
        if true_duplicates:
            status = "DUPLICATE_DETECTED"
            reason = "multiple production-purpose jobs share the same tenant and package digest"
            canonical = production[0]
            duplicate = production[1:]
            action = "REVIEW_REQUIRED_NO_DELETE"
        elif readiness and production:
            status = "WORKFLOW_SCOPE_COLLISION_HISTORY"
            reason = "readiness and production workflows were both persisted in the production-job table with distinct idempotency keys"
            canonical = production[0]
            duplicate = readiness
            action = "PRESERVE_HISTORY_AND_PREVENT_NEW_READINESS_JOB_CREATION"
        else:
            status = "NO_DUPLICATE"
            reason = "no multiple production-purpose jobs detected"
            canonical = production[0] if production else None
            duplicate = []
            action = "NONE"
        return {
            "version": self.VERSION,
            "status": status,
            "organization_id": int(organization_id),
            "episode_package_digest": str(episode_package_digest),
            "reason": reason,
            "canonical_job": canonical,
            "duplicate_jobs": duplicate,
            "references": {"job_count": len(jobs), "transition_rows_checked": True},
            "safe_action": action,
            "residual_risk": "historical readiness record remains until an explicit evidence-preserving migration is justified" if readiness else None,
            "jobs": jobs,
        }


mendes_job_reconciliation_service = MendesJobReconciliationService()
