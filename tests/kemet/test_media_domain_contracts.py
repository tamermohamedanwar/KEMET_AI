from app.core.media.contracts import *
from app.core.media.governance import governance_envelope, assert_no_execution_authority
from app.core.media.provenance import provenance, digest_bytes
from app.core.media.artifacts import artifact_metadata
from app.core.media.capabilities import capability_snapshot

def test_contract_digest_is_deterministic_and_tenant_bound():
    c=build_contract(CONTENT_INTENT,organization_id=7,contract_id="i1",payload={"topic":"x"})
    assert validate_contract(c)["digest"]==c["digest"]
    c["organization_id"]=8
    import pytest
    with pytest.raises(ContractValidationError): validate_contract(c)

def test_governance_is_non_executing_and_non_mcp():
    g=governance_envelope(organization_id=7)
    assert g["controls"]["human_approval_required"] is True
    assert_no_execution_authority(g)

def test_provenance_and_artifact_integrity():
    d=digest_bytes(b"x")
    a=artifact_metadata(artifact_id="a1",organization_id=7,kind="audio",mime_type="audio/wav",digest=d)
    assert a["organization_id"]==7

def test_capability_snapshot_has_no_execution_authority():
    s=capability_snapshot(["TEXT_TO_SPEECH","LOCAL_PROCESSING"])
    assert s["execution_authority"] is False and s["mcp"] is False
