from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from app.services.content_approval_packet_service import content_approval_packet_service
from app.services.content_experiment_production_service import content_experiment_production_service
from app.services.content_experiment_service import content_experiment_service
from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service
from app.services.mendes.mendes_production_job_store import mendes_production_job_store
from app.services.mendes.mendes_controlled_production_service import mendes_controlled_production_service
from app.services.social_publication_readiness_service import social_publication_readiness_service
from app.services.social_channel_readiness_service import social_channel_readiness_service
from app.services.voice_provider_decision_service import voice_provider_decision_service


class FinalContentApprovalService:
    VERSION = "1.1"
    SCHEMA = "kemet.content.final_approval.v1"

    def build(self, *, organization_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        record = self._latest_verified_record(org)
        if record is None:
            return self._blocked("verified_production_required", status="not_ready")
        try:
            package = mendes_pilot_episode_service.build(org)["package"]
            experiment = self._experiment(org)
            brief = content_experiment_production_service.build_brief(
                experiment=experiment, pilot_package=package
            )
            job = mendes_production_job_store.get(org, record.job_id)
            artifact, verification = self._artifact_evidence(package, job)
            readiness_job = self._readiness_view(job, package, artifact)
            readiness = mendes_episode_readiness_service.build(
                organization_id=org, job=readiness_job, package=package
            )
            production_result = {
                "organization_id": org,
                "artifact": artifact,
                "verification": verification,
                "readiness": readiness,
            }
            packet = content_approval_packet_service.build(
                organization_id=org,
                experiment=experiment,
                production_brief=brief,
                production_result=production_result,
            )
            voice_decision = voice_provider_decision_service.build(organization_id=org, readiness=readiness)
            preflight = self._publication_preflight(org, readiness, packet)
            return {
                "success": True,
                "status": "REVIEW_REQUIRED",
                "schema": self.SCHEMA,
                "version": self.VERSION,
                "approval_packet": packet,
                "publication_preflight": preflight,
                "voice_provider_decision": voice_decision,
                "source": {
                    "job_id": job.get("job_id"),
                    "job_state": job.get("state"),
                    "job_digest": job.get("job_digest"),
                    "derived_readiness": True,
                },
                "governance": {
                    "read_only": True,
                    "human_approval_required": True,
                    "execution_authority": False,
                    "external_publication": False,
                    "auto_publish": False,
                    "canonical_runtime_only": True,
                    "mcp": False,
                },
                "truth_boundary": "Final approval packet is a read-only reconstruction from verified local evidence; it does not grant approval or execute publication.",
            }
        except ValueError as exc:
            return self._blocked(str(exc))
        except Exception:
            return self._blocked("final_approval_unavailable", status="unavailable")

    @staticmethod
    def _latest_verified_record(org: int):
        from app.models.mendes_production_job import MendesProductionJobRecord
        return (MendesProductionJobRecord.query
                .filter_by(organization_id=org, state="VERIFIED")
                .order_by(MendesProductionJobRecord.id.desc()).first())

    @staticmethod
    def _experiment(org: int) -> dict[str, Any]:
        return content_experiment_service.build(
            organization_id=org,
            content_id="mendes-001",
            title="الخاتم الأزرق",
            audience="Egyptian Arabic short-form story viewers",
            hook="يونس يلتقط خاتمًا أزرق من بين حجارة قديمة في لحظة كان يجب أن يمر فيها المكان بلا مفاجآت.",
            story="شاب من عائلة منديس يجد خاتمًا غامضًا يفتح سرًا أكبر من حياته.",
            cta="تابع الحكاية واكتشف ما وراء العلامة.",
            telegram_cta="كمل الحكاية على Telegram وصوّت للخطوة التالية.",
        )

    @staticmethod
    def _readiness_view(job: Mapping[str, Any], package: Mapping[str, Any], artifact: Mapping[str, Any]) -> dict[str, Any]:
        view = dict(job)
        if str(job.get("script_digest") or "") != str(package.get("script_digest") or ""):
            raise ValueError("verified_job_script_binding_mismatch")
        bound_package_digest = str(artifact.get("package_digest") or "").strip()
        if not bound_package_digest or bound_package_digest != str(package.get("package_digest") or ""):
            raise ValueError("verified_artifact_package_binding_mismatch")
        view["episode_package_digest"] = bound_package_digest
        view["voice_contract_digest"] = (package.get("voice_contract") or {}).get("contract_digest")
        view["state"] = "PLANNED"
        view["approval_state"] = "pending"
        view["workflow_purpose"] = "readiness"
        return view

    @staticmethod
    def _artifact_evidence(package: Mapping[str, Any], job: Mapping[str, Any]):
        refs = list(job.get("asset_refs") or [])
        if not refs:
            raise ValueError("artifact_reference_required")
        ref = refs[0]
        artifact = {
            "artifact_kind": ref.get("kind"),
            "artifact_path": ref.get("uri"),
            "artifact_digest": ref.get("sha256"),
            "package_digest": ref.get("package_digest"),
            "artifact_ref": ref,
            "duration_seconds": ref.get("duration_seconds"),
        }
        artifact_path = Path(str(artifact.get("artifact_path") or ""))
        manifest_path = artifact_path.with_name(f"{artifact_path.stem}_manifest.json")
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifact["package_digest"] = manifest.get("episode_package_digest")
            except (OSError, ValueError, TypeError):
                pass
        verification = mendes_controlled_production_service._verify_artifact(
            artifact, dict(package), str(package.get("package_digest"))
        )
        if not verification.get("verified"):
            raise ValueError("artifact_verification_required")
        return artifact, verification

    @staticmethod
    def _publication_preflight(org: int, readiness: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
        from app.models.provider_connection import ProviderConnectionRecord

        platform_section = readiness.get("platform_readiness") or {}
        selected = list(platform_section.get("platforms") or [])
        records = platform_section.get("records") or {}
        required_platforms = {"youtube"}
        optional_platforms = set(selected) - {"youtube"}
        connection_rows = ProviderConnectionRecord.query.filter(
            ProviderConnectionRecord.organization_id == org,
            ProviderConnectionRecord.provider_id.in_([f"social:{p}" for p in selected]),
        ).all()
        connections = {row.provider_id: row for row in connection_rows}
        checks: dict[str, Any] = {}
        blockers: list[str] = []
        connection_evidence: dict[str, Any] = {}

        for platform in selected:
            record = records.get(platform) or {}
            row = connections.get(f"social:{platform}")
            metadata = dict(platform_section.get("metadata") or {})
            if platform == "tiktok":
                metadata = {"title": metadata.get("title"), "privacy_level": "SELF_ONLY", "is_aigc": True}
            elif platform == "youtube":
                metadata = {"title": metadata.get("title"), "description": metadata.get("long_description"), "audience": "not_made_for_kids"}
            else:
                metadata = {"caption": metadata.get("long_description")}

            connected = bool(row and row.status == "verified" and row.provider_account_ref and row.credential_ref)
            publishing_authorized = bool(row and isinstance(row.metadata_json, dict) and row.metadata_json.get("publishing_capable") is True)
            api_audited = bool(row and isinstance(row.metadata_json, dict) and row.metadata_json.get("api_audited") is True)

            result = social_publication_readiness_service.evaluate(
                organization_id=org,
                platform=platform,
                metadata=metadata,
                connected=connected,
                publishing_authorized=publishing_authorized,
                api_audited=api_audited,
                human_approval=False,
            )
            reason = result.get("error")
            checks[platform] = {
                "ready": bool(result.get("ready")),
                "status": result.get("status"),
                "reason": reason,
                "metadata_ready": bool(record.get("metadata_ready")),
                "publishing_authority": "VERIFIED" if publishing_authorized else "NOT_VERIFIED",
                "api_audited": api_audited,
                "publication_status": record.get("publication_status"),
            }
            connection_evidence[platform] = {
                "record_present": row is not None,
                "status": row.status if row else None,
                "account_ref_present": bool(row and row.provider_account_ref),
                "credential_ref_present": bool(row and row.credential_ref),
                "publishing_capable": publishing_authorized,
                "api_audited": api_audited,
            }
            if not result.get("ready") and platform in required_platforms:
                blockers.append(f"{platform}:{reason}")

        telegram_snapshot = social_channel_readiness_service.snapshot(org)
        telegram = next((item for item in telegram_snapshot.get("channels", []) if item.get("channel_id") == "telegram"), {})
        telegram_ready = bool(telegram.get("configured"))
        if not telegram_ready:
            blockers.append("telegram:configuration_required")

        voice = packet.get("evidence", {}).get("voice", {})
        budget = packet.get("evidence", {}).get("budget", {})
        if voice.get("provider_selected") is not True:
            blockers.append("voice:provider_selection_required")
        if not budget.get("verified_cost"):
            blockers.append("budget:verified_cost_required")

        blockers = sorted(set(blockers))
        next_actions = []
        if not voice.get("provider_selected"):
            next_actions.append("select_voice_provider")
        if not budget.get("verified_cost"):
            next_actions.append("capture_verified_cost")
        for platform in selected:
            if platform in required_platforms and any(item.startswith(f"{platform}:") for item in blockers):
                next_actions.append(f"connect_and_verify:{platform}")
        if not telegram_ready:
            next_actions.append("configure_telegram")
        return {
            "status": "BLOCKED" if blockers else "READY_FOR_HUMAN_APPROVAL",
            "ready": False if blockers else True,
            "platforms": checks,
            "required_platforms": sorted(required_platforms),
            "optional_platforms": sorted(optional_platforms),
            "telegram": {
                "ready": telegram_ready,
                "configuration": telegram.get("configuration"),
                "missing_configuration": list(telegram.get("missing_configuration") or []),
                "credentials_exposed": False,
            },
            "next_actions": sorted(set(next_actions)),
            "connection_evidence": connection_evidence,
            "blockers": blockers,
            "human_approval_required": True,
            "execution_authority": False,
            "external_publication": False,
            "auto_publish": False,
            "canonical_runtime_only": True,
            "credentials_exposed": False,
        }

    @staticmethod
    def _blocked(error: str, *, status: str = "BLOCKED") -> dict[str, Any]:
        return {
            "success": False,
            "status": status,
            "error": error,
            "approval_packet": None,
            "publication_preflight": {"status": status, "ready": False, "execution_authority": False},
            "governance": {"read_only": True, "execution_authority": False, "external_publication": False, "mcp": False},
        }


final_content_approval_service = FinalContentApprovalService()
