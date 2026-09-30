"""Versioned, deterministic domain contracts for Kemet media planning."""
from __future__ import annotations
import hashlib, json
from typing import Any, Mapping
CONTENT_INTENT="kemet.content_intent.v1"; CONTENT_BLUEPRINT="kemet.content_blueprint.v1"
SCENE_PLAN="kemet.scene_plan.v1"; ASSET_PLAN="kemet.asset_plan.v1"
VOICE_PLAN="kemet.voice_plan.v1"; RENDER_PLAN="kemet.render_plan.v1"
QA_PLAN="kemet.qa_plan.v1"; DISTRIBUTION_PLAN="kemet.distribution_plan.v1"
VISUAL_STYLE_CONTRACT = "kemet.visual_style.v1"
VISUAL_PRODUCTION_JOB_CONTRACT = "kemet.visual_production_job.v1"
class ContractValidationError(ValueError): pass
CONTRACTS=(CONTENT_INTENT,CONTENT_BLUEPRINT,SCENE_PLAN,ASSET_PLAN,VOICE_PLAN,RENDER_PLAN,QA_PLAN,DISTRIBUTION_PLAN,VISUAL_STYLE_CONTRACT,VISUAL_PRODUCTION_JOB_CONTRACT)
def _json(value:Any)->str: return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),default=str)
def contract_digest(contract:Mapping[str,Any])->str: return hashlib.sha256(_json(contract).encode()).hexdigest()
def build_contract(kind:str,*,organization_id:int,payload:Mapping[str,Any],contract_id:str)->dict[str,Any]:
    if kind not in CONTRACTS: raise ContractValidationError("unsupported_media_contract")
    if not isinstance(organization_id,int) or organization_id<=0: raise ContractValidationError("organization_required")
    if not isinstance(contract_id,str) or not contract_id: raise ContractValidationError("contract_id_required")
    body={"schema":kind,"contract_id":contract_id[:160],"organization_id":organization_id,"payload":dict(payload)}
    body["digest"]=contract_digest(body); return body
def validate_contract(contract:Mapping[str,Any])->dict[str,Any]:
    if contract.get("schema") not in CONTRACTS: raise ContractValidationError("unsupported_media_contract")
    if not isinstance(contract.get("organization_id"),int) or contract["organization_id"]<=0: raise ContractValidationError("organization_required")
    expected=contract_digest({k:v for k,v in contract.items() if k!="digest"})
    if contract.get("digest")!=expected: raise ContractValidationError("contract_digest_mismatch")
    return dict(contract)


VISUAL_STYLE_CONTRACT = "kemet.visual_style.v1"
VISUAL_PRODUCTION_JOB_CONTRACT = "kemet.visual_production_job.v1"

VISUAL_STYLE_FAMILIES = (
    "CINEMATIC_LIVE_ACTION", "THREE_D_ANIMATION", "TWO_D_CARTOON", "ANIME_STYLIZED",
    "MOTION_GRAPHICS", "PRODUCT_COMMERCIAL", "EDUCATIONAL_EXPLAINER",
    "DOCUMENTARY_REALISTIC", "FANTASY", "SCI_FI", "COMIC_STORYBOARD",
    "HISTORICAL_CULTURAL", "SOCIAL_SHORT",
)

VISUAL_PRODUCTION_STAGES = (
    "BRIEF", "CREATIVE_DIRECTION", "STYLE", "STORY", "SCRIPT", "STORYBOARD",
    "CHARACTER", "WORLD", "ASSETS", "SHOTS", "FRAMES", "MOTION", "AUDIO",
    "ASSEMBLY", "EDIT", "QA", "APPROVAL", "MASTER", "DISTRIBUTION",
)

LICENSE_STATES = (
    "VERIFIED_COMMERCIAL", "VERIFIED_NONCOMMERCIAL", "RESTRICTED", "UNKNOWN", "NOT_VERIFIED",
)

CAPABILITY_STATES = (
    "VERIFIED_READY", "HARDWARE_LIMITED", "WAITING_FOR_CAPACITY", "BLOCKED", "NOT_VERIFIED",
)

QA_STATES = ("PASS", "FAIL", "BLOCKED", "NOT_VERIFIED")


def build_visual_style(*, organization_id: int, style_id: str, family: str,
                       payload: Mapping[str, Any], contract_id: str) -> dict[str, Any]:
    if family not in VISUAL_STYLE_FAMILIES:
        raise ContractValidationError("unsupported_visual_style_family")
    required = (
        "visual_language", "camera_language", "lighting_language", "color_language",
        "motion_language", "texture_language", "character_rules", "environment_rules",
        "typography_rules", "aspect_ratio", "shot_duration_range", "reference_policy",
        "consistency_policy", "qa_policy",
    )
    missing = [key for key in required if key not in payload]
    if missing:
        raise ContractValidationError("visual_style_fields_missing:" + ",".join(missing))
    body = build_contract(
        VISUAL_STYLE_CONTRACT,
        organization_id=organization_id,
        contract_id=contract_id,
        payload={"style_id": style_id, "family": family, **dict(payload)},
    )
    body["payload"]["provider_independent"] = True
    body["digest"] = contract_digest({k: v for k, v in body.items() if k != "digest"})
    return body


def build_visual_production_job(*, organization_id: int, job_id: str,
                                 style: Mapping[str, Any], stages: Mapping[str, Mapping[str, Any]] | None = None,
                                 status: str = "PLANNED") -> dict[str, Any]:
    if not isinstance(style, Mapping) or style.get("schema") != VISUAL_STYLE_CONTRACT:
        raise ContractValidationError("visual_style_contract_required")
    provided = dict(stages or {})
    unknown = sorted(set(provided) - set(VISUAL_PRODUCTION_STAGES))
    if unknown:
        raise ContractValidationError("unknown_visual_production_stage:" + ",".join(unknown))
    stage_records = {}
    for stage in VISUAL_PRODUCTION_STAGES:
        record = dict(provided.get(stage) or {})
        record.setdefault("status", "PLANNED")
        record.setdefault("evidence", None)
        stage_records[stage] = record
    payload = {
        "job_id": str(job_id),
        "style_digest": style.get("digest"),
        "style_id": (style.get("payload") or {}).get("style_id"),
        "stages": stage_records,
        "status": str(status).upper(),
        "provider_independent": True,
        "evidence_required": True,
        "governance": {"execution_authority": False, "external_execution": False, "mcp": False},
    }
    return build_contract(
        VISUAL_PRODUCTION_JOB_CONTRACT,
        organization_id=organization_id,
        contract_id=str(job_id),
        payload=payload,
    )


def validate_license_state(state: str) -> str:
    normalized = str(state or "").strip().upper()
    if normalized not in LICENSE_STATES:
        raise ContractValidationError("invalid_license_state")
    return normalized


def validate_capability_state(state: str) -> str:
    normalized = str(state or "").strip().upper()
    if normalized not in CAPABILITY_STATES:
        raise ContractValidationError("invalid_capability_state")
    return normalized


def validate_qa_state(state: str) -> str:
    normalized = str(state or "").strip().upper()
    if normalized not in QA_STATES:
        raise ContractValidationError("invalid_qa_state")
    return normalized
