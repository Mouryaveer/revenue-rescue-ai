"""
LLM Provider abstraction.
Concrete implementations: OpenAIProvider, MockProvider (deterministic fallback).
The agent calls LLMProvider.complete() — never OpenAI directly.
This ensures the system runs without an API key in fallback mode.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

import structlog

logger = structlog.get_logger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw string output from the LLM."""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


class MockProvider(LLMProvider):
    """
    Deterministic fallback — no API key required.
    Uses rule-based logic to produce valid structured output.
    The UI must display MODE=FALLBACK when this is active — never present as AI.
    """

    STRATEGY_MAP = {
        "INSUFFICIENT_FUNDS":   ("SCHEDULE_RETRY", 24,  0.75),
        "EXPIRED_METHOD":       ("PAYMENT_METHOD_UPDATE", 0, 0.60),
        "GATEWAY_TEMPORARY":    ("RETRY_NOW",       2,  0.85),
        "BANK_DECLINE":         ("SCHEDULE_RETRY",  48, 0.55),
        "AUTH_FAILURE":         ("REMINDER",        0,  0.50),
        "MANDATE_FAILURE":      ("SCHEDULE_RETRY",  24, 0.65),
        "SUBSCRIPTION_GRACE":   ("SCHEDULE_RETRY",  24, 0.65),
        "CHECKOUT_ABANDONED":   ("CHECKOUT_RECOVERY", 0, 0.55),
        "UNKNOWN":              ("ESCALATE",         0, 0.20),
    }

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Extract failure_reason precisely — look for "Failure Reason: <VALUE>" pattern first
        import re
        match = re.search(r"Failure Reason:\s*(\w+)", user_prompt)
        if match:
            failure_reason = match.group(1)
        else:
            # Fallback: search for known reason codes in priority order
            priority_order = [
                "CHECKOUT_ABANDONED", "MANDATE_FAILURE", "SUBSCRIPTION_GRACE",
                "INSUFFICIENT_FUNDS", "EXPIRED_METHOD", "GATEWAY_TEMPORARY",
                "AUTH_FAILURE", "BANK_DECLINE", "UNKNOWN",
            ]
            failure_reason = "UNKNOWN"
            for reason in priority_order:
                if reason in user_prompt:
                    failure_reason = reason
                    break

        strategy, delay, confidence = self.STRATEGY_MAP.get(failure_reason, ("ESCALATE", 0, 0.20))
        needs_review = failure_reason == "UNKNOWN"

        # Detect whether this is a diagnosis or strategy prompt
        if "diagnosis_confidence" in user_prompt:
            output = {
                "diagnosis": f"rule_based_{failure_reason.lower()}",
                "diagnosis_confidence": confidence,
                "failure_category": failure_reason,
                "likely_cause": f"Rule-based diagnosis for {failure_reason}. No LLM inference.",
                "is_recoverable": strategy != "ESCALATE",
                "recommended_strategy": strategy,
                "needs_human_review": needs_review,
                "notes": "FALLBACK_MODE — deterministic rule-based output",
            }
        else:
            output = {
                "recovery_strategy": strategy,
                "reason": f"Rule-based strategy for {failure_reason}. No LLM inference.",
                "requested_action": {"type": strategy, "delay_hours": delay},
                "expected_recovery_paise": 0,
                "confidence": confidence,
                "fallback_strategy": "ESCALATE",
            }

        logger.info("mock_llm_response", failure_reason=failure_reason, strategy=strategy)
        return json.dumps(output)


def get_llm_provider(provider: str = "mock", api_key: str = "", model: str = "gpt-4o") -> LLMProvider:
    if provider == "openai" and api_key:
        return OpenAIProvider(api_key=api_key, model=model)
    logger.info("using_mock_llm_provider", reason="No API key or mock mode specified")
    return MockProvider()
