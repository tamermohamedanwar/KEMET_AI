from __future__ import annotations

from app.config.settings import AI_PROVIDER
from app.core.ai_federation import ai_federation
from app.core.execution_telemetry import execution_telemetry
from app.core.federation_policy import federation_policy
from app.core.provider_adapters import build_provider_adapters
from app.core.provider_contracts import ProviderConfigurationError, ProviderRequest, ProviderResponse, ProviderUnavailable
from app.core.provider_health import provider_health
from app.core.provider_resilience import provider_resilience
from app.core.provider_router import ProviderRouter
from app.core.provider_usage_telemetry import provider_usage_telemetry
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openrouter_provider import OpenRouterProvider


_LEGACY_PROVIDERS = {"ollama": OllamaProvider, "gemini": GeminiProvider, "openrouter": OpenRouterProvider}


def get_provider():
    provider_name = AI_PROVIDER.lower()
    if provider_name in _LEGACY_PROVIDERS:
        return _LEGACY_PROVIDERS[provider_name]()
    if provider_name == "federated":
        raise RuntimeError("Use get_federated_provider() for the federated contract")
    raise ValueError(f"Unknown provider: {AI_PROVIDER}")


def get_federated_provider(*, preferred: str | None = None, required_capabilities=(), organization_id=None, model: str | None = None):
    policy = federation_policy.for_organization(organization_id)
    decision = ProviderRouter(ai_federation, provider_health).decide(
        required_capabilities, preferred=preferred, require_configured=True, policy=policy, model=model)
    adapter = build_provider_adapters().get(decision.provider_id)
    if adapter is None:
        raise LookupError(f"No adapter registered for provider: {decision.provider_id}")
    return adapter, decision


def federated_generate(prompt: str, *, system: str | None = None, context=(), model: str | None = None,
                       preferred: str | None = None, required_capabilities=(), organization_id=None) -> ProviderResponse:
    policy = federation_policy.for_organization(organization_id)
    required = frozenset(set(required_capabilities) | set(policy.required_capabilities))
    if model and not policy.model_allowed(model):
        raise ProviderConfigurationError("Requested model is not allowed by the organization federation policy")
    adapters = build_provider_adapters()
    router = ProviderRouter(ai_federation, provider_health)
    attempted: set[str] = set()
    last_error: Exception | None = None
    while len(attempted) < len(adapters):
        try:
            decision = router.decide(required, preferred=preferred, require_configured=True, policy=policy, model=model)
        except LookupError:
            if last_error is not None:
                raise last_error
            raise
        if decision.provider_id in attempted:
            break
        attempted.add(decision.provider_id)
        adapter = adapters.get(decision.provider_id)
        if adapter is None:
            provider_health.record_failure(decision.provider_id, "adapter_missing")
            preferred = None
            continue
        effective_model = decision.model_id or model or policy.default_model
        request = ProviderRequest(prompt=prompt, system=system, context=tuple(context), model=effective_model,
                                  required_capabilities=required,
                                  metadata={"routing_provider": decision.provider_id, "routing_reason": decision.reason,
                                            "routing_model": effective_model, "organization_id": str(organization_id) if organization_id is not None else None})
        try:
            request_started = __import__("time").perf_counter()
            with execution_telemetry.span("kemet.provider.request", attributes={
                "kemet.provider_id": decision.provider_id, "kemet.provider_reason": decision.reason,
                "kemet.provider_model": effective_model or "default",
                "kemet.required_capabilities": ",".join(sorted(required)),
                "kemet.organization_id": str(organization_id) if organization_id is not None else "",
            }) as span:
                result = adapter.generate(request)
                latency_ms = (__import__("time").perf_counter() - request_started) * 1000
                provider_health.record_success(result.provider_id, latency_ms=latency_ms)
                observed_cost = result.metadata.get("cost_usd") if result.metadata else None
                provider_usage_telemetry.record_success(result.provider_id, latency_ms=latency_ms, input_tokens=result.input_tokens, output_tokens=result.output_tokens, total_tokens=result.total_tokens, observed_cost_usd=observed_cost)
                span.set_attribute("gen_ai.provider.name", result.provider_id)
                span.set_attribute("gen_ai.request.model", result.model or effective_model or "default")
                span.set_attribute("gen_ai.usage.input_tokens", result.input_tokens)
                span.set_attribute("gen_ai.usage.output_tokens", result.output_tokens)
                span.set_attribute("gen_ai.usage.total_tokens", result.total_tokens)
                execution_telemetry.event("provider.completed", attributes={"provider_id": result.provider_id,
                    "model": result.model or "", "total_tokens": result.total_tokens,
                    "organization_id": str(organization_id) if organization_id is not None else ""})
                return result
        except (ProviderUnavailable, ProviderConfigurationError) as exc:
            provider_usage_telemetry.record_failure(decision.provider_id, latency_ms=(__import__("time").perf_counter() - request_started) * 1000)
            failure_class = provider_resilience.classify_failure(exc)
            retry_after = getattr(exc, "retry_after", None)
            provider_resilience.penalize(decision.provider_id, failure_class, retry_after)
            provider_health.record_failure(decision.provider_id, exc, cooldown_seconds=retry_after)
            last_error = exc
            preferred = None
    if last_error is not None:
        raise last_error
    raise LookupError("No healthy configured provider adapter is available")
