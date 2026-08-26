"""
End-to-end integration tests — state is now TypedDict, access via dict.get().

Two mandatory e2e checks from §23 of the spec:
  1. FAILED → DETECTED → DIAGNOSED → APPROVED → RETRIED → SUCCESS → RECOVERED → STOPPED
  2. AI proposes policy-violating action → DENIED → not executed → audit recorded
"""

from agents.graph.recovery_graph import RecoveryAgent
from agents.schemas.agent_schemas import make_initial_state
from policies.schemas.policy_schema import PolicyConfig


def make_policy(**kwargs) -> PolicyConfig:
    return PolicyConfig(policy_id="e2e_policy", version=1, **kwargs)


def run_case(state, seed: int = 100) -> dict:
    agent = RecoveryAgent(policy=make_policy(), llm_provider="mock", simulator_seed=seed)
    return agent.run(state)


def s(**kw) -> dict:
    defaults = {
        "agent_run_id": "run-e2e",
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "GATEWAY_TEMPORARY",
        "amount_paise": 199900,
        "currency": "INR",
        "customer_id": "cust-e2e",
        "customer_segment": "premium",
        "llm_provider": "mock",
    }
    defaults.update(kw)
    return make_initial_state(**defaults)


# ── E2E Check 1: Full happy path ───────────────────────────────────────────────


def test_e2e_gateway_failure_recovers():
    """
    Full pipeline: risk_detection → ... → verification → RECOVERED → completion
    Verifies the mandatory E2E check 1 from §23.
    """
    recovered = False
    for seed in range(50):
        state = s(case_id=f"e2e-{seed}")
        result = run_case(state, seed=seed)

        assert "risk_detection" in result.get("node_trace", [])
        assert "diagnosis" in result.get("node_trace", [])
        assert "strategy" in result.get("node_trace", [])
        assert "policy_check" in result.get("node_trace", [])
        assert "completion" in result.get("node_trace", [])

        if result.get("case_is_recovered"):
            vr = result.get("verification_result", {})
            assert vr.get("outcome") == "RECOVERED"
            assert vr.get("amount_recovered_paise", 0) > 0
            assert result.get("case_is_stopped")
            recovered = True
            break

    assert recovered, "GATEWAY_TEMPORARY should recover in at least one of 50 seeds"


def test_e2e_recovery_stops_agent():
    """Once recovered, case_is_stopped must be True."""
    for seed in range(30):
        result = run_case(s(case_id=f"e2e-stop-{seed}", customer_segment="enterprise"), seed=seed)
        if result.get("case_is_recovered"):
            assert result.get("case_is_stopped"), "Recovered case MUST be stopped"
            assert result.get("node_trace", [])[-1] == "completion"
            break


# ── E2E Check 2: Policy blocks unauthorized action ────────────────────────────


def test_e2e_4th_retry_policy_denied():
    """
    retry_count=3 → Policy MUST deny → Executor MUST NOT execute.
    Mandatory E2E check 2 from §23.
    """
    state = s(
        case_id="e2e-deny",
        failure_reason="INSUFFICIENT_FUNDS",
        amount_paise=199900,
        customer_segment="standard",
        retry_count=3,
    )
    result = run_case(state)
    assert not result.get("case_is_recovered")
    assert (result.get("policy_result") or {}).get("decision") in ("ESCALATE", "DENIED")
    exec_r = result.get("execution_result") or {}
    assert exec_r.get("executed") is False or exec_r.get("type") != "payment_retry"


def test_e2e_opted_out_no_action():
    state = s(
        case_id="e2e-optout",
        failure_reason="BANK_DECLINE",
        amount_paise=149900,
        customer_opted_out=True,
    )
    result = run_case(state)
    assert not result.get("case_is_recovered")
    assert result.get("case_is_stopped")


# ── Checkout abandonment E2E ───────────────────────────────────────────────────


def test_e2e_checkout_abandonment_pipeline():
    state = make_initial_state(
        case_id="e2e-checkout",
        agent_run_id="run-checkout",
        event_type="CHECKOUT_ABANDONMENT",
        failure_reason="CHECKOUT_ABANDONED",
        amount_paise=349900,
        currency="INR",
        customer_id="cust-checkout",
        customer_segment="premium",
        checkout_timeout_elapsed=True,
        llm_provider="mock",
    )
    result = run_case(state, seed=42)
    diag = result.get("case_diagnosis")
    assert diag is not None
    assert diag.failure_category == "CHECKOUT_ABANDONED"
    assert result.get("case_strategy") is not None
    assert "completion" in result.get("node_trace", [])


# ── High-value always escalates ───────────────────────────────────────────────


def test_e2e_high_value_always_escalated():
    state = s(
        case_id="e2e-highval", failure_reason="BANK_DECLINE", amount_paise=6_000_000, customer_segment="enterprise"
    )
    result = run_case(state)
    assert not result.get("case_is_recovered")
    assert result.get("escalation_reason") is not None


# ── Unknown failure never fabricates ─────────────────────────────────────────


def test_e2e_unknown_failure_escalates_with_low_confidence():
    state = s(case_id="e2e-unknown", failure_reason="UNKNOWN", amount_paise=299900)
    result = run_case(state)
    assert not result.get("case_is_recovered")
    diag = result.get("case_diagnosis")
    if diag:
        assert diag.needs_human_review is True
        assert diag.diagnosis_confidence <= 0.25
