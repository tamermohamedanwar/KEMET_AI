from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

from app.services.mendes.mendes_governed_pilot_service import mendes_governed_pilot_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service
from app.services.mendes.mendes_production_job_service import mendes_production_job_service
from app.services.mendes.mendes_production_job_store import mendes_production_job_store
from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.production_backlot_service import production_backlot_service


class MendesControlledProductionService:
    VERSION = "1.0"
    ARTIFACT_VERSION = "kemet.mendes.production_artifact.v1"
    OUTPUT_ROOT = Path("instance/production/mendes")
    FONT_CANDIDATES = (
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    def execute(self, organization_id: int, approval: bool) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        if approval is not True:
            return self._blocked("production_approval_required")

        source = mendes_pilot_episode_service.build(org)
        package = source["package"]
        pilot = mendes_governed_pilot_service.assemble(org)
        voice_contract = package.get("voice_contract") or {
            "organization_id": org,
            "script_digest": package.get("script_digest") or pilot.get("episode_package_digest"),
            "contract_digest": self._digest({"episode_package_digest": pilot.get("episode_package_digest"), "voice_clone": False}),
            "voice_clone": False,
        }
        if int(voice_contract.get("organization_id") or 0) != org:
            return self._blocked("voice_contract_tenant_mismatch")

        quality_gates = package.get("quality_gates") or ["creative", "rights", "historical_label", "platform_policy", "production_integrity"]
        idempotency_key = f"phase6:mendes:{pilot['episode_package_digest']}"
        readiness_job = mendes_production_job_service.create(
            org,
            package,
            voice_contract,
            quality_gates,
            approval_state="pending",
            workflow_purpose="readiness",
        )
        readiness = mendes_episode_readiness_service.build(
            organization_id=org,
            job=readiness_job,
            package=package,
        )
        if readiness.get("readiness_status") == "BLOCKED":
            return self._blocked("episode_not_production_ready", readiness=readiness)
        job = mendes_production_job_store.create(
            org,
            package,
            voice_contract,
            quality_gates,
            approval_state="approved",
            idempotency_key=idempotency_key,
            workflow_purpose="production",
        )

        if job.get("state") == "VERIFIED":
            publication = mendes_publication_contract_service.validate(
                organization_id=org, production_job_id=job["job_id"], approval=False
            )
            refs = job.get("asset_refs") or []
            replay_artifact = None
            replay_verification = None
            if refs:
                ref = refs[0]
                replay_artifact = {
                    "artifact_kind": ref.get("kind"),
                    "artifact_path": ref.get("uri"),
                    "artifact_digest": ref.get("sha256"),
                    "artifact_ref": ref,
                    "duration_seconds": ref.get("duration_seconds"),
                }
                replay_verification = self._verify_artifact(replay_artifact, package, pilot["episode_package_digest"])
                if not replay_verification["verified"]:
                    return self._result(org, pilot, job, readiness, publication, artifact=replay_artifact, verification=replay_verification, replayed=True)
            return self._result(org, pilot, job, readiness, publication, artifact=replay_artifact, verification=replay_verification, replayed=True)

        if job.get("state") == "PLANNED":
            job = mendes_production_job_store.transition(org, job["job_id"], "APPROVED", approval=True)
        if job.get("state") == "APPROVED":
            job = mendes_production_job_store.transition(org, job["job_id"], "PRODUCING", approval=True)

        artifact = self._render_proof_artifact(org, package, pilot["episode_package_digest"])
        job = mendes_production_job_store.set_asset_refs(org, job["job_id"], [artifact["artifact_ref"]])
        job = mendes_production_job_store.transition(
            org,
            job["job_id"],
            "PRODUCED",
            approval=True,
            evidence={"type": "artifact_produced", "artifact_digest": artifact["artifact_digest"], "artifact_kind": artifact["artifact_kind"]},
        )
        verification = self._verify_artifact(artifact, package, pilot["episode_package_digest"])
        if not verification["verified"]:
            job = mendes_production_job_store.transition(
                org,
                job["job_id"],
                "FAILED",
                evidence=verification,
            )
            publication = mendes_publication_contract_service.validate(
                organization_id=org, production_job_id=job["job_id"], approval=False
            )
            return self._result(org, pilot, job, readiness, publication, artifact=artifact, verification=verification)

        job = mendes_production_job_store.transition(
            org,
            job["job_id"],
            "VERIFIED",
            evidence={
                "type": "artifact_verified",
                "artifact_digest": artifact["artifact_digest"],
                "verification_digest": verification["verification_digest"],
            },
        )
        publication = mendes_publication_contract_service.validate(
            organization_id=org, production_job_id=job["job_id"], approval=False
        )
        return self._result(org, pilot, job, readiness, publication, artifact=artifact, verification=verification)

    def _render_proof_artifact(self, organization_id: int, package: dict[str, Any], package_digest: str) -> dict[str, Any]:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("local_renderer_unavailable")
        font = next((p for p in self.FONT_CANDIDATES if os.path.exists(p)), None)
        if not font:
            raise RuntimeError("arabic_font_unavailable")

        episode = package.get("episode") or {}
        scenes = package.get("scenes") or []
        if not scenes:
            raise ValueError("scenes_required")
        episode_id = str(episode.get("episode_id") or "s1e1")
        root = self.OUTPUT_ROOT / f"org_{organization_id}" / episode_id
        root.mkdir(parents=True, exist_ok=True)
        work = root / "render_work"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True)
        clips: list[Path] = []
        total_duration = 0
        for scene in scenes:
            number = int(scene.get("scene_number") or len(clips) + 1)
            duration = int(scene.get("duration_seconds") or 1)
            total_duration += duration
            text_path = work / f"scene_{number}.txt"
            lines = [
                f"HIKAYAT MENDES — S1E1",
                f"SCENE {number}",
                str(scene.get("description") or ""),
                f"DIALOGUE: {scene.get('dialogue') or ''}",
            ]
            text_path.write_text("\n".join(lines), encoding="utf-8")
            clip = work / f"clip_{number}.mp4"
            vf = (
                f"drawtext=fontfile={font}:textfile={text_path}:text_shaping=1:"
                "fontcolor=white:fontsize=42:line_spacing=18:"
                "x=(w-text_w)/2:y=(h-text_h)/2:"
                "box=1:boxcolor=black@0.62:boxborderw=32"
            )
            cmd = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=0x10233F:s=1280x720:r=24",
                "-t", str(duration), "-vf", vf,
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                str(clip),
            ]
            completed = subprocess.run(cmd, capture_output=True, text=True, timeout=max(60, duration * 5))
            if completed.returncode != 0:
                raise RuntimeError("local_media_render_failed")
            clips.append(clip)

        concat_file = work / "concat.txt"
        concat_file.write_text("ffconcat version 1.0\n" + "".join(f"file '{c.resolve().as_posix()}'\n" for c in clips), encoding="utf-8")
        output = root / f"{episode_id}_controlled_production.mp4"
        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_file),
            "-an", "-c", "copy", "-movflags", "+faststart", str(output),
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=max(120, total_duration * 3))
        if completed.returncode != 0:
            raise RuntimeError("local_media_concat_failed")
        digest = self._file_digest(output)
        manifest = {
            "schema": self.ARTIFACT_VERSION,
            "organization_id": organization_id,
            "episode_id": episode_id,
            "episode_package_digest": package_digest,
            "artifact_kind": "controlled_production_proof_video",
            "path": str(output),
            "format": "mp4",
            "duration_seconds": total_duration,
            "scene_count": len(scenes),
            "sha256": digest,
            "renderer": "ffmpeg-local",
            "network": "disabled",
            "external_execution": False,
            "publication": "not_requested",
            "final_creative_quality": "not_claimed",
        }
        manifest_path = root / f"{episode_id}_controlled_production_manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return {
            "artifact_kind": manifest["artifact_kind"],
            "artifact_path": str(output),
            "manifest_path": str(manifest_path),
            "artifact_digest": digest,
            "artifact_ref": {
                "type": "local_media_artifact",
                "kind": manifest["artifact_kind"],
                "uri": str(output),
                "sha256": digest,
                "format": "mp4",
                "duration_seconds": total_duration,
                "package_digest": package_digest,
                "scene_count": len(scenes),
            },
            "duration_seconds": total_duration,
            "scene_count": len(scenes),
        }

    def _verify_artifact(self, artifact: dict[str, Any], package: dict[str, Any], package_digest: str) -> dict[str, Any]:
        path = Path(str(artifact.get("artifact_path") or ""))
        ref = artifact.get("artifact_ref") or {}
        manifest_path = path.with_name(f"{path.stem}_manifest.json")
        manifest = {}
        if manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                manifest = {}
        bound_digest = str(ref.get("package_digest") or manifest.get("episode_package_digest") or "")
        bound_scene_count = int(ref.get("scene_count") or manifest.get("scene_count") or artifact.get("scene_count") or 0)
        checks = {
            "exists": path.is_file(),
            "non_empty": path.is_file() and path.stat().st_size > 0,
            "sha256_matches": path.is_file() and self._file_digest(path) == artifact.get("artifact_digest"),
            "manifest_present": manifest_path.is_file(),
            "package_digest_bound": package_digest == bound_digest,
            "scene_count_bound": bound_scene_count == len(package.get("scenes") or []),
        }
        verified = all(checks.values())
        payload = {"schema": "kemet.mendes.artifact_verification.v1", "checks": checks, "verified": verified}
        payload["verification_digest"] = self._digest(payload)
        return payload

    @staticmethod
    def _file_digest(path: Path) -> str:
        digest = sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _result(self, organization_id: int, pilot: dict[str, Any], job: dict[str, Any], readiness: dict[str, Any], publication: dict[str, Any], *, artifact: dict[str, Any] | None = None, verification: dict[str, Any] | None = None, replayed: bool = False) -> dict[str, Any]:
        return {
            "success": job.get("state") == "VERIFIED",
            "status": "VERIFIED" if job.get("state") == "VERIFIED" else job.get("state"),
            "version": self.VERSION,
            "organization_id": organization_id,
            "episode": pilot["package"]["episode"],
            "production_job": job,
            "readiness": readiness,
            "artifact": artifact,
            "verification": verification,
            "publication": publication,
            "measurement": {"status": "AWAITING_AUTHORITATIVE_PLATFORM_MEASUREMENT", "views": None, "qualified_views": None, "revenue": None, "synthetic": False},
            "learning": {"status": "PENDING_AUTHORITATIVE_OUTCOME", "synthetic": False},
            "replayed": replayed,
            "governance": {
                "human_approval_required": True,
                "approval_granted_for_local_production": True,
                "external_execution": False,
                "external_publication": False,
                "auto_publish": False,
                "canonical_runtime_only": True,
                "execution_authority": False,
                "credentials_exposed": False,
                "mcp": False,
            },
            "truth_boundary": "This artifact is a locally rendered controlled production proof. It is not represented as a final creative master, published media, platform performance, or revenue evidence.",
            "phase": "PHASE_6_CONTROLLED_PRODUCTION_EXECUTION",
        }

    @staticmethod
    def _blocked(error: str, **extra: Any) -> dict[str, Any]:
        return {"success": False, "status": "BLOCKED", "error": error, "external_execution": False, "execution_authority": False, **extra}


mendes_controlled_production_service = MendesControlledProductionService()
