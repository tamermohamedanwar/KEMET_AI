"""Governance envelope for media plans; never grants execution authority."""
from __future__ import annotations
from typing import Any, Mapping
GOVERNANCE={"mode":"advisory","human_approval_required":True,"execution_authority":False,"external_execution":False,"auto_publish":False,"canonical_runtime":True,"mcp":False}
def governance_envelope(*,organization_id:int,action:str="media.plan")->dict[str,Any]:
    if organization_id<=0: raise ValueError("organization_required")
    if not action: raise ValueError("action_required")
    return {"organization_id":organization_id,"action":action,"controls":dict(GOVERNANCE)}
def assert_no_execution_authority(value:Mapping[str,Any])->None:
    controls=value.get("controls",{})
    if controls.get("execution_authority") or controls.get("external_execution") or controls.get("auto_publish"): raise ValueError("media_governance_execution_authority_forbidden")
    if controls.get("mcp") is not False: raise ValueError("media_mcp_forbidden")
