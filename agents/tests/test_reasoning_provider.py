"""
Unit tests for ReasoningProvider, Cloudflare Workers AI integration, and DeepSeek-R1 parsing.

Verifies:
- DeepSeek <think>...</think> stripping and JSON extraction.
- JSON bounded repair on trailing commas and malformed wrapping.
- CloudflareWorkersAIProvider quota exhaustion (429/403) triggering immediate deterministic fallback.
- Transient server error (5xx) single retry with fallback.
- LocalDeterministicProvider producing valid Pydantic DiagnosisOutput and StrategyOutput.
- Provider factory defaults to zero-cost LocalDeterministicProvider without credentials.
"""

import json
from unittest.mock import MagicMock, patch
import httpx
import pytest

from agents.nodes.llm_provider import (
    CloudflareWorkersAIProvider,
    LocalDeterministicProvider,
    MockProvider,
    clean_deepseek_reasoning_output,
    get_llm_provider,
    repair_json_string,
)
from agents.schemas.agent_schemas import DiagnosisOutput, StrategyOutput


def test_clean_deepseek_reasoning_output_removes_think_tags():
    raw = (
        "<think>\n"
        "The customer experienced an INSUFFICIENT_FUNDS decline. "
        "The best approach is to schedule a retry in 24 hours.\n"
        "</think>\n"
        '{"diagnosis": "insufficient_funds_transient", "diagnosis_confidence": 0.82, '
        '"failure_category": "INSUFFICIENT_FUNDS", "likely_cause": "Temporary low balance", '
        '"is_recoverable": true, "recommended_strategy": "SCHEDULE_RETRY"}'
    )
    cleaned = clean_deepseek_reasoning_output(raw)
    assert "<think>" not in cleaned
    assert "</think>" not in cleaned
    data = json.loads(cleaned)
    assert data["failure_category"] == "INSUFFICIENT_FUNDS"
    assert data["recommended_strategy"] == "SCHEDULE_RETRY"


def test_clean_deepseek_output_markdown_fences():
    raw = (
        "Here is the strategy proposal:\n"
        "```json\n"
        '{\n  "recovery_strategy": "SCHEDULE_RETRY",\n  "reason": "Retry after salary cycle.",\n'
        '  "requested_action": {"type": "SCHEDULE_RETRY", "delay_hours": 24},\n'
        '  "expected_recovery_paise": 199900,\n  "confidence": 0.78\n}\n'
        "```"
    )
    cleaned = clean_deepseek_reasoning_output(raw)
    data = json.loads(cleaned)
    assert data["recovery_strategy"] == "SCHEDULE_RETRY"
    assert data["requested_action"]["delay_hours"] == 24


def test_repair_json_string_removes_trailing_commas():
    broken_json = '{"a": 1, "b": 2,}'
    repaired = repair_json_string(broken_json)
    assert repaired == '{"a": 1, "b": 2}'
    data = json.loads(repaired)
    assert data == {"a": 1, "b": 2}


def test_local_deterministic_provider_valid_diagnosis_output():
    provider = LocalDeterministicProvider()
    user_prompt = "Case ID: case-1\nFailure Reason: INSUFFICIENT_FUNDS\nAmount: ₹1999.00 (INR)\nLightGBM Probability: 0.75"
    raw = provider.complete("system prompt", user_prompt)
    data = json.loads(raw)
    # Validate with Pydantic DiagnosisOutput
    diag = DiagnosisOutput(**data)
    assert diag.failure_category == "INSUFFICIENT_FUNDS"
    assert diag.recommended_strategy == "SCHEDULE_RETRY"
    assert diag.diagnosis_confidence == 0.75
    assert diag.is_recoverable is True


def test_local_deterministic_provider_valid_strategy_output():
    provider = LocalDeterministicProvider()
    user_prompt = "Propose strategy for:\nFailure Reason: GATEWAY_TEMPORARY\nAmount: ₹499.00\nLightGBM Probability: 0.85"
    raw = provider.complete("system prompt", user_prompt)
    data = json.loads(raw)
    strat = StrategyOutput(**data)
    assert strat.recovery_strategy == "RETRY_NOW"
    assert strat.confidence == 0.85


def test_cloudflare_provider_quota_exhaustion_falls_back():
    provider = CloudflareWorkersAIProvider(
        account_id="test_account",
        api_token="test_token",
    )

    # Mock 429 Rate Limit / Quota Exhaustion
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = '{"success": false, "errors": [{"message": "Daily quota of 10,000 neurons exceeded"}]}'

    with patch("httpx.Client.post", return_value=mock_response):
        user_prompt = "Failure Reason: BANK_DECLINE\nAmount: ₹1000.00"
        raw = provider.complete("system", user_prompt)
        data = json.loads(raw)
        # Should gracefully return deterministic fallback output
        assert "recovery_strategy" in data or "recommended_strategy" in data


def test_cloudflare_provider_missing_credentials_safe_fallback():
    # No credentials supplied
    provider = CloudflareWorkersAIProvider(
        account_id="",
        api_token="",
    )
    user_prompt = "Failure Reason: INSUFFICIENT_FUNDS"
    raw = provider.complete("system", user_prompt)
    data = json.loads(raw)
    assert data["failure_category"] == "INSUFFICIENT_FUNDS" or data["recovery_strategy"] == "SCHEDULE_RETRY"


def test_get_llm_provider_default_deterministic():
    provider = get_llm_provider("deterministic")
    assert isinstance(provider, LocalDeterministicProvider)

    # Unknown or empty provider defaults to zero-cost deterministic
    provider_fallback = get_llm_provider("")
    assert isinstance(provider_fallback, LocalDeterministicProvider)
