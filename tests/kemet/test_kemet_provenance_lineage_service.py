import pytest

from app.services.kemet_provenance_lineage_service import KemetProvenanceLineageService


@pytest.fixture
def service():
    return KemetProvenanceLineageService()


def node(kind, ident, tenant=7, version=1, digest="a" * 64):
    return {
        "type": kind,
        "id": ident,
        "organization_id": tenant,
        "version": version,
        "digest": digest,
    }


def test_build_and_verify_tenant_bound_lineage(service):
    package = service.build_chain(
        organization_id=7,
        trace_id="trace-1",
        nodes=[
            node("content", "content-1"),
            node("source", "source-1"),
            node("version", "version-1"),
            node("asset", "asset-1"),
            node("publication", "publication-1"),
            node("product", "product-1"),
            node("transaction", "transaction-1"),
        ],
    )
    assert package["schema"] == "kemet.provenance_lineage.v1"
    assert len(package["digest"]) == 64
    assert service.verify_chain(package=package, organization_id=7)["valid"] is True
    assert package["governance"]["external_execution"] is False


def test_lineage_rejects_cross_tenant_node(service):
    with pytest.raises(ValueError, match="lineage_tenant_mismatch"):
        service.build_chain(
            organization_id=7,
            trace_id="trace-2",
            nodes=[node("asset", "asset-1", tenant=8)],
        )


def test_lineage_rejects_unknown_node_type(service):
    with pytest.raises(ValueError, match="unsupported_node_type"):
        service.build_chain(
            organization_id=7,
            trace_id="trace-3",
            nodes=[node("unknown", "x")],
        )


def test_commerce_lineage_binds_payment_transaction(service):
    package = service.commerce_chain(
        organization_id=7,
        trace_id="exec-7",
        execution_key="exec-7",
        payment_evidence={
            "payment_id": 91,
            "amount": 125.0,
            "currency": "USD",
            "provider": "test",
            "provider_transaction_id": "tx-91",
        },
    )
    assert service.verify_chain(package=package, organization_id=7)["valid"] is True
    assert [node["type"] for node in package["nodes"]] == ["transaction"]
    assert package["nodes"][0]["id"] == "91"


def test_commerce_lineage_requires_evidence(service):
    with pytest.raises(ValueError, match="commerce_lineage_evidence_required"):
        service.commerce_chain(
            organization_id=7,
            trace_id="exec-8",
            execution_key="exec-8",
        )


def test_lineage_verification_fails_closed_on_external_execution(service):
    package = service.build_chain(
        organization_id=7,
        trace_id="trace-4",
        nodes=[node("asset", "asset-1")],
    )
    package["governance"]["external_execution"] = True
    assert service.verify_chain(package=package, organization_id=7)["valid"] is False
