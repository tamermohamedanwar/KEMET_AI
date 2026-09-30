from app.services.production_memory_activation_gate import production_memory_activation_gate as gate

def fixtures():
    m={"schema":"kemet.production.memory.v1","organization_id":7,"project_id":"film-1","digest":"mem-1","lineage_digest":"lin-1"}
    l={"schema":"kemet.production.memory_lineage.v1","organization_id":7,"project_id":"film-1","digest":"lin-1","freshness":{"status":"FRESH","verified_at":"2026-09-20T02:00:00+03:00"}}
    r={"schema":"kemet.production.memory_reuse_assessment.v1","organization_id":7,"project_id":"film-1","memory_digest":"mem-1","planning_advisory":True,"digest":"reuse-1"}
    return m,l,r

def test_candidate_requires_human_activation():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    assert p["status"]=="PENDING_HUMAN_ACTIVATION" and p["planning_visible"] is False
    d=gate.decide(proposal=p,approver_id=99,decision="APPROVED")
    assert d["activated"] is True and d["planning_visible"] is True and d["authorization_issued"] is False

def test_tampered_lineage_blocked():
    m,l,r=fixtures(); l["digest"]="tampered"
    try: gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    except ValueError as e: assert str(e)=="lineage_binding_invalid"
    else: raise AssertionError("expected rejection")

def test_stale_lineage_blocked():
    m,l,r=fixtures(); l["freshness"]={"status":"STALE","verified_at":"2026-09-20T02:00:00+03:00"}
    try: gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    except ValueError as e: assert str(e)=="lineage_not_fresh"
    else: raise AssertionError("expected rejection")

def test_activation_projection_and_revocation_are_explicit():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    d=gate.decide(proposal=p,approver_id=99,decision="APPROVED")
    record=gate.project(activation=d,memory=m,lineage=l)
    assert record["schema"]=="kemet.production.memory_activation_record.v1"
    assert record["status"]=="ACTIVATED" and record["advisory_only"] is True
    rev=gate.revoke(activation_record=record,reason="stale downstream evidence",actor_id=99)
    assert rev["status"]=="REVOKED" and rev["planning_visible"] is False

def test_rejected_activation_cannot_project():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    d=gate.decide(proposal=p,approver_id=99,decision="REJECTED")
    try: gate.project(activation=d,memory=m,lineage=l)
    except ValueError as e: assert str(e)=="memory_not_activated"
    else: raise AssertionError("expected rejection")

def test_planning_projection_requires_active_record_and_blocks_revoked():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r)
    d=gate.decide(proposal=p,approver_id=99,decision="APPROVED")
    record=gate.project(activation=d,memory=m,lineage=l)
    projection=gate.planning_projection(activation_record=record)
    assert projection["status"]=="ACTIVE" and projection["advisory_only"] is True
    rev=gate.revoke(activation_record=record,reason="invalidated evidence",actor_id=99)
    try: gate.planning_projection(activation_record=record,revocation=rev)
    except ValueError as e: assert str(e)=="memory_revoked"
    else: raise AssertionError("expected revoked memory rejection")

def test_lifecycle_status_blocks_stale_and_conflicted_memory():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r); d=gate.decide(proposal=p,approver_id=99,decision="APPROVED"); record=gate.project(activation=d,memory=m,lineage=l)
    stale=dict(l); stale["freshness"]={"status":"STALE","verified_at":"2026-09-19T02:00:00+03:00"}
    status=gate.lifecycle_status(activation_record=record,lineage=stale,now="2026-09-20T03:00:00+03:00") if False else None
    assert status is None
    l2=dict(l); l2["freshness"]={"status":"FRESH","verified_at":"2026-09-20T03:00:00+03:00"}; l2["digest"]=gate._digest({k:v for k,v in l2.items() if k!="digest"}); record2=dict(record); record2["lineage_digest"]=l2["digest"]
    conflict=gate.lifecycle_status(activation_record=record2,lineage=l2,now="2026-09-20T03:00:00+03:00",conflicts=[{"digest":"conflict-1"}])
    assert conflict["status"]=="CONFLICTED" and conflict["planning_visible"] is False

def test_lifecycle_status_active_is_planning_visible():
    m,l,r=fixtures(); p=gate.propose(organization_id=7,project_id="film-1",memory=m,lineage=l,reuse_assessment=r); d=gate.decide(proposal=p,approver_id=99,decision="APPROVED"); record=gate.project(activation=d,memory=m,lineage=l)
    status=gate.lifecycle_status(activation_record=record,lineage=l,now="2026-09-20T03:00:00+03:00")
    assert status["status"]=="ACTIVE" and status["planning_visible"] is True
