from app.services.production_intelligence import ProductionIntelligence


def test_plan_context_rejects_cross_tenant_memory():
    svc = ProductionIntelligence()
    spec = svc.specification(
        organization_id=1, project_id="p", scenes=[], shots=[], assets=[], constraints=[]
    )
    memory = svc.memory(
        organization_id=2, project_id="p", facts=[], invariants=[],
        failure_patterns=[], evidence_digests=[]
    )
    try:
        svc.plan_context(
            organization_id=1, project_id="p",
            specification=spec, memory=memory, reuse_assessment={}
        )
    except ValueError as exc:
        assert str(exc) == "organization_mismatch"
    else:
        raise AssertionError("cross-tenant context must be rejected")

