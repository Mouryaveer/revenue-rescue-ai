"""
Agent unit tests.
Tests the full LangGraph pipeline using MockProvider (no API key needed).
State is now TypedDict — access via result["key"] or result.get("key").
"""

import pytest

from agents.graph.recovery_graph import RecoveryAgent
from agents.schemas.agent_schemas import make_initial_state
from policies.schemas.policy_schema import PolicyConfig


def default_policy() -> PolicyConfig:
    return PolicyConfig(policy_id="test", version=1)


def make_state(**overrides):
    defaults = dict(
        case_id="case-001",
        agent_run_id="run-001",
        event_type="FAILED_PAYMENT",
        failure_reason="INSUFFICIENT_FUNDS",
        amount_paise=299900,
        customer_id="cust-001",
        customer_segment="standard",
        customer_opted_out=False,
        customer_suspended=False,
        llm_provider="mock",
    )
    defaults.update(overrides)
    return make_initial_state(**defaults)


def make_agent(seed: int = 42) -> RecoveryAgent:
    return RecoveryAgent(policy=default_policy(), llm_provider="mock", simulator_seed=seed)


# ── Basic completion ───────────────────────────────────────────────────────────

def test_agent_runs_to_completion():
    result = make_agent().run(make_state())
    assert "completion" in result.get("node_trace", [])


def test_agent_produces_diagnosis():
    result = make_agent().run(make_state())
    diag = result.get("case_diagnosis")
    assert diag is not None
    assert diag.failure_category == "INSUFFICIENT_FUNDS"
    assert 0.0 <= diag.diagnosis_confidence <= 1.0


def test_agent_produces_strategy():
    result = make_agent().run(make_state())
    strat = result.get("case_strategy")
    assert strat is not None
    assert strat.recovery_strategy in (
        "RETRY_NOW", "SCHEDULE_RETRY", "PAYMENT_METHOD_UPDATE",
        "REMINDER", "CHECKOUT_RECOVERY", "PROMISE_TO_PAY", "ESCALATE"
    )


def test_agent_policy_check_runs():
    result = make_agent().run(make_state())
    assert result.get("policy_result") is not None
    assert "decision" in result.get("policy_result", {})


def test_agent_execution_result_set():
    result = make_agent().run(make_state())
    assert result.get("execution_result") is not None


def test_recovery_or_completion_terminal():
    result = make_agent().run(make_state())
    assert (
        result.get("case_is_recovered")
        or result.get("case_is_stopped")
        or result.get("escalation_reason") is not None
    )


# ── Gateway temporary — high success rate ─────────────────────────────────────

def test_gateway_temporary_often_recovers():
    successes = 0
    for seed in range(30):
        result = make_agent(seed=seed).run(
            make_state(failure_reason="GATEWAY_TEMPORARY", amount_paise=100000)
        )
        if result.get("case_is_recovered"):
            successes += 1
    assert successes >= 15, f"GATEWAY_TEMPORARY should recover frequently, got {successes}/30"


# ── Policy denial paths ────────────────────────────────────────────────────────

def test_opted_out_customer_case_stopped():
    result = make_agent().run(make_state(customer_opted_out=True))
    assert not result.get("case_is_recovered")
    assert result.get("case_is_stopped")


def test_suspended_customer_case_stopped():
    result = make_agent().run(make_state(customer_suspended=True))
    assert result.get("case_is_stopped")


def test_max_retries_reached_escalates():
    result = make_agent().run(make_state(retry_count=3))
    assert not result.get("case_is_recovered")
    assert result.get("case_is_stopped") or result.get("escalation_reason") is not None


def test_amount_over_limit_escalates():
    result = make_agent().run(make_state(amount_paise=6_000_000))
    assert not result.get("case_is_recovered")
    assert result.get("escalation_reason") is not None


def test_already_recovered_stopped_immediately():
    result = make_agent().run(make_state(case_is_recovered=True))
    assert result.get("case_is_stopped")


# ── Checkout abandonment ───────────────────────────────────────────────────────

def test_checkout_abandonment_runs():
    result = make_agent().run(make_state(
        event_type="CHECKOUT_ABANDONMENT",
        failure_reason="CHECKOUT_ABANDONED",
        amount_paise=349900,
        checkout_timeout_elapsed=True,
    ))
    diag = result.get("case_diagnosis")
    assert diag is not None
    assert diag.failure_category == "CHECKOUT_ABANDONED"
    assert result.get("case_strategy") is not None


def test_checkout_opted_out_blocked():
    result = make_agent().run(make_state(
        event_type="CHECKOUT_ABANDONMENT",
        failure_reason="CHECKOUT_ABANDONED",
        amount_paise=349900,
        checkout_timeout_elapsed=True,
        customer_opted_out=True,
    ))
    assert not result.get("case_is_recovered")
    assert result.get("case_is_stopped")


# ── Unknown failure ────────────────────────────────────────────────────────────

def test_unknown_failure_escalated():
    result = make_agent().run(make_state(failure_reason="UNKNOWN"))
    assert not result.get("case_is_recovered")


# ── Fallback mode ─────────────────────────────────────────────────────────────

def test_fallback_produces_valid_structured_output():
    from agents.nodes.llm_provider import MockProvider
    import json
    output = MockProvider().complete("system", "Failure Reason: INSUFFICIENT_FUNDS diagnosis_confidence")
    data = json.loads(output)
    assert "diagnosis_confidence" in data
    assert "failure_category" in data


def test_fallback_produces_strategy_output():
    from agents.nodes.llm_provider import MockProvider
    import json
    output = MockProvider().complete("system", "Failure Reason: GATEWAY_TEMPORARY recovery_strategy")
    data = json.loads(output)
    assert "recovery_strategy" in data
    assert data["recovery_strategy"] in (
        "RETRY_NOW", "SCHEDULE_RETRY", "PAYMENT_METHOD_UPDATE",
        "REMINDER", "CHECKOUT_RECOVERY", "PROMISE_TO_PAY", "ESCALATE"
    )


# ── Node trace integrity ───────────────────────────────────────────────────────

def test_node_trace_always_starts_with_risk_detection():
    result = make_agent().run(make_state())
    assert result.get("node_trace", [])[0] == "risk_detection"


def test_node_trace_ends_with_completion():
    result = make_agent().run(make_state())
    assert result.get("node_trace", [])[-1] == "completion"


def test_policy_check_in_trace_when_approved():
    result = make_agent().run(make_state(amount_paise=100000, retry_count=0))
    if (result.get("execution_result") or {}).get("executed"):
        assert "policy_check" in result.get("node_trace", [])
