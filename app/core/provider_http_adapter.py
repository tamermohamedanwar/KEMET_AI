from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import requests

from app.core.provider_adapter import ProviderAdapter
from app.core.governed_http import governed_request
from app.core.provider_contracts import (
    ProviderConfigurationError,
    ProviderRequest,
    ProviderResponse,
    ProviderUnavailable,
)


class ResponsesAPIAdapter(ProviderAdapter):
    def __init__(self, provider_id: str, base_url: str, api_key_env: str, default_model: str):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.default_model = default_model
        host = urlparse(self.base_url).hostname
        if not host:
            raise ValueError("provider_base_url_hostname_required")
        self._endpoint = f"{self.base_url}/responses"

    def _input(self, request: ProviderRequest) -> list[dict[str, Any]] | str:
        items: list[dict[str, Any]] = []
        if request.system:
            items.append({"role": "developer", "content": request.system})
        for item in request.context:
            if item.get("role") in {"user", "assistant", "developer"} and "content" in item:
                items.append({"role": str(item["role"]), "content": str(item["content"])})
        items.append({"role": "user", "content": request.prompt})
        return items

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderConfigurationError(f"{self.provider_id} credentials are not configured")
        model = request.model or self.default_model
        try:
            response = governed_request("POST", 
                self._endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "input": self._input(request), "store": False},
                timeout=120,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retry_after = None
            if getattr(exc, "response", None) is not None:
                try:
                    retry_after = float(exc.response.headers.get("Retry-After"))
                except (TypeError, ValueError):
                    retry_after = None
            raise ProviderUnavailable(f"{self.provider_id} request failed", status_code=status, retry_after=retry_after) from exc
        usage = data.get("usage") or {}
        content = str(data.get("output_text") or _extract_output_text(data.get("output")))
        return ProviderResponse(
            content=content,
            provider_id=self.provider_id,
            model=data.get("model", model),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            request_id=data.get("id"),
            finish_reason=data.get("status"),
        )


class ChatCompletionsAdapter(ProviderAdapter):
    def __init__(self, provider_id: str, base_url: str, api_key_env: str, default_model: str):
        self.provider_id = provider_id
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.default_model = default_model
        host = urlparse(self.base_url).hostname
        if not host:
            raise ValueError("provider_base_url_hostname_required")
        self._endpoint = f"{self.base_url}/chat/completions"

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise ProviderConfigurationError(f"{self.provider_id} credentials are not configured")
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for item in request.context:
            if item.get("role") in {"user", "assistant", "system"} and "content" in item:
                messages.append({"role": str(item["role"]), "content": str(item["content"])})
        messages.append({"role": "user", "content": request.prompt})
        model = request.model or self.default_model
        payload = {"model": model, "messages": messages}
        try:
            response = governed_request(
                "POST", self._endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload, timeout=120, allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retry_after = None
            if getattr(exc, "response", None) is not None:
                try:
                    retry_after = float(exc.response.headers.get("Retry-After"))
                except (TypeError, ValueError):
                    retry_after = None
            raise ProviderUnavailable(f"{self.provider_id} request failed", status_code=status, retry_after=retry_after) from exc
        choices = data.get("choices") or []
        message = choices[0].get("message") if choices and isinstance(choices[0], dict) else {}
        content = str((message or {}).get("content", ""))
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("prompt_tokens", 0) or 0)
        output_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", input_tokens + output_tokens) or 0)
        finish_reason = choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None
        return ProviderResponse(
            content=content, provider_id=self.provider_id, model=data.get("model", model),
            input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens,
            request_id=data.get("id"), finish_reason=finish_reason,
        )


class AnthropicAdapter(ProviderAdapter):
    provider_id = "anthropic"

    def __init__(self, default_model: str = "claude-sonnet-4-5"):
        self.default_model = default_model

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ProviderConfigurationError("anthropic credentials are not configured")
        messages: list[dict[str, Any]] = []
        for item in request.context:
            if item.get("role") in {"user", "assistant"} and "content" in item:
                messages.append({"role": item["role"], "content": item["content"]})
        messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if request.system:
            payload["system"] = request.system
        try:
            endpoint = "https://api.anthropic.com/v1/messages"
            response = governed_request("POST", 
                endpoint,
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json=payload,
                timeout=120,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retry_after = None
            if getattr(exc, "response", None) is not None:
                try:
                    retry_after = float(exc.response.headers.get("Retry-After"))
                except (TypeError, ValueError):
                    retry_after = None
            raise ProviderUnavailable("anthropic request failed", status_code=status, retry_after=retry_after) from exc
        content = "".join(str(part.get("text", "")) for part in data.get("content", []) if part.get("type") == "text")
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("input_tokens", 0) or 0)
        output_tokens = int(usage.get("output_tokens", 0) or 0)
        return ProviderResponse(
            content=content,
            provider_id=self.provider_id,
            model=data.get("model", payload["model"]),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            request_id=data.get("id"),
            finish_reason=data.get("stop_reason"),
        )


class GoogleInteractionsAdapter(ProviderAdapter):
    provider_id = "google"

    def __init__(self, default_model: str = "gemini-3.8-flash"):
        self.default_model = default_model

    def generate(self, request: ProviderRequest) -> ProviderResponse:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ProviderConfigurationError("google credentials are not configured")
        input_value: Any = request.prompt
        if request.context:
            input_value = [
                {"role": item["role"], "content": str(item["content"])}
                for item in request.context
                if item.get("role") in {"user", "model", "assistant"} and "content" in item
            ] + [{"role": "user", "content": request.prompt}]
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "input": input_value,
            "store": False,
        }
        if request.system:
            payload["system_instruction"] = request.system
        try:
            endpoint = "https://generativelanguage.googleapis.com/v1beta/interactions"
            response = governed_request("POST", 
                endpoint,
                headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                json=payload,
                timeout=120,
                allow_redirects=False,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retry_after = None
            if getattr(exc, "response", None) is not None:
                try:
                    retry_after = float(exc.response.headers.get("Retry-After"))
                except (TypeError, ValueError):
                    retry_after = None
            raise ProviderUnavailable("google request failed", status_code=status, retry_after=retry_after) from exc
        usage = data.get("usage") or {}
        content = str(data.get("output_text") or _extract_interaction_steps(data.get("steps")))
        return ProviderResponse(
            content=content,
            provider_id=self.provider_id,
            model=data.get("model", payload["model"]),
            input_tokens=int(usage.get("total_input_tokens", 0) or 0),
            output_tokens=int(usage.get("total_output_tokens", 0) or 0),
            total_tokens=int(usage.get("total_tokens", 0) or 0),
            request_id=data.get("id"),
            finish_reason=data.get("status"),
        )


def _extract_output_text(output: Any) -> str:
    parts: list[str] = []
    for item in output or []:
        for part in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(part, dict) and part.get("type") in {"output_text", "text"}:
                parts.append(str(part.get("text", "")))
    return "".join(parts)


def _extract_interaction_text(outputs: Any) -> str:
    parts: list[str] = []
    for item in outputs or []:
        if isinstance(item, dict):
            parts.append(str(item.get("text", "")))
    return "".join(parts)


def _extract_interaction_steps(steps: Any) -> str:
    parts: list[str] = []
    for step in steps or []:
        for item in step.get("content", []) if isinstance(step, dict) else []:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
    return "".join(parts)
