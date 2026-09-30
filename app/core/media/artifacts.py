"""Artifact metadata contract; bytes remain outside the domain envelope."""
from __future__ import annotations
from typing import Any
ALLOWED_KINDS={"audio","image","video","caption","document","render","bundle"}
def artifact_metadata(*,artifact_id:str,organization_id:int,kind:str,mime_type:str,digest:str,uri:str|None=None)->dict[str,Any]:
    if organization_id<=0: raise ValueError("organization_required")
    if not artifact_id: raise ValueError("artifact_id_required")
    if kind not in ALLOWED_KINDS: raise ValueError("unsupported_artifact_kind")
    if not mime_type or not digest: raise ValueError("artifact_integrity_required")
    return {"artifact_id":artifact_id[:160],"organization_id":organization_id,"kind":kind,"mime_type":mime_type[:160],"digest":digest,"uri":uri}
