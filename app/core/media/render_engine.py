from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json, shutil, subprocess
from pathlib import Path
from typing import Any, Mapping

from app.core.media.artifacts import artifact_metadata
from app.core.media.contracts import RENDER_PLAN, build_contract, contract_digest
from app.core.media.governance import governance_envelope

@dataclass(frozen=True)
class RenderRequest:
    organization_id: int
    input_uri: str
    output_uri: str
    duration_seconds: float | None = None
    source_spec: Mapping[str, Any] | None = None
    video_filter: str | None = None
    audio: bool = True
    audio_uri: str | None = None

class RenderEngineV1:
    VERSION="1.0"
    RENDERER="ffmpeg-local"

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str).encode()).hexdigest()

    def snapshot(self) -> dict[str, Any]:
        ffmpeg=shutil.which("ffmpeg")
        ffprobe=shutil.which("ffprobe")
        return {"version":self.VERSION,"renderer":self.RENDERER,"configured":bool(ffmpeg and ffprobe),
                "ffmpeg":ffmpeg,"ffprobe":ffprobe,"network":"disabled",
                "execution_authority":False,"external_execution":False,"mcp":False}

    def plan(self, request: RenderRequest) -> dict[str, Any]:
        if request.organization_id <= 0: raise ValueError("organization_required")
        if not request.output_uri: raise ValueError("render_paths_required")
        if not request.source_spec and not request.input_uri: raise ValueError("render_paths_required")
        if not request.source_spec and "://" in request.input_uri and not request.input_uri.startswith("file://"): raise ValueError("remote_input_blocked")
        if "://" in request.output_uri and not request.output_uri.startswith("file://"): raise ValueError("remote_output_blocked")
        canonical={"schema":RENDER_PLAN,"version":self.VERSION,"organization_id":request.organization_id,
                   "input_uri":request.input_uri,"output_uri":request.output_uri,
                   "source_spec":request.source_spec,"duration_seconds":request.duration_seconds,"video_filter":request.video_filter,"audio":request.audio,"audio_uri":request.audio_uri,
                   "renderer":self.RENDERER,"network":"disabled","execution_authority":False}
        governance={**governance_envelope(organization_id=request.organization_id, action="media.render"), "mcp": False, "execution_authority": False, "external_execution": False, "auto_publish": False}
        payload={**canonical, "governance": governance}
        contract=build_contract(
            RENDER_PLAN,
            organization_id=request.organization_id,
            payload=payload,
            contract_id=self._digest(payload)[:32],
        )
        contract.update(canonical)
        contract["governance"]=governance
        contract["digest"]=contract_digest({k:v for k,v in contract.items() if k!="digest"})
        contract["contract_digest"]=contract["digest"]
        return contract

    def render(self, plan: Mapping[str, Any], *, approval: bool=False, execution_authorization: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if approval is not True: return {"success":False,"status":"blocked","error":"human_approval_required","executed":False}
        if not isinstance(execution_authorization, Mapping): return {"success":False,"status":"blocked","error":"canonical_execution_required","executed":False}
        if execution_authorization.get("_execution_action") != "media_render": return {"success":False,"status":"blocked","error":"media_render_action_required","executed":False}
        if not execution_authorization.get("_approved_execution") or not execution_authorization.get("gate_handoff"): return {"success":False,"status":"blocked","error":"gate_handoff_required","executed":False}
        if bool(plan.get("execution_authority")) or plan.get("network") != "disabled": return {"success":False,"status":"blocked","error":"render_plan_governance_violation","executed":False}
        input_uri = str(plan.get("input_uri", ""))
        source_spec = plan.get("source_spec")
        target=Path(str(plan.get("output_uri","")).removeprefix("file://"))
        if source_spec:
            if not isinstance(source_spec, Mapping) or source_spec.get("type") != "lavfi" or not str(source_spec.get("value") or "").strip():
                return {"success":False,"status":"blocked","error":"render_source_spec_invalid","executed":False}
        audio_uri = str(plan.get("audio_uri") or "").strip()
        if audio_uri:
            if "://" in audio_uri and not audio_uri.startswith("file://"):
                return {"success":False,"status":"blocked","error":"remote_audio_blocked","executed":False}
            audio_path = Path(audio_uri.removeprefix("file://"))
            if not audio_path.is_file():
                return {"success":False,"status":"blocked","error":"render_audio_missing","executed":False}
        else:
            audio_path = None
        if not source_spec:
            source=Path(input_uri.removeprefix("file://"))
            if not source.is_file(): return {"success":False,"status":"blocked","error":"render_input_missing","executed":False}
        ffmpeg=shutil.which("ffmpeg")
        if not ffmpeg: return {"success":False,"status":"blocked","error":"ffmpeg_runtime_required","executed":False}
        target.parent.mkdir(parents=True,exist_ok=True)
        if source_spec:
            cmd=[ffmpeg,"-hide_banner","-loglevel","error","-y","-f","lavfi","-i",str(source_spec["value"])]
        else:
            cmd=[ffmpeg,"-hide_banner","-loglevel","error","-y","-i",str(source)]
        if plan.get("duration_seconds") is not None: cmd += ["-t",str(plan["duration_seconds"])]
        if plan.get("video_filter"): cmd += ["-vf",str(plan["video_filter"])]
        if audio_path:
            cmd += ["-i",str(audio_path),"-map","0:v:0","-map","1:a:0","-shortest"]
        elif not plan.get("audio",True):
            cmd += ["-an"]
        cmd += ["-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac",str(target)]
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=600)
        except subprocess.TimeoutExpired:
            return {"success":False,"status":"unknown","error":"render_timeout","executed":False}
        if result.returncode != 0:
            return {"success":False,"status":"failed","error":"local_media_render_failed","stderr":result.stderr[-1000:],"executed":False}
        digest=self._file_digest(target)
        artifact=artifact_metadata(artifact_id=self._digest({"plan":plan.get("contract_digest"),"output":str(target)})[:32],
                                   organization_id=int(plan["organization_id"]),kind="video",mime_type="video/mp4",digest=digest,uri=str(target))
        return {"success":True,"status":"rendered","executed":True,"external_execution":False,"artifact":artifact,
                "plan_digest":plan.get("contract_digest"),"governance":governance_envelope(organization_id=int(plan["organization_id"]), action="media.render")}
    @staticmethod
    def _file_digest(path:Path)->str:
        h=sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        return h.hexdigest()

render_engine_v1=RenderEngineV1()
