"""Readiness contract for governed media provider adapters."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping
from app.core.media.capabilities import MEDIA_CAPABILITIES

@dataclass(frozen=True)
class MediaProviderAdapterDescriptor:
    provider_id: str
    capabilities: tuple[str, ...]
    trust: str = "untrusted"
    execution_authority: bool = False
    external_execution: bool = False
    mcp: bool = False
    def __post_init__(self):
        if not self.provider_id.strip(): raise ValueError("provider_id_required")
        unknown=set(self.capabilities)-set(MEDIA_CAPABILITIES)
        if unknown: raise ValueError("unsupported_media_capability")
        if self.trust != "untrusted": raise ValueError("provider_output_must_be_untrusted")
        if self.execution_authority or self.external_execution or self.mcp: raise ValueError("media_adapter_governance_violation")
    def snapshot(self)->dict[str,Any]:
        return {"provider_id":self.provider_id,"capabilities":sorted(self.capabilities),"trust":self.trust,"execution_authority":False,"external_execution":False,"mcp":False}

def validate_provider_output(*, provider_id:str, output:Mapping[str,Any])->dict[str,Any]:
    if not provider_id.strip(): raise ValueError("provider_id_required")
    if not isinstance(output, Mapping): raise ValueError("provider_output_mapping_required")
    result=dict(output)
    result["provider_id"]=provider_id
    result["trust"]="untrusted"
    result["execution_authority"]=False
    result["external_execution"]=False
    result["mcp"]=False
    return result
