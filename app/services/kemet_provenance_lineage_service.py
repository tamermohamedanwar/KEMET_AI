from __future__ import annotations

from typing import Any, Mapping

from app.core.evidence.fabric import execution_evidence_fabric


class KemetProvenanceLineageService:
    """Build tenant-bound provenance across governed business artifacts."""

    VERSION = "1.0"
    NODE_TYPES = (
        "content",
        "source",
        "version",
        "asset",
        "publication",
        "product",
        "transaction",
    )

    def build_chain(
        self,
        *,
        organization_id: int,
        nodes: list[Mapping[str, Any]],
        trace_id: str,
    ) -> dict[str, Any]:
        organization_id = int(organization_id or 0)
        if organization_id <= 0:
            raise ValueError("organization_required")
        trace_id = str(trace_id or "").strip()
        if not trace_id:
            raise ValueError("trace_id_required")
        if not nodes:
            raise ValueError("nodes_required")

        normalized: list[dict[str, Any]] = []
        for node in nodes:
            node_type = str(node.get("type") or "").strip().lower()
            node_id = str(node.get("id") or "").strip()
            tenant = int(node.get("organization_id") or 0)
            if node_type not in self.NODE_TYPES:
                raise ValueError("unsupported_node_type")
            if not node_id:
                raise ValueError("node_id_required")
            if tenant != organization_id:
                raise ValueError("lineage_tenant_mismatch")
            digest = str(node.get("digest") or "").strip()
            if len(digest) != 64:
                raise ValueError("node_digest_required")
            normalized.append({
                "type": node_type,
                "id": node_id,
                "organization_id": organization_id,
                "version": node.get("version"),
                "digest": digest,
                "metadata": dict(node.get("metadata") or {}),
            })

        correlation = execution_evidence_fabric.correlation_context(
            trace_id=trace_id, organization_id=organization_id,
        )
        package = {
            "schema": "kemet.provenance_lineage.v1",
            "version": self.VERSION,
            "correlation": correlation,
            "nodes": normalized,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "tenant_scoped": True,
                "human_approval_required": True,
                "canonical_executor": "kemet",
            },
        }
        package["digest"] = execution_evidence_fabric.digest(package)
        return package

    def attach_to_evidence(self, *, package: Mapping[str, Any], evidence: Mapping[str, Any], organization_id: int) -> dict[str, Any]:
        verified = self.verify_chain(package=package, organization_id=organization_id)
        if not verified["valid"]:
            raise ValueError("invalid_provenance_lineage")
        evidence_package = dict(evidence)
        evidence_package["provenance"] = {
            "schema": package.get("schema"),
            "digest": package.get("digest"),
            "node_count": len(package.get("nodes") or []),
            "organization_id": int(organization_id),
        }
        evidence_package["digest"] = execution_evidence_fabric.digest(
            {key: value for key, value in evidence_package.items() if key != "digest"}
        )
        return evidence_package

    def commerce_chain(
        self,
        *,
        organization_id: int,
        trace_id: str,
        execution_key: str,
        payment_evidence: Mapping[str, Any] | None = None,
        product_id: Any = None,
    ) -> dict[str, Any]:
        nodes: list[dict[str, Any]] = []
        if product_id is not None and str(product_id).strip():
            product_identity = str(product_id).strip()
            nodes.append({
                "type": "product",
                "id": product_identity,
                "organization_id": organization_id,
                "version": 1,
                "digest": execution_evidence_fabric.digest({
                    "type": "product", "id": product_identity,
                    "organization_id": organization_id,
                }),
                "metadata": {"execution_key": str(execution_key)},
            })
        payment = dict(payment_evidence or {})
        payment_id = payment.get("payment_id")
        if payment_id is not None:
            transaction_identity = str(payment_id).strip()
            nodes.append({
                "type": "transaction",
                "id": transaction_identity,
                "organization_id": organization_id,
                "version": 1,
                "digest": execution_evidence_fabric.digest({
                    "type": "transaction", "id": transaction_identity,
                    "organization_id": organization_id,
                    "amount": payment.get("amount"),
                    "currency": payment.get("currency"),
                    "provider_transaction_id": payment.get("provider_transaction_id"),
                }),
                "metadata": {
                    "execution_key": str(execution_key),
                    "provider": payment.get("provider"),
                    "provider_transaction_id": payment.get("provider_transaction_id"),
                },
            })
        if not nodes:
            raise ValueError("commerce_lineage_evidence_required")
        return self.build_chain(
            organization_id=organization_id, nodes=nodes, trace_id=trace_id,
        )

    def verify_chain(self, *, package: Mapping[str, Any], organization_id: int) -> dict[str, Any]:
        expected_tenant = int(organization_id or 0)
        if expected_tenant <= 0:
            raise ValueError("organization_required")
        nodes = list(package.get("nodes") or [])
        checks = {
            "schema": package.get("schema") == "kemet.provenance_lineage.v1",
            "tenant": all(int(node.get("organization_id") or 0) == expected_tenant for node in nodes),
            "node_types": all(str(node.get("type")) in self.NODE_TYPES for node in nodes),
            "node_digests": all(len(str(node.get("digest") or "")) == 64 for node in nodes),
            "read_only": package.get("governance", {}).get("read_only") is True,
            "external_execution": package.get("governance", {}).get("external_execution") is False,
        }
        return {"valid": bool(nodes) and all(checks.values()), "checks": checks, "authority": "none"}


kemet_provenance_lineage_service = KemetProvenanceLineageService()
