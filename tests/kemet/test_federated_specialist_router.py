import pytest

from app.core.federation.federated_specialist_router import FederatedSpecialistRouter
from app.core.federation_policy import FederationPolicy


class HealthyRegistry:
    def is_healthy(self, provider_id):
        return True


def test_router_merges_policy_required_capabilities():
    router = FederatedSpecialistRouter(health=HealthyRegistry())
    policy = FederationPolicy(
        organization_id=1,
        required_capabilities=frozenset({"research"}),
        allowed_providers=frozenset({"manus"}),
    )
    decision = router.decide(
        {"research"}, policy=policy, verified={"manus"}
    )
    assert decision.provider_id == "manus"
    assert decision.authority == "governed_submission"
    assert decision.policy_requirements == ("research",)


def test_router_honors_preferred_provider():
    router = FederatedSpecialistRouter(health=HealthyRegistry())
    decision = router.decide(
        {"reasoning"}, preferred="meta", verified={"meta"}
    )
    assert decision.provider_id == "meta"
    assert decision.reason == "capability_policy_match"


def test_router_rejects_unverified_specialist():
    router = FederatedSpecialistRouter(health=HealthyRegistry())
    with pytest.raises(LookupError, match="policy and requested capabilities"):
        router.decide({"research"}, verified=set())


def test_router_never_grants_external_execution_authority():
    router = FederatedSpecialistRouter(health=HealthyRegistry())
    decision = router.decide({"research"}, verified={"manus"})
    assert decision.authority == "governed_submission"
    assert decision.provider_id != "kemet"
