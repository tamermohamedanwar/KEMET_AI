"""Canonical asset binding gate for Kemet Production OS."""
from __future__ import annotations
from hashlib import sha256
import json, mimetypes
from pathlib import Path
from typing import Any, Mapping

class AssetBindingGate:
    VERSION = "1.0"
    SCHEMA = "kemet.media.asset_binding_gate.v1"
    IMAGE_MIME = {"image/png", "image/jpeg", "image/webp"}

    def inspect(self, *, organization_id: int, project_id: str, references: list[Mapping[str, Any]]) -> dict[str, Any]:
        if int(organization_id or 0) <= 0: raise ValueError("organization_required")
        if not project_id: raise ValueError("project_required")
        if not isinstance(references, list) or not references: raise ValueError("references_required")
        checked=[]; errors=[]
        for ref in references:
            result=self._check(ref)
            checked.append(result)
            errors.extend(result["errors"])
        payload={"schema":self.SCHEMA,"version":1,"organization_id":int(organization_id),"project_id":str(project_id),"references":checked,"status":"BOUND" if not errors else "BLOCKED","canonical":True,"source_of_truth":"canonical_production_state","immutable_digest_binding":True}
        payload["digest"]=self._digest(payload)
        payload["governance"]={"human_approval_required":True,"execution_authority":False,"external_execution":False,"mcp":False}
        return payload

    def _check(self, ref: Mapping[str, Any]) -> dict[str, Any]:
        errors=[]
        ref_id=str(ref.get("id") or "").strip(); version=ref.get("version"); uri=str(ref.get("uri") or "").strip(); expected=str(ref.get("digest") or "").strip()
        if not ref_id: errors.append("reference_id_required")
        if not version: errors.append("reference_version_required")
        if not uri: errors.append("reference_uri_required")
        path=Path(uri.removeprefix("file://")) if uri else None
        actual=None; mime=None; size=None
        if path and path.is_file():
            size=path.stat().st_size; mime=mimetypes.guess_type(path.name)[0]
            if mime not in self.IMAGE_MIME: errors.append("unsupported_reference_mime")
            actual=self._file_digest(path)
            if expected and expected != actual: errors.append("reference_digest_mismatch")
        else: errors.append("reference_asset_missing")
        if not expected: errors.append("reference_digest_required")
        return {"id":ref_id,"version":int(version) if version else None,"uri":uri,"expected_digest":expected,"actual_digest":actual,"mime_type":mime,"size_bytes":size,"errors":sorted(set(errors)),"bound":not errors}

    @staticmethod
    def _file_digest(path:Path)->str:
        h=sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
        return h.hexdigest()
    @staticmethod
    def _digest(value:Any)->str:
        return sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str).encode()).hexdigest()

asset_binding_gate=AssetBindingGate()
