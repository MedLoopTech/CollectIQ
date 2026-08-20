"""Deterministic model-cost estimation — AIMFOLD_MASTER_GOAL.md section 35
(Cost Intelligence): "Every paid acquisition or AI operation should be
attributable where practical." No AI call here, on purpose — a lookup
table and arithmetic, same "Deterministic Before AI" reasoning (section
28) as every other rollup/analytics module in this codebase.

Rate table checked 2026-08-20 against public provider pricing pages (USD
per 1,000,000 tokens):

  - Gemini 2.5 Flash-Lite (what `gemini-flash-lite-latest` resolves to
    today): $0.10 input / $0.40 output.
  - Gemini 2.5 Flash (what `gemini-flash-latest` resolves to today):
    $0.15 input / $1.25 output.
  - Claude Sonnet 5 (Anthropic's default model in this codebase's
    AnthropicLLMClient): $2.00 input / $10.00 output.

These are **-latest aliases and a point-in-time snapshot, not a live
feed** — Google has already announced retiring the Gemini 2.5 line on
2026-10-16, after which `gemini-flash-lite-latest`/`gemini-flash-latest`
will silently resolve to different (and differently-priced) models this
table will be wrong for. `estimate_model_cost()` returns None rather than
a stale/guessed number for anything not in RATE_TABLE below — a caller
that needs the rate table current for billing accuracy must update it
deliberately, not rely on this module noticing on its own.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenRate:
    input_usd_per_million: float
    output_usd_per_million: float


RATE_TABLE: dict[tuple[str, str], TokenRate] = {
    ("gemini", "gemini-flash-lite-latest"): TokenRate(0.10, 0.40),
    ("gemini", "gemini-flash-latest"): TokenRate(0.15, 1.25),
    ("anthropic", "claude-sonnet-5"): TokenRate(2.00, 10.00),
}


def estimate_model_cost(
    provider: str, model: str, input_tokens: int | None, output_tokens: int | None
) -> float | None:
    """Returns None (not 0.0, not a guess) when the (provider, model)
    pair isn't in RATE_TABLE, or when either token count is missing —
    both are "unknown", not "free"."""

    rate = RATE_TABLE.get((provider, model))
    if rate is None or input_tokens is None or output_tokens is None:
        return None
    cost = (input_tokens / 1_000_000) * rate.input_usd_per_million
    cost += (output_tokens / 1_000_000) * rate.output_usd_per_million
    return round(cost, 8)


__all__ = ["TokenRate", "RATE_TABLE", "estimate_model_cost"]
