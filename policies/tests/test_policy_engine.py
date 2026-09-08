"""
Policy Engine unit tests.
Every rule is tested independently and in combination.
These tests must pass before the engine is wired to anything.
"""

import pytest

from policies.engine.policy_engine import AuthorizationContext, PolicyEngine
from policies.schemas.policy_schema import PolicyConfig


def make_policy(**overrides) -> PolicyConfig:
    base = {
        "policy_id": "test_policy",
        "version": 1,
    }
    base.update(overrides)
    return PolicyConfig(**base)


def make_ctx(**overrides) -> AuthorizationContext:
    defaults = dict(
        case_id="case-001",
        action_type="retry_payment",
        amount_paise=499900,  # ₹4,999
        retry_count=0,
        communication_count=0,
        customer_opted_out=False,
        customer_suspended=False,
        case_is_recovered=False,
        payment_already_succeeded=False,
        failure_reason="INSUFFICIENT_FUNDS",
        hours_since_last_attempt=25.0,
        diagnosis_confidence=0.9,
    )
    defaults.update(overrides)
    return AuthorizationContext(**defaults)


def engine() -> PolicyEngine:
    return PolicyEngine(make_policy())


# ── Basic approval ─────────────────────────────────────────────────────────────

def test_basic_approval():
    result = engine().authorize(make_ctx())
    assert result.allowed is True
    assert result.decision == "APPROVED"


# ── Retry limits ───────────────────────────────────────────────────────────────

def test_retry_1_allowed():
    result = engine().authorize(make_ctx(retry_count=1))
    assert result.allowed is True

def test_retry_2_allowed():
    result = engine().authorize(make_ctx(retry_count=2))
    assert result.allowed is True

def test_retry_3_blocked():
    """4th attempt (retry_count=3 means 3 retries already done) → ESCALATE."""
    result = engine().authorize(make_ctx(retry_count=3))
    assert result.allowed is False
    assert result.decision == "ESCALATE"
    assert "MAX_RETRIES_EXCEEDED" in result.violations

def test_retry_10_blocked():
    result = engine().authorize(make_ctx(retry_count=10))
    assert result.allowed is False
    assert result.decision == "ESCALATE"


# ── Monetary limits ────────────────────────────────────────────────────────────

def test_amount_at_limit_allowed():
    result = engine().authorize(make_ctx(amount_paise=5_000_000))
    assert result.allowed is True

def test_amount_over_limit_escalated():
    result = engine().authorize(make_ctx(amount_paise=5_000_001))
    assert result.allowed is False
    assert result.decision == "ESCALATE"
    assert "AMOUNT_EXCEEDS_AUTO_LIMIT" in result.violations

def test_zero_amount_denied():
    result = engine().authorize(make_ctx(amount_paise=0))
    assert result.allowed is False
    assert result.decision == "DENIED"

def test_negative_amount_denied():
    result = engine().authorize(make_ctx(amount_paise=-100))
    assert result.allowed is False


# ── Customer state ─────────────────────────────────────────────────────────────

def test_opted_out_customer_denied():
    result = engine().authorize(make_ctx(customer_opted_out=True))
    assert result.allowed is False
    assert result.decision == "DENIED"
    assert "CUSTOMER_OPT_OUT" in result.violations

def test_suspended_customer_denied():
    result = engine().authorize(make_ctx(customer_suspended=True))
    assert result.allowed is False
    assert result.decision == "DENIED"
    assert "CUSTOMER_SUSPENDED" in result.violations


# ── Stopping conditions ────────────────────────────────────────────────────────

def test_already_recovered_stopped():
    result = engine().authorize(make_ctx(case_is_recovered=True))
    assert result.allowed is False
    assert result.decision == "STOP"
    assert "CASE_ALREADY_RECOVERED" in result.violations

def test_payment_already_succeeded_stopped():
    result = engine().authorize(make_ctx(payment_already_succeeded=True))
    assert result.allowed is False
    assert result.decision == "STOP"


# ── Timing rules ───────────────────────────────────────────────────────────────

def test_retry_interval_not_satisfied():
    result = engine().authorize(make_ctx(hours_since_last_attempt=12.0))
    assert result.allowed is False
    assert result.decision == "DENIED"
    assert "RETRY_INTERVAL_NOT_SATISFIED" in result.violations

def test_retry_interval_exactly_satisfied():
    result = engine().authorize(make_ctx(hours_since_last_attempt=24.0))
    assert result.allowed is True

def test_first_attempt_no_timing_check():
    result = engine().authorize(make_ctx(hours_since_last_attempt=None))
    assert result.allowed is True


# ── Communication limits ───────────────────────────────────────────────────────

def test_reminder_within_limit():
    result = engine().authorize(make_ctx(action_type="send_payment_reminder", communication_count=2))
    assert result.allowed is True

def test_reminder_at_limit_blocked():
    result = engine().authorize(make_ctx(action_type="send_payment_reminder", communication_count=3))
    assert result.allowed is False
    assert "MAX_COMMUNICATIONS_EXCEEDED" in result.violations


# ── Unknown failure escalation ────────────────────────────────────────────────

def test_unknown_failure_escalated():
    result = engine().authorize(make_ctx(failure_reason="UNKNOWN"))
    assert result.allowed is False
    assert result.decision == "ESCALATE"
    assert "UNKNOWN_FAILURE_REASON" in result.violations


# ── Low confidence escalation ─────────────────────────────────────────────────

def test_low_confidence_escalated():
    result = engine().authorize(make_ctx(diagnosis_confidence=0.3))
    assert result.allowed is False
    assert result.decision == "ESCALATE"

def test_confidence_at_threshold_passed():
    result = engine().authorize(make_ctx(diagnosis_confidence=0.5))
    assert result.allowed is True


# ── Checkout-specific rules ────────────────────────────────────────────────────

def test_checkout_recovery_approved():
    result = engine().authorize(make_ctx(
        action_type="send_checkout_recovery",
        checkout_timeout_elapsed=True,
        checkout_recovery_message_count=0,
        amount_paise=50_000,
    ))
    assert result.allowed is True

def test_checkout_timeout_not_reached():
    result = engine().authorize(make_ctx(
        action_type="send_checkout_recovery",
        checkout_timeout_elapsed=False,
        checkout_recovery_message_count=0,
        amount_paise=50_000,
    ))
    assert result.allowed is False
    assert "CHECKOUT_TIMEOUT_NOT_REACHED" in result.violations

def test_checkout_message_limit_exceeded():
    result = engine().authorize(make_ctx(
        action_type="send_checkout_recovery",
        checkout_timeout_elapsed=True,
        checkout_recovery_message_count=2,
        amount_paise=50_000,
    ))
    assert result.allowed is False
    assert "MAX_CHECKOUT_RECOVERY_MESSAGES" in result.violations

def test_checkout_amount_too_low():
    result = engine().authorize(make_ctx(
        action_type="send_checkout_recovery",
        checkout_timeout_elapsed=True,
        checkout_recovery_message_count=0,
        amount_paise=500,  # below 10,000 paise minimum
    ))
    assert result.allowed is False
    assert "CHECKOUT_AMOUNT_TOO_LOW" in result.violations

def test_checkout_opted_out_denied():
    result = engine().authorize(make_ctx(
        action_type="send_checkout_recovery",
        checkout_timeout_elapsed=True,
        checkout_recovery_message_count=0,
        amount_paise=50_000,
        customer_opted_out=True,
    ))
    assert result.allowed is False
    assert "CUSTOMER_OPT_OUT" in result.violations


# ── Red-team tests ─────────────────────────────────────────────────────────────

def test_redteam_llm_cannot_override_max_retries():
    """Simulates: LLM proposes 4th retry. Policy must block it regardless."""
    result = engine().authorize(make_ctx(retry_count=3, action_type="retry_payment"))
    assert result.allowed is False
    assert result.decision in ("DENIED", "ESCALATE")

def test_redteam_opted_out_no_contact_allowed():
    """Customer opted out. No action type should bypass this."""
    for action in ("send_payment_reminder", "send_checkout_recovery", "change_communication_channel"):
        result = engine().authorize(make_ctx(action_type=action, customer_opted_out=True))
        assert result.allowed is False, f"Action {action} should be blocked for opted-out customer"

def test_redteam_recovered_case_no_further_actions():
    """Once RECOVERED, the case must not accept any further actions."""
    for action in ("retry_payment", "schedule_retry", "send_payment_reminder", "send_checkout_recovery"):
        result = engine().authorize(make_ctx(action_type=action, case_is_recovered=True))
        assert result.allowed is False
        assert result.decision == "STOP"

def test_redteam_policy_engine_unavailable_returns_escalate():
    """Simulate policy engine error — must fail closed."""
    from policies.engine.policy_engine import PolicyEngineError
    engine_instance = engine()

    # Corrupt the policy to trigger internal error
    engine_instance._policy = None  # type: ignore
    result = engine_instance.authorize(make_ctx())
    assert result.allowed is False
    assert result.decision == "ESCALATE"

def test_redteam_audit_includes_policy_version():
    """Every decision must carry policy_version for auditability."""
    result = engine().authorize(make_ctx())
    assert result.policy_version == 1
    assert result.policy_id == "test_policy"
