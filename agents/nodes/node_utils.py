"""
Helpers shared by LLM nodes and deterministic nodes.

Must not import from llm_nodes, deterministic_nodes, or llm_provider, so that
deterministic nodes stay importable without any LLM dependency.
"""

from __future__ import annotations

from agents.schemas.agent_schemas import AgentState, DiagnosisOutput, StrategyOutput


def _add_trace(state: AgentState, node: str) -> dict:
    """Return a partial state update that appends to node_trace."""
    current = list(state.get("node_trace", []))
    current.append(node)
    return {"node_trace": current, "current_node": node}


def _fallback_diagnosis(
    failure_reason: str, ml_probability: float | None = None
) -> DiagnosisOutput:
    strategy_map = {
        "INSUFFICIENT_FUNDS": ("SCHEDULE_RETRY", 0.75),
        "EXPIRED_METHOD": ("PAYMENT_METHOD_UPDATE", 0.60),
        "GATEWAY_TEMPORARY": ("RETRY_NOW", 0.85),
        "BANK_DECLINE": ("SCHEDULE_RETRY", 0.55),
        "AUTH_FAILURE": ("REMINDER", 0.50),
        "MANDATE_FAILURE": ("SCHEDULE_RETRY", 0.65),
        "SUBSCRIPTION_GRACE": ("SCHEDULE_RETRY", 0.65),
        "CHECKOUT_ABANDONED": ("CHECKOUT_RECOVERY", 0.55),
        "UNKNOWN": ("ESCALATE", 0.20),
    }
    strategy, default_conf = strategy_map.get(failure_reason, ("ESCALATE", 0.20))
    confidence = (
        ml_probability if (ml_probability is not None and strategy != "ESCALATE") else default_conf
    )
    confidence = round(max(0.0, min(1.0, float(confidence))), 4)

    return DiagnosisOutput(
        diagnosis=f"fallback_{failure_reason.lower()}",
        diagnosis_confidence=confidence,
        failure_category=failure_reason,
        likely_cause=f"Deterministic fallback for {failure_reason}",
        is_recoverable=strategy != "ESCALATE",
        recommended_strategy=strategy,
        needs_human_review=failure_reason == "UNKNOWN",
        notes="FALLBACK_MODE",
    )


def _fallback_strategy(
    diag: DiagnosisOutput, amount_paise: int, delay_hours: int = 24
) -> StrategyOutput:
    strategy = diag.recommended_strategy
    delay = delay_hours if "RETRY" in strategy else 0
    return StrategyOutput(
        recovery_strategy=strategy,
        reason=f"Deterministic fallback strategy for {diag.failure_category}",
        requested_action={"type": strategy, "delay_hours": delay},
        expected_recovery_paise=amount_paise if strategy != "ESCALATE" else 0,
        confidence=diag.diagnosis_confidence,
        fallback_strategy="ESCALATE",
    )


def _strategy_to_action_type(strategy: str) -> str:
    return {
        "RETRY_NOW": "retry_payment",
        "SCHEDULE_RETRY": "schedule_retry",
        "PAYMENT_METHOD_UPDATE": "request_payment_method_update",
        "REMINDER": "send_payment_reminder",
        "CHECKOUT_RECOVERY": "send_checkout_recovery",
        "PROMISE_TO_PAY": "create_promise_to_pay",
        "ESCALATE": "escalate_to_human",
    }.get(strategy, "escalate_to_human")
