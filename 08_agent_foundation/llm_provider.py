"""Provider-agnostic OpenAI-compatible LLM adapter for CollectIQ agents.

DeepSeek is supported through its OpenAI-compatible chat-completions API.
No financial calculation should be delegated to this module; agents receive structured facts
from deterministic CollectIQ services and use the model for interpretation/drafting only.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


def load_model_config(provider: str | None = None) -> ModelConfig:
    provider = (provider or os.getenv("COLLECTIQ_LLM_PROVIDER", "deepseek")).lower().strip()

    if provider == "deepseek":
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is required when provider=deepseek")
        return ModelConfig(
            provider="deepseek",
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"),
            api_key=key,
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )

    # Generic OpenAI-compatible provider. This covers OpenAI-compatible gateways or fallbacks
    # without coupling agent business logic to one vendor SDK surface.
    key = os.environ.get("LLM_API_KEY", "")
    if not key:
        raise RuntimeError("LLM_API_KEY is required for a generic provider")
    return ModelConfig(
        provider=provider,
        model=os.getenv("LLM_MODEL", ""),
        api_key=key,
        base_url=os.getenv("LLM_BASE_URL") or None,
    )


class LLMProvider:
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or load_model_config()
        kwargs: dict[str, Any] = {"api_key": self.config.api_key}
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
        self.client = OpenAI(**kwargs)

    def json_completion(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        temperature: float = 0.1,
        max_tokens: int = 1800,
    ) -> dict[str, Any]:
        """Return strict JSON plus lightweight run metadata.

        Prompts must explicitly request JSON because some OpenAI-compatible providers require
        the prompt and response_format to agree.
        """
        started = time.perf_counter()
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, default=str)},
            ],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        message = response.choices[0].message.content or "{}"
        data = json.loads(message)
        usage = getattr(response, "usage", None)
        return {
            "data": data,
            "run": {
                "provider": self.config.provider,
                "model": self.config.model,
                "request_id": getattr(response, "id", None),
                "latency_ms": latency_ms,
                "input_tokens": getattr(usage, "prompt_tokens", None) if usage else None,
                "output_tokens": getattr(usage, "completion_tokens", None) if usage else None,
            },
        }
