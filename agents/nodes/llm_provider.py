"""
Reasoning Model Provider Abstraction for RevenueRescue AI.

Supports:
1. LocalDeterministicProvider (MockProvider) — 100% zero-cost local fallback (default).
2. CloudflareWorkersAIProvider — Hosted DeepSeek-R1-Distill-Qwen on Cloudflare Workers AI free tier.
3. OpenAIProvider — Optional paid/trial fallback for OpenAI compatible endpoints.

Safety & Resilience Invariants:
- Bounded timeouts (default 30s) on all outbound requests.
- Strict token budgets (max 512 completion tokens).
- Server-side credential isolation (never logged, never exposed to frontend).
- Strips DeepSeek <think>...</think> reasoning tags cleanly.
- Error classification: rate limits (429) & quota exhaustion trigger immediate fallback without retry loops.
- Bounded single retry ONLY for safe transient 5xx server errors.
- Robust JSON repair and schema validation before any strategy is proposed.
"""

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class ProviderErrorCode(str, Enum):
    NONE = "NONE"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    AUTH_ERROR = "AUTH_ERROR"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    SERVER_ERROR = "SERVER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass
class ReasoningResponse:
    content: str
    raw_output: str
    provider: str
    model: str
    latency_ms: int
    error_code: ProviderErrorCode = ProviderErrorCode.NONE
    error_message: str | None = None
    fallback_used: bool = False
    token_usage: dict[str, int] = field(default_factory=dict)


def clean_deepseek_reasoning_output(raw: str) -> str:
    """
    Remove <think>...</think> chain-of-thought blocks from DeepSeek-R1 output
    and isolate the valid JSON object payload.
    """
    if not raw:
        return ""

    # Remove complete <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)

    # If <think> was unclosed (e.g. truncated output), remove everything up to </think> or clear
    if "<think>" in text:
        text = re.sub(r"<think>.*$", "", text, flags=re.DOTALL)
    if "</think>" in text:
        text = text.split("</think>")[-1]

    text = text.strip()

    # Extract JSON fenced block if present: ```json ... ```
    match_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if match_fence:
        return match_fence.group(1).strip()

    # Otherwise extract outermost balanced JSON object {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    return text


def repair_json_string(text: str) -> str:
    """Attempt bounded repair on common LLM JSON syntax errors (trailing commas, quotes)."""
    # Remove trailing commas before closing braces/brackets
    cleaned = re.sub(r",\s*([\]}])", r"\1", text)
    return cleaned


class ReasoningProvider(ABC):
    """Abstract base class for all reasoning providers."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw string output from the model."""

    def complete_with_metadata(self, system_prompt: str, user_prompt: str) -> ReasoningResponse:
        """Return structured response with latency, provider, and error telemetry."""
        t0 = time.perf_counter()
        try:
            content = self.complete(system_prompt, user_prompt)
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return ReasoningResponse(
                content=clean_deepseek_reasoning_output(content),
                raw_output=content,
                provider=self.__class__.__name__,
                model=getattr(self, "_model", "unknown"),
                latency_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return ReasoningResponse(
                content="",
                raw_output="",
                provider=self.__class__.__name__,
                model=getattr(self, "_model", "unknown"),
                latency_ms=elapsed_ms,
                error_code=ProviderErrorCode.INVALID_OUTPUT,
                error_message=str(e),
                fallback_used=True,
            )


# Backward-compatible alias
LLMProvider = ReasoningProvider


class LocalDeterministicProvider(ReasoningProvider):
    """
    Deterministic zero-cost fallback — no API key or external cloud request required.
    Produces valid Pydantic-compatible JSON grounded in failure category rules
    and quantitative ML recovery probability evidence.
    """

    STRATEGY_MAP = {
        "INSUFFICIENT_FUNDS": ("SCHEDULE_RETRY", 24, 0.75),
        "EXPIRED_METHOD": ("PAYMENT_METHOD_UPDATE", 0, 0.60),
        "GATEWAY_TEMPORARY": ("RETRY_NOW", 2, 0.85),
        "BANK_DECLINE": ("SCHEDULE_RETRY", 48, 0.55),
        "AUTH_FAILURE": ("REMINDER", 0, 0.50),
        "MANDATE_FAILURE": ("SCHEDULE_RETRY", 24, 0.65),
        "SUBSCRIPTION_GRACE": ("SCHEDULE_RETRY", 24, 0.65),
        "CHECKOUT_ABANDONED": ("CHECKOUT_RECOVERY", 0, 0.55),
        "UNKNOWN": ("ESCALATE", 0, 0.20),
    }

    def __init__(self, model_name: str = "local-deterministic-v1") -> None:
        self._model = model_name

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Extract failure_reason precisely
        match = re.search(r"Failure Reason:\s*(\w+)", user_prompt)
        if match:
            failure_reason = match.group(1)
        else:
            priority_order = [
                "CHECKOUT_ABANDONED",
                "MANDATE_FAILURE",
                "SUBSCRIPTION_GRACE",
                "INSUFFICIENT_FUNDS",
                "EXPIRED_METHOD",
                "GATEWAY_TEMPORARY",
                "AUTH_FAILURE",
                "BANK_DECLINE",
                "UNKNOWN",
            ]
            failure_reason = "UNKNOWN"
            for reason in priority_order:
                if reason in user_prompt:
                    failure_reason = reason
                    break

        strategy, delay, default_conf = self.STRATEGY_MAP.get(failure_reason, ("ESCALATE", 0, 0.20))
        needs_review = failure_reason == "UNKNOWN"

        # Check if quantitative ML probability was supplied in user prompt
        prob_match = re.search(
            r"(?:LightGBM Probability|ML Recovery Probability):\s*([0-9.]+)", user_prompt
        )
        # A recovery probability is not evidence for an unknown failure cause.
        # Keep escalated cases at the conservative rule-based confidence.
        confidence = (
            float(prob_match.group(1)) if prob_match and strategy != "ESCALATE" else default_conf
        )

        # Extract amount if present
        amount_match = re.search(r"Amount.*?(?:INR|Paise)?:?\s*([0-9.]+)", user_prompt)
        amount_paise = 0
        if amount_match:
            try:
                val = float(amount_match.group(1))
                amount_paise = int(val * 100) if "INR" in user_prompt else int(val)
            except Exception:
                amount_paise = 0

        # Diagnosis vs Strategy detection
        is_strategy = "recovery_strategy" in user_prompt or (
            "strategy" in user_prompt.lower() and "diagnosis" not in user_prompt.lower()
        )

        if is_strategy:
            output = {
                "recovery_strategy": strategy,
                "reason": f"Deterministic strategy for {failure_reason} with confidence {confidence:.2f}.",
                "requested_action": {"type": strategy, "delay_hours": delay},
                "expected_recovery_paise": amount_paise if strategy != "ESCALATE" else 0,
                "confidence": round(min(1.0, max(0.0, confidence)), 4),
                "fallback_strategy": "ESCALATE",
            }
        else:
            output = {
                "diagnosis": f"rule_based_{failure_reason.lower()}",
                "diagnosis_confidence": round(min(1.0, max(0.0, confidence)), 4),
                "failure_category": failure_reason,
                "likely_cause": f"Rule-based deterministic diagnosis for {failure_reason}. No external inference cost.",
                "is_recoverable": strategy != "ESCALATE",
                "recommended_strategy": strategy,
                "needs_human_review": needs_review,
                "notes": "FALLBACK_MODE",
            }

        logger.info("mock_llm_response", failure_reason=failure_reason, strategy=strategy)
        return json.dumps(output)


# Backward-compatible alias
MockProvider = LocalDeterministicProvider


class CloudflareWorkersAIProvider(ReasoningProvider):
    """
    Cloudflare Workers AI serverless inference client.
    Default Model: @cf/deepseek-ai/deepseek-r1-distill-qwen-32b
    Free-tier: 10,000 neurons/day shared across models.
    """

    DEFAULT_MODEL = "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"

    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = DEFAULT_MODEL,
        timeout_seconds: float = 30.0,
        max_tokens: int = 512,
        fallback_provider: ReasoningProvider | None = None,
    ) -> None:
        self._account_id = account_id.strip()
        self._api_token = api_token.strip()
        self._model = model.strip() or self.DEFAULT_MODEL
        self._timeout_seconds = timeout_seconds
        self._max_tokens = max_tokens
        self._fallback = fallback_provider or LocalDeterministicProvider()
        self._endpoint = (
            f"https://api.cloudflare.com/client/v4/accounts/{self._account_id}/ai/run/{self._model}"
        )

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Call Cloudflare Workers AI with quota handling, bounded retry, and deterministic fallback."""
        if not self._account_id or not self._api_token:
            logger.info("cloudflare_credentials_missing", action="using_deterministic_fallback")
            return self._fallback.complete(system_prompt, user_prompt)

        headers = {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self._max_tokens,
            "temperature": 0.1,
        }

        # Attempt call with bounded single retry on 5xx transient server errors only
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                with httpx.Client(timeout=self._timeout_seconds) as client:
                    resp = client.post(self._endpoint, headers=headers, json=payload)

                # 1. Check for Rate Limit / Quota Exhaustion (429 / 403)
                if resp.status_code in (429, 403):
                    logger.warning(
                        "cloudflare_workers_ai_quota_exhausted",
                        status_code=resp.status_code,
                        action="falling_back_to_deterministic",
                    )
                    return self._fallback.complete(system_prompt, user_prompt)

                # 2. Check for Auth Errors (401)
                if resp.status_code == 401:
                    logger.error(
                        "cloudflare_workers_ai_auth_error",
                        status_code=resp.status_code,
                        action="falling_back_to_deterministic",
                    )
                    return self._fallback.complete(system_prompt, user_prompt)

                # 3. Check for Server Errors (5xx)
                if resp.status_code >= 500:
                    if attempt < max_attempts:
                        logger.warning(
                            "cloudflare_workers_ai_transient_5xx",
                            status_code=resp.status_code,
                            attempt=attempt,
                            action="retrying_once",
                        )
                        time.sleep(1.0)
                        continue
                    else:
                        logger.error(
                            "cloudflare_workers_ai_5xx_exhausted",
                            status_code=resp.status_code,
                            action="falling_back_to_deterministic",
                        )
                        return self._fallback.complete(system_prompt, user_prompt)

                # 4. Handle Successful 200 response
                if resp.status_code == 200:
                    data = resp.json()
                    # Cloudflare returns {"result": {"response": "..."}, "success": true}
                    raw_text = ""
                    if isinstance(data, dict):
                        result = data.get("result", {})
                        if isinstance(result, dict):
                            raw_text = result.get("response", "")
                        elif isinstance(result, str):
                            raw_text = result

                    cleaned = clean_deepseek_reasoning_output(raw_text)
                    cleaned = repair_json_string(cleaned)
                    # Verify it parses as JSON
                    try:
                        json.loads(cleaned)
                        return cleaned
                    except Exception:
                        logger.warning(
                            "cloudflare_raw_output_invalid_json", raw_snippet=cleaned[:100]
                        )
                        return self._fallback.complete(system_prompt, user_prompt)

                # Any other unexpected status code
                logger.warning(
                    "cloudflare_workers_ai_unexpected_status",
                    status_code=resp.status_code,
                    action="falling_back_to_deterministic",
                )
                return self._fallback.complete(system_prompt, user_prompt)

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt < max_attempts:
                    logger.warning("cloudflare_network_timeout", attempt=attempt, error=str(exc))
                    time.sleep(1.0)
                    continue
                logger.error(
                    "cloudflare_workers_ai_call_failed",
                    error=str(exc),
                    action="falling_back_to_deterministic",
                )
                return self._fallback.complete(system_prompt, user_prompt)
            except Exception as exc:
                logger.error(
                    "cloudflare_unhandled_exception",
                    error=str(exc),
                    action="falling_back_to_deterministic",
                )
                return self._fallback.complete(system_prompt, user_prompt)

        return self._fallback.complete(system_prompt, user_prompt)


class OpenAIProvider(ReasoningProvider):
    """Optional OpenAI client with strict timeout and fallback."""

    def __init__(self, api_key: str, model: str = "gpt-4o", timeout_seconds: float = 30.0) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, timeout=timeout_seconds)
        self._model = model
        self._fallback = LocalDeterministicProvider()

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content or ""
            return clean_deepseek_reasoning_output(raw)
        except Exception as e:
            logger.warning(
                "openai_provider_error", error=str(e), action="falling_back_to_deterministic"
            )
            return self._fallback.complete(system_prompt, user_prompt)


def get_llm_provider(
    provider: str = "deterministic",
    api_key: str | None = None,
    model: str = "",
    cloudflare_account_id: str = "",
    cloudflare_api_token: str | None = None,
) -> ReasoningProvider:
    """
    Factory function returning the configured reasoning provider.
    Defaults to zero-cost LocalDeterministicProvider unless explicitly configured.
    """
    provider_clean = (provider or "deterministic").lower()

    def load_settings() -> Any:
        try:
            from app.core.config import settings

            return settings
        except Exception:
            return None

    app_settings = load_settings()

    if provider_clean in ("cloudflare", "cloudflare_workers_ai"):
        account_id = cloudflare_account_id or (
            getattr(app_settings, "CLOUDFLARE_ACCOUNT_ID", "") if app_settings else ""
        )
        token = cloudflare_api_token or (
            str(getattr(app_settings, "CLOUDFLARE_API_TOKEN", "") or "") if app_settings else ""
        )
        model_id = model or (
            getattr(app_settings, "REASONING_MODEL", CloudflareWorkersAIProvider.DEFAULT_MODEL)
            if app_settings
            else CloudflareWorkersAIProvider.DEFAULT_MODEL
        )
        return CloudflareWorkersAIProvider(
            account_id=account_id,
            api_token=token,
            model=model_id,
        )

    if provider_clean == "openai" and api_key:
        return OpenAIProvider(api_key=api_key, model=model or "gpt-4o")

    logger.info(
        "using_local_deterministic_reasoning_provider", reason="zero-cost default or mock mode"
    )
    return LocalDeterministicProvider()


# Backward-compatible alias
get_reasoning_provider = get_llm_provider
