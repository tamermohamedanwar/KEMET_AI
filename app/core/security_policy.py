from dataclasses import dataclass
from datetime import datetime, timezone


class PolicyDenied(PermissionError):
    pass


@dataclass(frozen=True)
class PolicyGrant:
    subject_id: str
    organization_id: int
    actions: tuple[str, ...]
    resources: tuple[str, ...]
    expires_at: datetime | None = None

    def allows(self, action: str, resource: str, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if self.expires_at and now >= self.expires_at:
            return False
        return action in self.actions and resource in self.resources


class AuthorizationPolicyEngine:
    VERSION = "1.0"

    def authorize(self, *, grant: PolicyGrant | None, subject_id: str, organization_id: int,
                  action: str, resource: str, now: datetime | None = None):
        if grant is None:
            raise PolicyDenied("authorization_grant_required")
        if grant.subject_id != str(subject_id):
            raise PolicyDenied("subject_mismatch")
        if grant.organization_id != int(organization_id):
            raise PolicyDenied("organization_scope_mismatch")
        if not grant.allows(action, resource, now):
            raise PolicyDenied("policy_denied")
        return {"authorized": True, "policy_version": self.VERSION, "action": action, "resource": resource}


security_policy = AuthorizationPolicyEngine()
