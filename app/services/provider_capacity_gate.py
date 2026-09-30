"""Provider capability and capacity gate; never assumes capacity from configuration alone."""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping

class ProviderCapacityGate:
    VERSION="1.0"; SCHEMA="kemet.media.provider_capacity_gate.v1"
    def evaluate(self, *, providers: list[Mapping[str,Any]], required_capabilities: list[str], shot: Mapping[str,Any] | None=None)->dict[str,Any]:
        required={str(x) for x in required_capabilities if str(x)}; results=[]
        for p in providers:
            caps={str(x) for x in (p.get("capabilities") or [])}; cap_ok=required.issubset(caps)
            cap=dict(p.get("capacity") or {}); configured=bool(p.get("configured")); healthy=bool(p.get("healthy",False)); available=bool(p.get("available",False))
            concurrency_ok=cap.get("in_flight",0) < cap.get("max_concurrency",1) if cap.get("max_concurrency") is not None else True
            queue_ok=cap.get("queue_depth",0) <= cap.get("max_queue_depth",10**9)
            ready=cap_ok and configured and healthy and available and concurrency_ok and queue_ok
            results.append({"provider_id":p.get("provider_id"),"capability_ok":cap_ok,"configured":configured,"healthy":healthy,"available":available,"concurrency_ok":concurrency_ok,"queue_ok":queue_ok,"ready":ready,"capacity":cap})
        payload={"schema":self.SCHEMA,"version":1,"required_capabilities":sorted(required),"providers":results,"ready_providers":[x["provider_id"] for x in results if x["ready"]],"status":"READY" if any(x["ready"] for x in results) else "BLOCKED","policy":{"configuration_is_not_capacity":True,"stale_capacity_requires_refresh":True,"approval_required_before_external_generation":True}}
        payload["digest"]=sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str).encode()).hexdigest(); payload["governance"]={"human_approval_required":True,"execution_authority":False,"external_execution":False,"mcp":False}; return payload
provider_capacity_gate=ProviderCapacityGate()
