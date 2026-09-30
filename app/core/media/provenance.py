"""Deterministic provenance metadata for untrusted media/provider inputs."""
from __future__ import annotations
import hashlib
from typing import Any
def digest_bytes(data:bytes)->str: return hashlib.sha256(data).hexdigest()
def provenance(*,source_type:str,source_ref:str,trust:str="untrusted",digest:str|None=None)->dict[str,Any]:
    if source_type not in {"user","provider","local","derived"}: raise ValueError("invalid_source_type")
    if trust not in {"trusted","untrusted"}: raise ValueError("invalid_trust")
    if not source_ref: raise ValueError("source_ref_required")
    return {"source_type":source_type,"source_ref":source_ref[:500],"trust":trust,"digest":digest}
