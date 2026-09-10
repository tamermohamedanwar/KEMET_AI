from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass(frozen=True)
class IntegrationDefinition:
    integration_id: str
    name: str
    category: str
    capabilities: tuple = ()
    enabled: bool = True
    requires_approval: bool = True


@dataclass(frozen=True)
class GlobalProfile:
    locale: str = "en-US"
    currency: str = "USD"
    industry: str = "general"
    timezone: str = "UTC"


class GlobalizationEngine:
    SUPPORTED_LOCALES = {
        "en-US",
        "ar-EG",
        "de-DE",
        "fr-FR",
        "es-ES",
    }

    SUPPORTED_CURRENCIES = {
        "USD",
        "EUR",
        "GBP",
        "EGP",
        "SAR",
        "AED",
    }

    SUPPORTED_INDUSTRIES = {
        "general",
        "retail",
        "real_estate",
        "marketing",
        "hospitality",
        "education",
        "healthcare",
        "finance",
        "ecommerce",
        "travel",
    }

    def __init__(
        self,
        integrations: Optional[List[IntegrationDefinition]] = None,
    ):
        self._integrations: Dict[str, IntegrationDefinition] = {}

        for integration in integrations or []:
            self.register_integration(integration)

    def validate_profile(self, profile: GlobalProfile) -> Dict:
        errors = []

        if profile.locale not in self.SUPPORTED_LOCALES:
            errors.append("unsupported_locale")

        if profile.currency not in self.SUPPORTED_CURRENCIES:
            errors.append("unsupported_currency")

        if profile.industry not in self.SUPPORTED_INDUSTRIES:
            errors.append("unsupported_industry")

        if not profile.timezone:
            errors.append("timezone_required")

        return {
            "ok": not errors,
            "errors": errors,
            "profile": asdict(profile),
        }

    def register_integration(
        self,
        integration: IntegrationDefinition,
    ) -> Dict:
        if not integration.integration_id:
            raise ValueError("integration_id is required")

        if not integration.category:
            raise ValueError("integration category is required")

        self._integrations[integration.integration_id] = integration

        return {
            "ok": True,
            "integration_id": integration.integration_id,
            "registered": True,
        }

    def list_integrations(
        self,
        category: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List[Dict]:
        items = list(self._integrations.values())

        if category:
            items = [
                item
                for item in items
                if item.category == category
            ]

        if enabled_only:
            items = [
                item
                for item in items
                if item.enabled
            ]

        items.sort(
            key=lambda item: (
                item.category,
                item.name.lower(),
            )
        )

        return [asdict(item) for item in items]

    def resolve_integration(
        self,
        integration_id: str,
    ) -> Optional[Dict]:
        item = self._integrations.get(integration_id)

        if not item or not item.enabled:
            return None

        return asdict(item)

    def build_integration_plan(
        self,
        integration_id: str,
    ) -> Dict:
        item = self._integrations.get(integration_id)

        if not item:
            return {
                "ok": False,
                "status": "not_found",
                "integration_id": integration_id,
            }

        if not item.enabled:
            return {
                "ok": False,
                "status": "disabled",
                "integration_id": integration_id,
            }

        return {
            "ok": True,
            "status": (
                "waiting_approval"
                if item.requires_approval
                else "ready"
            ),
            "engine": "kemet_global_integrations",
            "version": "1.0",
            "integration": asdict(item),
            "requires_approval": item.requires_approval,
            "external_execution": False,
            "database_mutation": False,
        }

    def summary(self) -> Dict:
        items = list(self._integrations.values())

        return {
            "supported_locales": len(self.SUPPORTED_LOCALES),
            "supported_currencies": len(self.SUPPORTED_CURRENCIES),
            "supported_industries": len(self.SUPPORTED_INDUSTRIES),
            "integrations": len(items),
            "enabled_integrations": sum(
                1 for item in items if item.enabled
            ),
            "mode": "advisory",
            "external_execution": False,
            "database_mutation": False,
        }
