from dataclasses import asdict, dataclass
from typing import Any

from app.core.ai_federation import ai_federation
from app.core.federation_policy import federation_policy
from app.core.federation.specialist_registry import specialist_registry
from app.core.federation.capability_federation import capability_federation
from app.core.federation.federated_specialist_router import FederatedSpecialistRouter
from app.core.provider_health import provider_health
from app.core.provider_router import ProviderRouter
from app.core.task_classifier import classify_task


@dataclass(frozen=True)
class RoutingPreview:
    task_type: str
    capabilities: tuple[str, ...]
    risk: str
    confidence: float
    provider: dict[str, Any] | None
    specialist: dict[str, Any] | None
    approval_required: bool
    execution_allowed: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FederationRoutingPreviewService:
    VERSION = "1.0"

    def preview(self, prompt: str, *, organization_id: int,
                verified_provider_ids: set[str] | None = None) -> RoutingPreview:
        text = (prompt or "").strip()
        if not text:
            raise ValueError("prompt_required")
        if organization_id <= 0:
            raise ValueError("organization_id_required")
        classification = classify_task(text)
        policy = federation_policy.for_organization(organization_id)
        verified = verified_provider_ids or set()
        allowed_verified = {p for p in verified if policy.provider_allowed(p)}
        provider = self._provider_preview(classification, policy, allowed_verified)
        specialist = self._specialist_preview(classification, policy, allowed_verified)
        execution_allowed = bool(provider or specialist)
        approval_required = classification.risk == "high" or classification.task_type == "automation"
        return RoutingPreview(
            classification.task_type,
            tuple(sorted(classification.capabilities)),
            classification.risk,
            classification.confidence,
            provider,
            specialist,
            approval_required,
            execution_allowed,
        )

    def _provider_preview(self, classification, policy, verified: set[str]):
        router = ProviderRouter()
        required = classification.capabilities
        candidates = []
        for profile in ai_federation.all():
            if profile.provider_id not in verified:
                continue
            if not profile.enabled or not profile.execution_ready:
                continue
            if not profile.supports(required) or not provider_health.is_healthy(profile.provider_id):
                continue
            if not policy.provider_allowed(profile.provider_id):
                continue
            candidates.append(profile)
        capability_route = capability_federation.route(
            required, verified=verified, preferred=policy.preferred_provider
        )
        if not candidates or not capability_route.get("selected"):
            return None
        selected_provider = capability_route["selected"]["provider_id"]
        if selected_provider not in verified:
            return None
        try:
            decision = router.decide(
                required,
                preferred=selected_provider,
                require_configured=True,
                policy=policy,
            )
            if decision.provider_id != selected_provider:
                return None
        except LookupError:
            return None
        return {
            "provider_id": decision.provider_id,
            "model_id": decision.model_id,
            "reason": decision.reason,
            "model_reason": decision.model_reason,
            "candidate_count": len(candidates),
            "capability_route": capability_route,
        }

    def _specialist_preview(self, classification, policy, verified: set[str]):
        try:
            decision = FederatedSpecialistRouter().decide(
                classification.capabilities,
                preferred=policy.preferred_provider,
                policy=policy,
                verified=verified,
            )
        except LookupError:
            return None
        return {
            "provider_id": decision.provider_id,
            "execution_kind": decision.execution_kind,
            "capabilities": list(decision.capabilities),
            "reason": decision.reason,
            "authority": decision.authority,
            "approval_required": decision.approval_required,
            "policy_requirements": list(decision.policy_requirements),
        }


federation_routing_preview = FederationRoutingPreviewService()
