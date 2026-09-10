from __future__ import annotations

from copy import deepcopy

from app.workforce.profiles import WORKFORCE_PROFILES


class WorkforceRegistry:
    def __init__(self, profiles=None):
        self._profiles = dict(
            profiles or WORKFORCE_PROFILES
        )

    def exists(self, workforce_id: str) -> bool:
        key = str(workforce_id or "").strip().lower()
        return key in self._profiles

    def get(self, workforce_id: str):
        key = str(workforce_id or "").strip().lower()
        profile = self._profiles.get(key)

        if profile is None:
            return None

        result = deepcopy(profile)
        result["id"] = key
        result["status"] = "ready"
        return result

    def list(self):
        return [
            {
                "id": workforce_id,
                "name": profile.get("name", workforce_id),
                "role": profile.get("role", ""),
                "description": profile.get("description", ""),
                "industries": list(
                    profile.get("industries", [])
                ),
                "status": "ready",
            }
            for workforce_id, profile
            in self._profiles.items()
        ]

    def for_industry(self, industry_id: str):
        industry = str(
            industry_id or ""
        ).strip().lower()

        return [
            self.get(workforce_id)
            for workforce_id, profile
            in self._profiles.items()
            if industry in profile.get("industries", [])
        ]

    def allowed_actions(self, workforce_id: str):
        profile = self.get(workforce_id)
        return (
            profile.get("allowed_actions", [])
            if profile else []
        )

    def capabilities(self, workforce_id: str):
        profile = self.get(workforce_id)
        return (
            profile.get("capabilities", [])
            if profile else []
        )

    def approval_actions(self, workforce_id: str):
        profile = self.get(workforce_id)
        return (
            profile.get("approval_actions", [])
            if profile else []
        )

    def can_execute(
        self,
        workforce_id: str,
        action: str,
    ) -> bool:
        return action in self.allowed_actions(
            workforce_id
        )


workforce_registry = WorkforceRegistry()
