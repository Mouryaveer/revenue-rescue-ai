"""
LLM-backed graph nodes: diagnosis and strategy.

Each node falls back to a deterministic output when the LLM call or output
validation fails. Imports helpers from node_utils only; never from
deterministic_nodes.
"""

from __future__ import annotations

import json
import time

import structlog

from agents.nodes.llm_provider import (
    LLMProvider,
    clean_deepseek_reasoning_output,
    repair_json_string,
)
from agents.nodes.node_utils import _add_trace, _fallback_diagnosis, _fallback_strategy
from agents.prompts.system_prompt import (
    DIAGNOSIS_PROMPT_TEMPLATE,
    STRATEGY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from agents.schemas.agent_schemas import AgentState, DiagnosisOutput, StrategyOutput

logger = structlog.get_logger(__name__)


# ── Node 3: Diagnosis (LLM or fallback) ───────────────────────────────────────


def node_diagnosis(state: AgentState, llm: LLMProvider) -> dict:
    trace = _add_trace(state, "diagnosis")
    failure_reason = state.get("failure_reason", "UNKNOWN")
    logger.info("node_diagnosis", case_id=state.get("case_id"), failure_reason=failure_reason)

    prompt = DIAGNOSIS_PROMPT_TEMPLATE.format(
        case_id=state.get("case_id"),
        event_type=state.get("event_type"),
        failure_reason=failure_reason,
        amount_inr=(state.get("amount_paise") or 0) / 100,
        customer_segment=state.get("customer_segment", "standard"),
        customer_opted_out=state.get("customer_opted_out", False),
        retry_count=state.get("retry_count", 0),
        hours_since_last_attempt=state.get("hours_since_last_attempt"),
        checkout_timeout_elapsed=state.get("checkout_timeout_elapsed", False),
    )

    # Append quantitative evidence context if available
    ml_prob = state.get("ml_probability")
    if ml_prob is not None:
        ev_paise = state.get("ml_expected_value_paise") or 0
        prompt += f"\nQuantitative Evidence:\n- LightGBM Probability: {ml_prob:.4f}\n- Expected Value: ₹{ev_paise / 100.0:.2f} INR\n"

    t0 = time.perf_counter()
    try:
        raw = llm.complete(SYSTEM_PROMPT, prompt)
        cleaned = clean_deepseek_reasoning_output(raw)
        cleaned = repair_json_string(cleaned)
        data = json.loads(cleaned)
        diag = DiagnosisOutput(**data)
    except Exception as e:
        logger.warning("diagnosis_llm_failure", error=str(e), case_id=state.get("case_id"))
        diag = _fallback_diagnosis(failure_reason, ml_probability=ml_prob)

    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "diagnosis_complete",
        case_id=state.get("case_id"),
        confidence=diag.diagnosis_confidence,
        latency_ms=elapsed,
    )
    return {**trace, "case_diagnosis": diag}


# ── Node 4: Strategy (LLM or fallback) ───────────────────────────────────────


def node_strategy(state: AgentState, llm: LLMProvider) -> dict:
    trace = _add_trace(state, "strategy")
    diag: DiagnosisOutput | None = state.get("case_diagnosis")
    if not diag:
        diag = _fallback_diagnosis(
            state.get("failure_reason", "UNKNOWN"), state.get("ml_probability")
        )

    prompt = STRATEGY_PROMPT_TEMPLATE.format(
        case_id=state.get("case_id"),
        failure_category=diag.failure_category,
        diagnosis=diag.diagnosis,
        diagnosis_confidence=diag.diagnosis_confidence,
        is_recoverable=diag.is_recoverable,
        amount_inr=(state.get("amount_paise") or 0) / 100,
        customer_segment=state.get("customer_segment", "standard"),
        retry_count=state.get("retry_count", 0),
        event_type=state.get("event_type"),
    )

    # Append quantitative evidence & rule-based timing recommendation
    delay_recommendation = state.get("rule_retry_delay_hours")
    if delay_recommendation is None:
        delay_recommendation = 24
    ml_prob = state.get("ml_probability")
    if ml_prob is not None:
        ev_paise = state.get("ml_expected_value_paise") or 0
        prompt += (
            f"\nQuantitative Inputs:\n"
            f"- LightGBM Probability: {ml_prob:.4f}\n"
            f"- Expected Value: ₹{ev_paise / 100.0:.2f} INR\n"
            f"- Rule-based Recommended Retry Delay: {delay_recommendation} hours (subject to policy authorization)\n"
        )

    try:
        raw = llm.complete(SYSTEM_PROMPT, prompt)
        cleaned = clean_deepseek_reasoning_output(raw)
        cleaned = repair_json_string(cleaned)
        data = json.loads(cleaned)
        strat = StrategyOutput(**data)
        # Ensure requested action contains delay_hours for retry strategies if omitted
        if "RETRY" in strat.recovery_strategy and "delay_hours" not in strat.requested_action:
            strat.requested_action["delay_hours"] = delay_recommendation
    except Exception as e:
        logger.warning("strategy_llm_failure", error=str(e), case_id=state.get("case_id"))
        strat = _fallback_strategy(
            diag, state.get("amount_paise", 0), delay_hours=delay_recommendation
        )

    logger.info("strategy_proposed", case_id=state.get("case_id"), strategy=strat.recovery_strategy)
    return {**trace, "case_strategy": strat}
