import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from . import mock
from .config import settings

T = TypeVar("T", bound=BaseModel)

# USD per million tokens (input, output). Used only for the on-screen cost estimate.
PRICING = {
    "claude-haiku-5-5": (1.0, 5.0),
    "claude-sonnet-5-5": (3.0, 15.0),
}


class BudgetExceeded(Exception):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    searches: int = 0
    cost_usd: float = 0.0
    by_stage: dict = field(default_factory=dict)

    def add(self, stage: str, model: str, tin: int, tout: int) -> None:
        pin, pout = PRICING.get(model, (0.0, 0.0))  # free-tier providers are not priced
        cost = (tin * pin + tout * pout) / 1_000_000
        self.input_tokens += tin
        self.output_tokens += tout
        self.calls += 1
        self.cost_usd += cost
        s = self.by_stage.setdefault(stage, {"tokens": 0, "cost_usd": 0.0, "calls": 0})
        s["tokens"] += tin + tout
        s["cost_usd"] = round(s["cost_usd"] + cost, 6)
        s["calls"] += 1

    def as_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "calls": self.calls,
            "searches": self.searches,
            "cost_usd": round(self.cost_usd, 5),
            "by_stage": self.by_stage,
        }


_client = None


def _anthropic():
    global _client
    if _client is None:
        from anthropic import AsyncAnthropic

        _client = AsyncAnthropic(api_key=settings.anthropic_api_key, max_retries=3)
    return _client


# Gemini "thinking" dominates latency. Verification is where accuracy is decided, so it gets more of it.
# Only Gemini accepts reasoning_effort; other providers would reject it.
EFFORT = {"plan": "none", "analyze": "low", "write": "low", "single": "low", "verify": "medium", "revise": "low", "ask": "low"}

# Free-tier quotas are per model per day, so each stage walks a chain of (provider, model) and moves on
# when one is used up. Cheap models handle simple steps; accuracy-critical steps never use "lite" models.
STRONG = {"gemini": ["gemini-3.5-flash", "gemini-3-flash-preview"], "groq": ["openai/gpt-oss-120b"]}
CHEAP = {"gemini": ["gemini-3.5-flash-lite"], "groq": ["openai/gpt-oss-20b"]}
STRONG_STAGES = {"analyze", "write", "single", "verify", "ask"}
# Document Q&A goes to Groq first so Gemini's small daily quota is kept for research runs.
GROQ_FIRST = {"ask"}
_exhausted: set[tuple[str, str]] = set()


def _chain(stage: str) -> list[tuple[str, str]]:
    tiers = [STRONG] if stage in STRONG_STAGES else [CHEAP, STRONG]
    providers = settings.compat_providers
    if stage in GROQ_FIRST:
        providers = sorted(providers, key=lambda p: p != "groq")
    chain = [(p, m) for tier in tiers for p in providers for m in tier[p]]
    live = [c for c in chain if c not in _exhausted]
    return live or chain


async def _openai_compat(stage: str, system: str, messages: list[dict]) -> tuple[str, int, int]:
    """Chat call for Gemini/Groq via their OpenAI-compatible endpoints.

    Retries per-minute rate limits and stalls; skips to the next model/provider when a daily quota is exhausted.
    """
    from .config import PROVIDERS

    effort = EFFORT.get(stage)
    last = "no attempt made"
    async with httpx.AsyncClient(timeout=90) as client:
        for provider, model in _chain(stage):
            headers = {"Authorization": f"Bearer {settings.key_for(provider)}"}
            url = f"{PROVIDERS[provider]['base_url']}/chat/completions"
            body = {
                "model": model,
                # Groq's free tier counts requested output against a small per-minute token limit.
                "max_tokens": min(settings.max_output_tokens, 3500) if provider == "groq" else settings.max_output_tokens,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, *messages],
            }
            if effort and provider == "gemini" and "lite" not in model:
                body["reasoning_effort"] = effort
            elif effort and provider == "groq":
                body["reasoning_effort"] = "low" if effort == "none" else effort  # gpt-oss has no "none"
            for attempt in range(5):
                try:
                    r = await client.post(url, headers=headers, json=body)
                except httpx.TimeoutException:
                    last = f"{model} timed out"
                    continue
                daily = r.status_code == 429 and ("PerDay" in r.text or "per day" in r.text.lower() or "tokens per day" in r.text.lower())
                if daily:
                    _exhausted.add((provider, model))
                    last = f"{provider}/{model} daily free quota used up"
                    break  # next model or provider
                if r.status_code == 413:
                    last = f"{provider}/{model} request too large for its free per-minute token limit"
                    break  # this model cannot take it; try the next one
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"{provider}/{model} busy (HTTP {r.status_code})"
                    wait = float(r.headers.get("retry-after") or min(3 * 2**attempt, 30))
                    await asyncio.sleep(min(wait, 30))
                    continue
                if r.status_code == 400 and "reasoning_effort" in body:
                    del body["reasoning_effort"]  # this model does not support it
                    continue
                if r.status_code >= 400:
                    raise RuntimeError(f"{provider} API error {r.status_code}: {r.text[:300]}")
                data = r.json()
                usage = data.get("usage") or {}
                text = data["choices"][0]["message"]["content"] or ""
                return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    raise RuntimeError(f"All free providers unavailable ({last}). Daily quotas reset every 24h; add a Groq key for more headroom.")


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


async def call_json(
    stage: str,
    system: str,
    user: str,
    schema: type[T],
    usage: Usage,
    model: str | None = None,
    mock_ctx: dict | None = None,
) -> T:
    """Run one structured LLM call. In mock mode, returns canned data instead."""
    model = model or settings.fast_model

    if settings.mock_llm:
        return schema.model_validate(mock.respond(stage, mock_ctx or {}))

    spec = json.dumps(schema.model_json_schema())
    full_system = (
        f"{system}\n\nRespond with ONLY a single JSON object that matches this JSON schema. "
        f"No prose, no markdown fences.\nSchema: {spec}"
    )
    messages = [{"role": "user", "content": user}]
    last_err: Exception | None = None
    for _ in range(2):
        if settings.provider == "anthropic":
            resp = await _anthropic().messages.create(
                model=model,
                max_tokens=settings.max_output_tokens,
                system=full_system,
                messages=messages,
            )
            tin, tout = resp.usage.input_tokens, resp.usage.output_tokens
            text = "".join(b.text for b in resp.content if b.type == "text")
        else:
            text, tin, tout = await _openai_compat(stage, full_system, messages)
        usage.add(stage, model, tin, tout)
        try:
            return schema.model_validate(_extract_json(text))
        except (ValueError, ValidationError) as e:
            last_err = e
            messages = [
                {"role": "user", "content": user},
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That was not valid. Fix it and return only JSON. Error: {e}"},
            ]
    raise RuntimeError(f"{stage}: model returned invalid JSON twice: {last_err}")
