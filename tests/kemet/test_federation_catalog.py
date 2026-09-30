from app.core.ai_federation import ai_federation
from app.core.provider_router import ProviderRouter


def test_global_provider_catalog_includes_meta_and_manus():
    snapshot = {item["provider_id"]: item for item in ai_federation.routing_snapshot()}
    assert {"openai", "anthropic", "google", "xai", "meta", "manus"}.issubset(snapshot)
    assert snapshot["meta"]["execution_ready"] is False
    assert snapshot["manus"]["execution_ready"] is False


def test_catalog_only_providers_never_become_execution_routes():
    decision = ProviderRouter().decide({"agentic"})
    assert decision.provider_id not in {"meta", "manus"}


def test_unready_provider_cannot_be_selected_even_when_preferred():
    decision = ProviderRouter().decide({"agentic"}, preferred="manus")
    assert decision.provider_id != "manus"
