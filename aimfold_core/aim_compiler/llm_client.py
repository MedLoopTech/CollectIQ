"""Model-independent LLM client interface for the Aim Compiler.

AIMFOLD_MASTER_GOAL.md section 27 (Model Independence) requires core logic
not depend on one AI provider, and section 28 (Deterministic Before AI)
says use AI only where interpretation genuinely adds value. Aim compilation
is exactly that kind of task, so it needs a real model — but this repo has
no AI provider credentials configured, and none should be fabricated. Every
class below is either a deterministic stand-in used by tests, or a thin
adapter that raises clearly if the credential it needs isn't present.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: float | None = None


class LLMClient(ABC):
    """Anything that can turn (system_prompt, user_prompt) into text."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse: ...


class StubLLMClient(LLMClient):
    """Deterministic, no-network client for tests and local development.

    NOT a real compiler — it recognizes a small set of canned intents
    (used by tests/test_compiler.py) and otherwise raises, so it fails
    loudly instead of silently returning something misleading in a real
    deployment that forgot to configure a provider.
    """

    def __init__(self, canned_responses: dict[str, str]):
        self._canned = canned_responses

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        for key, response_text in self._canned.items():
            if key in user_prompt:
                return LLMResponse(text=response_text, provider="stub", model="stub-deterministic")
        raise NotImplementedError(
            "StubLLMClient has no canned response for this prompt. It exists only to make "
            "compiler.py's parsing/validation/retry logic testable without a real API key — "
            "wire up AnthropicLLMClient (or another real LLMClient) for actual compilation."
        )


class AnthropicLLMClient(LLMClient):
    """Real provider adapter. Requires the `anthropic` package and an
    ANTHROPIC_API_KEY — raises immediately if either is missing rather than
    silently falling back to something fake."""

    def __init__(self, model: str = "claude-sonnet-5", api_key: str | None = None):
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. The Aim Compiler needs a real model to "
                "interpret user intent — set this env var (or pass api_key=) before using "
                "AnthropicLLMClient. Falling back to StubLLMClient would silently produce "
                "canned, non-real compilations, which this codebase avoids on purpose."
            )
        try:
            import anthropic  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The `anthropic` package is not installed. Add it to requirements.txt and "
                "`pip install -r aimfold_core/aim_compiler/requirements.txt`."
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return LLMResponse(
            text=text,
            provider="anthropic",
            model=self._model,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
        )


class GeminiLLMClient(LLMClient):
    """Google Gemini adapter, same shape as AnthropicLLMClient.

    Default model is `gemini-flash-latest`, not a pinned version like
    `gemini-2.5-flash` — carried over from a sibling project's env
    (sehat90) where pinned 1.5/2.5-flash model ids were retired out from
    under that API key. Using the `-latest` alias avoids repeating that."""

    def __init__(self, model: str = "gemini-flash-latest", api_key: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Set this env var (or pass api_key=) before using "
                "GeminiLLMClient — no key is fabricated or reused from another project "
                "automatically."
            )
        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "The `google-genai` package is not installed. Add it to requirements.txt and "
                "`pip install -r aimfold_core/aim_compiler/requirements.txt`."
            ) from exc
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> LLMResponse:
        response = self._client.models.generate_content(
            model=self._model,
            contents=user_prompt,
            config={"system_instruction": system_prompt},
        )
        usage = getattr(response, "usage_metadata", None)
        return LLMResponse(
            text=response.text,
            provider="gemini",
            model=self._model,
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
        )


def build_llm_client_from_env() -> LLMClient:
    """Provider switch driven by AI_PROVIDER, same convention sehat90 uses
    (its memory: "Provider abstraction (Anthropic prod / Gemini test via
    AI_PROVIDER)"). Defaults to anthropic if unset."""
    provider = os.environ.get("AI_PROVIDER", "anthropic").strip().lower()
    if provider == "gemini":
        return GeminiLLMClient()
    if provider == "anthropic":
        return AnthropicLLMClient()
    raise RuntimeError(f"Unknown AI_PROVIDER={provider!r} — expected 'anthropic' or 'gemini'.")
