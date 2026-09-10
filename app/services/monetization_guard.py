"""Kemet commercial enforcement boundary.

Centralized, fail-closed entitlement and usage decisions.
This layer does not mutate billing state or execute external actions.
"""

from app.services.entitlement_service import EntitlementService
from app.services.saas_control_plane import saas_control_plane


class MonetizationGuard:
    VERSION = "1.0"

    def feature(self, organization_id, feature, require_usage=False):
        if not organization_id:
            return self._blocked("organization_required", feature=feature)

        try:
            entitlement = EntitlementService.require_feature(
                organization_id, feature
            )
        except Exception:
            return self._blocked(
                "entitlement_check_failed", feature=feature
            )

        if not entitlement.get("allowed"):
            return self._blocked(
                entitlement.get("reason") or "feature_not_entitled",
                feature=entitlement.get("feature", feature),
                plan=entitlement.get("plan"),
            )

        usage = None
        if require_usage:
            try:
                usage = EntitlementService.usage(organization_id)
            except Exception:
                return self._blocked(
                    "usage_check_failed",
                    feature=entitlement.get("feature", feature),
                )
            if not usage.get("allowed"):
                return self._blocked(
                    "usage_limit_reached",
                    feature=entitlement.get("feature", feature),
                    plan=usage.get("plan"),
                    limit=usage.get("limit"),
                    used=usage.get("used"),
                    remaining=usage.get("remaining"),
                )

        return {
            "allowed": True,
            "plan": entitlement.get("plan"),
            "feature": entitlement.get("feature", feature),
            "usage": usage,
            "reason": "commercial_policy_allowed",
            "governance": self._governance(),
        }

    def capability(self, organization_id, capability_id, require_usage=False):
        result = saas_control_plane.check_capability(
            organization_id, capability_id
        )
        if not result.get("allowed"):
            return {
                "allowed": False,
                "capability_id": capability_id,
                "feature": result.get("feature"),
                "plan": result.get("plan"),
                "reason": result.get("reason") or "capability_not_entitled",
                "governance": self._governance(),
            }

        if require_usage:
            usage_result = self.feature(
                organization_id,
                result.get("feature"),
                require_usage=True,
            )
            if not usage_result.get("allowed"):
                usage_result["capability_id"] = capability_id
                return usage_result

        return {
            "allowed": True,
            "capability_id": capability_id,
            "feature": result.get("feature"),
            "plan": result.get("plan"),
            "reason": "commercial_policy_allowed",
            "governance": self._governance(),
        }

    @staticmethod
    def _governance():
        return {
            "read_only": True,
            "advisory": True,
            "external_execution": False,
            "database_mutation": False,
            "payment_execution": False,
            "auto_execute": False,
        }

    @classmethod
    def _blocked(cls, reason, **extra):
        return {
            "allowed": False,
            "reason": reason,
            **extra,
            "governance": cls._governance(),
        }


monetization_guard = MonetizationGuard()
