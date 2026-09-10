from __future__ import annotations

from dataclasses import dataclass, field

from .connector_contract import ConnectorContract


@dataclass
class ConnectorRegistry:
    """Organization-scoped registry for declarative external connectors."""

    _contracts: dict[tuple[int, str], ConnectorContract] = field(default_factory=dict)

    def _key(self, organization_id: int, connector_id: str) -> tuple[int, str]:
        return (int(organization_id), str(connector_id).strip())

    def register(self, contract: ConnectorContract) -> dict:
        result = contract.validate()
        if not result["valid"]:
            return {"registered": False, "errors": result["errors"]}
        if contract.organization_id is None:
            return {"registered": False, "errors": ["organization_id_required"]}
        key = self._key(contract.organization_id, contract.connector_id)
        self._contracts[key] = contract
        return {
            "registered": True,
            "connector_id": contract.connector_id,
            "organization_id": contract.organization_id,
        }

    def get(
        self,
        connector_id: str,
        organization_id: int | None = None,
    ) -> ConnectorContract | None:
        connector_id = str(connector_id).strip()
        if organization_id is not None:
            return self._contracts.get(self._key(organization_id, connector_id))
        matches = [
            contract
            for (org_id, registered_id), contract in self._contracts.items()
            if registered_id == connector_id
        ]
        return matches[0] if len(matches) == 1 else None

    def allows(self, connector_id: str, operation: str, organization_id: int) -> bool:
        contract = self.get(connector_id, organization_id)
        return bool(contract and contract.allows(operation, organization_id))

    def list_for_organization(self, organization_id: int) -> list[dict]:
        return [
            contract.as_dict()
            for (org_id, _), contract in self._contracts.items()
            if org_id == organization_id
        ]

    def validate_all(self) -> dict:
        results = {
            f"{org_id}:{connector_id}": contract.validate()
            for (org_id, connector_id), contract in self._contracts.items()
        }
        return {
            "valid": all(item["valid"] for item in results.values()),
            "connectors": results,
        }

    def clear(self) -> None:
        self._contracts.clear()


connector_registry = ConnectorRegistry()
