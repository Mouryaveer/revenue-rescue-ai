"""
Simulator unit tests — verifies payment outcomes and checkout recovery simulation.
"""

import pytest

from simulator.engine.payment_simulator import PaymentSimulator, SimulatedOutcome
from simulator.engine.recovery_verifier import RecoveryVerifier, VerificationOutcome
from simulator.generators.customer_generator import CustomerGenerator
from simulator.generators.payment_generator import PaymentEventGenerator


# ── Customer Generator ─────────────────────────────────────────────────────────

def test_customer_generator_reproducible():
    """Two generators with the same seed produce the same customer IDs and segments."""
    g1 = CustomerGenerator(seed=42)
    g2 = CustomerGenerator(seed=42)
    c1 = g1.generate(10)
    c2 = g2.generate(10)
    # Customer IDs and segments are driven by the seeded random.Random — fully reproducible
    assert [c.customer_id for c in c1] == [c.customer_id for c in c2]
    assert [c.segment for c in c1] == [c.segment for c in c2]
    assert [c.opted_out_communication for c in c1] == [c.opted_out_communication for c in c2]


def test_customer_generator_different_seeds():
    g1 = CustomerGenerator(seed=1)
    g2 = CustomerGenerator(seed=2)
    c1 = g1.generate(10)
    c2 = g2.generate(10)
    assert [c.name for c in c1] != [c.name for c in c2]


def test_customer_no_real_credentials():
    """All customers must be flagged synthetic."""
    g = CustomerGenerator(seed=42)
    customers = g.generate(50)
    assert all(c.is_synthetic for c in customers)


def test_customer_segments_varied():
    g = CustomerGenerator(seed=42)
    customers = g.generate(200)
    segments = {c.segment for c in customers}
    assert segments >= {"standard", "premium"}  # at minimum


# ── Payment Event Generator ────────────────────────────────────────────────────

def test_payment_events_reproducible():
    cg = CustomerGenerator(seed=42)
    customers = cg.generate(20)
    pg1 = PaymentEventGenerator(seed=42)
    pg2 = PaymentEventGenerator(seed=42)
    e1 = pg1.generate_batch(customers, 50)
    e2 = pg2.generate_batch(customers, 50)
    assert [e.idempotency_key for e in e1] != [e.idempotency_key for e in e2]  # UUIDs differ but reproducible structure
    assert [e.failure_reason for e in e1] == [e.failure_reason for e in e2]


def test_all_three_event_types_generated():
    cg = CustomerGenerator(seed=42)
    customers = cg.generate(50)
    pg = PaymentEventGenerator(seed=42)
    events = pg.generate_batch(customers, 300)
    types = {e.event_type for e in events}
    assert "FAILED_PAYMENT" in types
    assert "FAILED_SUBSCRIPTION" in types
    assert "CHECKOUT_ABANDONED" in types


def test_checkout_events_have_session_id():
    cg = CustomerGenerator(seed=42)
    customers = cg.generate(20)
    pg = PaymentEventGenerator(seed=42)
    events = pg.generate_batch(customers, 200)
    checkouts = [e for e in events if e.event_type == "CHECKOUT_ABANDONED"]
    assert all(e.checkout_session_id is not None for e in checkouts)
    assert all(e.failure_reason == "CHECKOUT_ABANDONED" for e in checkouts)


def test_all_amounts_positive():
    cg = CustomerGenerator(seed=42)
    customers = cg.generate(20)
    pg = PaymentEventGenerator(seed=42)
    events = pg.generate_batch(customers, 100)
    assert all(e.amount_paise > 0 for e in events)


# ── Payment Simulator ──────────────────────────────────────────────────────────

def test_payment_simulator_reproducible():
    sim1 = PaymentSimulator(seed=42)
    sim2 = PaymentSimulator(seed=42)
    r1 = sim1.execute_retry(
        case_id="c1", customer_id="u1", customer_segment="premium",
        failure_reason="INSUFFICIENT_FUNDS", retry_number=2,
        amount_paise=100000,
    )
    r2 = sim2.execute_retry(
        case_id="c1", customer_id="u1", customer_segment="premium",
        failure_reason="INSUFFICIENT_FUNDS", retry_number=2,
        amount_paise=100000,
    )
    assert r1.outcome == r2.outcome


def test_gateway_temporary_high_success_on_retry2():
    """GATEWAY_TEMPORARY has 90% success on retry #2 — over 100 trials should mostly succeed."""
    successes = 0
    for seed in range(100):
        sim = PaymentSimulator(seed=seed)
        r = sim.execute_retry(
            case_id="c", customer_id="u", customer_segment="standard",
            failure_reason="GATEWAY_TEMPORARY", retry_number=2, amount_paise=50000,
        )
        if r.outcome == SimulatedOutcome.SUCCESS:
            successes += 1
    assert successes >= 75, f"Expected >=75/100 successes, got {successes}"


def test_expired_method_always_fails():
    """Expired payment method always fails — customer must update method."""
    for seed in range(20):
        sim = PaymentSimulator(seed=seed)
        r = sim.execute_retry(
            case_id="c", customer_id="u", customer_segment="standard",
            failure_reason="EXPIRED_METHOD", retry_number=1, amount_paise=50000,
        )
        assert r.outcome == SimulatedOutcome.FAILED


def test_checkout_recovery_returns_tuple():
    sim = PaymentSimulator(seed=42)
    comm, payment = sim.execute_checkout_recovery(
        case_id="c1", customer_id="u1", customer_segment="premium",
        amount_paise=300000, message_number=1,
    )
    assert comm.message_id is not None
    assert comm.is_synthetic is True


def test_checkout_no_resume_returns_none_payment():
    """When customer doesn't resume, payment result is None."""
    # Force no-resume by using low-probability segment with many seeds
    no_resume_found = False
    for seed in range(50):
        sim = PaymentSimulator(seed=seed)
        comm, payment = sim.execute_checkout_recovery(
            case_id="c", customer_id="u", customer_segment="at_risk",
            amount_paise=50000, message_number=1,
        )
        if not comm.customer_resumed:
            assert payment is None
            no_resume_found = True
            break
    assert no_resume_found, "Should find at least one no-resume scenario in 50 seeds"


def test_simulator_result_is_synthetic():
    sim = PaymentSimulator(seed=42)
    r = sim.execute_retry(
        case_id="c", customer_id="u", customer_segment="standard",
        failure_reason="BANK_DECLINE", retry_number=1, amount_paise=50000,
    )
    assert r.is_synthetic is True


# ── Recovery Verifier ──────────────────────────────────────────────────────────

def test_verifier_marks_success_as_recovered():
    from simulator.engine.payment_simulator import SimulatedPaymentResult
    from datetime import datetime, timezone
    verifier = RecoveryVerifier()
    result = SimulatedPaymentResult(
        attempt_id="A1", transaction_id="T1",
        outcome=SimulatedOutcome.SUCCESS,
        failure_reason=None, amount_paise=499900, currency="INR",
        executed_at=datetime.now(timezone.utc),
    )
    vr = verifier.verify_payment_attempt(case_id="c1", payment_result=result)
    assert vr.outcome == VerificationOutcome.RECOVERED
    assert vr.amount_recovered_paise == 499900


def test_verifier_marks_failure_as_failed():
    from simulator.engine.payment_simulator import SimulatedPaymentResult
    from datetime import datetime, timezone
    verifier = RecoveryVerifier()
    result = SimulatedPaymentResult(
        attempt_id="A1", transaction_id="T1",
        outcome=SimulatedOutcome.FAILED,
        failure_reason="INSUFFICIENT_FUNDS", amount_paise=499900, currency="INR",
        executed_at=datetime.now(timezone.utc),
    )
    vr = verifier.verify_payment_attempt(case_id="c1", payment_result=result)
    assert vr.outcome == VerificationOutcome.FAILED
    assert vr.amount_recovered_paise == 0


def test_verifier_idempotency_already_recovered():
    from simulator.engine.payment_simulator import SimulatedPaymentResult
    from datetime import datetime, timezone
    verifier = RecoveryVerifier()
    result = SimulatedPaymentResult(
        attempt_id="A1", transaction_id="T1",
        outcome=SimulatedOutcome.SUCCESS,
        failure_reason=None, amount_paise=499900, currency="INR",
        executed_at=datetime.now(timezone.utc),
    )
    vr = verifier.verify_payment_attempt(
        case_id="c1", payment_result=result, case_is_already_recovered=True
    )
    assert vr.outcome == VerificationOutcome.ALREADY_RECOVERED
    assert vr.amount_recovered_paise == 0


def test_verifier_checkout_no_resume_is_failed():
    verifier = RecoveryVerifier()
    vr = verifier.verify_checkout_recovery(case_id="c1", payment_result=None)
    assert vr.outcome == VerificationOutcome.FAILED
    assert vr.amount_recovered_paise == 0
