"""
LangGraph node implementations.
Each node is a pure function: AgentState (TypedDict) -> dict (partial update).
LangGraph merges the returned dict into the state automatically.
Only diagnosis and strategy nodes use the LLM. All others are deterministic.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime

import structlog
from app.providers.base import PaymentProvider, PaymentStatus

from agents.nodes.llm_provider import LLMProvider
from agents.prompts.system_prompt import (
    DIAGNOSIS_PROMPT_TEMPLATE,
    STRATEGY_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
)
from agents.schemas.agent_schemas import AgentState, DiagnosisOutput, StrategyOutput
from policies.engine.policy_engine import AuthorizationContext, PolicyEngine
from simulator.engine.recovery_verifier import RecoveryVerifier

logger = structlog.get_logger(__name__)


def _add_trace(state: AgentState, node: str) -> dict:
    """Return a partial state update that appends to node_trace."""
    current = list(state.get("node_trace", []))
    current.append(node)
    return {"node_trace": current, "current_node": node}


# ── Node 1: Risk Detection (deterministic) ────────────────────────────────────


def node_risk_detection(state: AgentState) -> dict:
    trace = _add_trace(state, "risk_detection")
    logger.info(
        "node_risk_detection", case_id=state.get("case_id"), event_type=state.get("event_type")
    )

    if state.get("case_is_recovered"):
        return {
            **trace,
            "case_is_stopped": True,
            "escalation_reason": "Case already recovered — stopping",
        }

    if state.get("payment_already_succeeded"):
        return {**trace, "case_is_stopped": True}

    if (state.get("amount_paise", 0)) <= 0:
        return {**trace, "error": "Invalid amount — rejecting case", "case_is_stopped": True}

    return trace


# ── Node 2: Context Builder (deterministic) ───────────────────────────────────


def node_context_builder(state: AgentState) -> dict:
    trace = _add_trace(state, "context_builder")
    logger.info("node_context_builder", case_id=state.get("case_id"))

    # Compute quantitative recovery probability and expected value via LightGBM
    try:
        from app.services.ml_scoring_service import MLScoringService

        scorer = MLScoringService()
        features = {
            "event_type": state.get("event_type", "FAILED_PAYMENT"),
            "failure_reason": state.get("failure_reason", "UNKNOWN"),
            "payment_method": state.get("payment_method", "card"),
            "device_type": state.get("device_type", "web"),
            "country": state.get("country", "IN"),
            "amount_paise": state.get("amount_paise", 0),
            "retry_count": state.get("retry_count", 0),
        }
        evidence = scorer.get_quantitative_evidence(features)
        return {
            **trace,
            "ml_probability": evidence["recovery_probability"],
            "ml_expected_value_paise": evidence["expected_value_paise"],
            "ml_model_version": evidence["model_version"],
            "ml_evidence": evidence,
            "rule_retry_delay_hours": evidence["rule_based_retry_delay_hours"],
        }
    except Exception as e:
        logger.warning(
            "context_builder_ml_scoring_failed", error=str(e), case_id=state.get("case_id")
        )
        return trace


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
        from agents.nodes.llm_provider import clean_deepseek_reasoning_output, repair_json_string

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
        from agents.nodes.llm_provider import clean_deepseek_reasoning_output, repair_json_string

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


# ── Node 5: Policy Check (deterministic) ─────────────────────────────────────


def node_policy_check(state: AgentState, policy_engine: PolicyEngine) -> dict:
    trace = _add_trace(state, "policy_check")
    strat: StrategyOutput | None = state.get("case_strategy")
    diag: DiagnosisOutput | None = state.get("case_diagnosis")

    if not strat:
        return {
            **trace,
            "policy_result": {"decision": "ESCALATE", "reason": "No strategy available"},
        }

    action_type = _strategy_to_action_type(strat.recovery_strategy)

    ctx = AuthorizationContext(
        case_id=str(state.get("case_id")),
        action_type=action_type,
        amount_paise=state.get("amount_paise", 0),
        retry_count=state.get("retry_count", 0),
        communication_count=state.get("communication_count", 0),
        customer_opted_out=state.get("customer_opted_out", False),
        customer_suspended=state.get("customer_suspended", False),
        case_is_recovered=state.get("case_is_recovered", False),
        payment_already_succeeded=state.get("payment_already_succeeded", False),
        failure_reason=state.get("failure_reason", "UNKNOWN"),
        hours_since_last_attempt=state.get("hours_since_last_attempt"),
        diagnosis_confidence=diag.diagnosis_confidence if diag else None,
        checkout_timeout_elapsed=state.get("checkout_timeout_elapsed", False),
        checkout_recovery_message_count=state.get("checkout_recovery_message_count", 0),
    )

    result = policy_engine.authorize(ctx)
    logger.info(
        "policy_check_result",
        case_id=state.get("case_id"),
        decision=result.decision,
        action=action_type,
        policy_version=result.policy_version,
    )
    return {**trace, "policy_result": result.model_dump()}


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


# ── Node 6: Action Execution (APPROVED actions only) ──────────────────────────


def node_action_execution(state: AgentState, provider: PaymentProvider) -> dict:
    trace = _add_trace(state, "action_execution")
    policy_result = state.get("policy_result") or {}

    if policy_result.get("decision") != "APPROVED":
        logger.warning(
            "action_blocked_by_policy",
            case_id=state.get("case_id"),
            decision=policy_result.get("decision"),
            reason=policy_result.get("reason"),
        )
        return {
            **trace,
            "execution_result": {
                "executed": False,
                "reason": policy_result.get("reason"),
                "decision": policy_result.get("decision"),
            },
        }

    strat: StrategyOutput | None = state.get("case_strategy")
    strategy = strat.recovery_strategy if strat else "ESCALATE"
    logger.info(
        "executing_action",
        case_id=state.get("case_id"),
        strategy=strategy,
        provider_mode=provider.mode.value,
    )
    updates: dict = dict(trace)

    if strategy in ("RETRY_NOW", "SCHEDULE_RETRY"):
        # Use PaymentProvider interface instead of direct simulator call
        idempotency_key = f"{state.get('case_id')}-{strategy}-{(state.get('retry_count', 0)) + 1}"

        if strategy == "SCHEDULE_RETRY":
            # Extract delay from strategy requested_action
            delay_hours = 24  # Default delay
            if strat and strat.requested_action:
                delay_hours = strat.requested_action.get("delay_hours", 24)

            result = provider.schedule_retry(
                case_id=str(state.get("case_id")),
                original_payment_id=str(state.get("payment_id", "")),
                amount_paise=state.get("amount_paise", 0),
                currency=str(state.get("currency", "INR")),
                customer_id=str(state.get("customer_id")),
                delay_hours=delay_hours,
                idempotency_key=idempotency_key,
                retry_number=(state.get("retry_count", 0)) + 1,
                failure_reason=str(state.get("failure_reason", "UNKNOWN")),
                customer_segment=str(state.get("customer_segment", "standard")),
            )
        else:
            result = provider.retry_payment(
                case_id=str(state.get("case_id")),
                original_payment_id=str(state.get("payment_id", "")),
                amount_paise=state.get("amount_paise", 0),
                currency=str(state.get("currency", "INR")),
                customer_id=str(state.get("customer_id")),
                idempotency_key=idempotency_key,
                retry_number=(state.get("retry_count", 0)) + 1,
                failure_reason=str(state.get("failure_reason", "UNKNOWN")),
                customer_segment=str(state.get("customer_segment", "standard")),
            )

        updates["execution_result"] = {
            "executed": True,
            "type": "payment_retry",
            "attempt_id": result.attempt_id,
            "transaction_id": result.payment_id,
            "outcome": result.status.value,
            "failure_reason": result.failure_reason,
            "amount_paise": result.amount_paise,
        }
        updates["retry_count"] = (state.get("retry_count", 0)) + 1

    elif strategy == "CHECKOUT_RECOVERY":
        # For checkout recovery, we send a communication and potentially a payment
        # Since PaymentProvider doesn't have checkout_recovery, we handle communication separately
        updates["communication_count"] = (state.get("communication_count", 0)) + 1
        updates["checkout_recovery_message_count"] = (
            state.get("checkout_recovery_message_count", 0)
        ) + 1
        updates["execution_result"] = {
            "executed": True,
            "type": "checkout_recovery",
            "message_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
            "delivered": True,
            "customer_resumed": False,  # Will be determined by external webhook
            "transaction_id": None,
            "outcome": "PENDING",  # Pending customer action
            "amount_paise": 0,
        }

    elif strategy in ("REMINDER", "PAYMENT_METHOD_UPDATE"):
        updates["communication_count"] = (state.get("communication_count", 0)) + 1
        updates["execution_result"] = {
            "executed": True,
            "type": "communication",
            "strategy": strategy,
            "message_id": f"MSG-{uuid.uuid4().hex[:8].upper()}",
            "delivered": True,
        }

    else:
        updates["execution_result"] = {
            "executed": True,
            "type": strategy.lower(),
            "strategy": strategy,
        }

    return updates


# ── Node 7: Observation ───────────────────────────────────────────────────────


def node_observation(state: AgentState) -> dict:
    trace = _add_trace(state, "observation")
    logger.info("observation", case_id=state.get("case_id"), result=state.get("execution_result"))
    return trace


# ── Node 8: Verification (deterministic) ─────────────────────────────────────


def node_verification(
    state: AgentState, provider: PaymentProvider, verifier: RecoveryVerifier
) -> dict:
    trace = _add_trace(state, "verification")
    execution_result = state.get("execution_result") or {}

    if not execution_result.get("executed"):
        return {**trace, "verification_result": {"verified": False, "outcome": "NOT_EXECUTED"}}

    exec_type = execution_result.get("type", "")

    if exec_type == "checkout_recovery":
        # Checkout recovery requires external webhook to confirm payment
        # For now, mark as PENDING until webhook received
        return {
            **trace,
            "verification_result": {
                "verified": False,
                "outcome": "PENDING_WEBHOOK",
                "transaction_id": None,
                "amount_recovered_paise": 0,
                "reason": "Awaiting webhook confirmation for checkout recovery",
                "verified_at": datetime.now(UTC).isoformat(),
            },
        }

    elif exec_type == "payment_retry":
        transaction_id = execution_result.get("transaction_id")
        if not transaction_id:
            return {
                **trace,
                "verification_result": {
                    "verified": False,
                    "outcome": "NO_TRANSACTION",
                    "transaction_id": None,
                    "amount_recovered_paise": 0,
                    "reason": "No transaction ID from payment retry",
                    "verified_at": datetime.now(UTC).isoformat(),
                },
            }

        # Use PaymentProvider to fetch authoritative payment status
        payment_result = provider.get_payment(transaction_id)

        # Only mark as recovered if payment is SUCCESS
        is_recovered = payment_result.status == PaymentStatus.SUCCESS

        vr_dict = {
            "verified": is_recovered,
            "outcome": "RECOVERED" if is_recovered else payment_result.status.value,
            "transaction_id": transaction_id,
            "amount_recovered_paise": payment_result.amount_paise if is_recovered else 0,
            "reason": f"Payment status: {payment_result.status.value}",
            "verified_at": datetime.now(UTC).isoformat(),
        }

        if is_recovered:
            logger.info(
                "revenue_verified_recovered",
                case_id=state.get("case_id"),
                amount_paise=payment_result.amount_paise,
                transaction_id=transaction_id,
            )
            return {
                **trace,
                "verification_result": vr_dict,
                "case_is_recovered": True,
                "case_is_stopped": True,
            }

        return {**trace, "verification_result": vr_dict}
    else:
        return {
            **trace,
            "verification_result": {"verified": False, "outcome": "COMMUNICATION_SENT"},
        }


# ── Node 9: Escalation (deterministic) ───────────────────────────────────────


def node_escalation(state: AgentState) -> dict:
    trace = _add_trace(state, "escalation")
    reason = (
        state.get("escalation_reason")
        or (state.get("policy_result") or {}).get("reason")
        or "Escalation triggered"
    )
    logger.info("case_escalated", case_id=state.get("case_id"), reason=reason)
    return {**trace, "escalation_reason": reason, "case_is_stopped": True}


# ── Node 10: Completion ───────────────────────────────────────────────────────


def node_completion(state: AgentState) -> dict:
    trace = _add_trace(state, "completion")
    updates: dict = dict(trace)
    policy_result = state.get("policy_result") or {}
    if policy_result.get("decision") == "DENIED" and not state.get("case_is_recovered"):
        updates["case_is_stopped"] = True
        # Propagate the denial reason so audit trail records it clearly
        if not state.get("escalation_reason"):
            updates["escalation_reason"] = policy_result.get("reason", "DENIED by policy")
    logger.info(
        "agent_run_complete",
        case_id=state.get("case_id"),
        recovered=state.get("case_is_recovered"),
        stopped=state.get("case_is_stopped"),
        nodes_visited=state.get("node_trace"),
    )
    return updates
