"""
Baseline simulator tests — verifies the comparison baseline works correctly.
"""

from simulator.engine.baseline_simulator import BaselineSimulator
from simulator.generators.customer_generator import CustomerGenerator
from simulator.generators.payment_generator import PaymentEventGenerator


def setup_events(n: int = 100, seed: int = 42):
    cg = CustomerGenerator(seed=seed)
    customers = cg.generate(20)
    pg = PaymentEventGenerator(seed=seed)
    return pg.generate_batch(customers, n)


def test_baseline_runs_all_events():
    events = setup_events(50)
    bl = BaselineSimulator(seed=42)
    results = bl.run_batch(events)
    assert len(results) == 50


def test_baseline_always_retries_once():
    events = setup_events(50)
    bl = BaselineSimulator(seed=42)
    results = bl.run_batch(events)
    assert all(r.retry_count == 1 for r in results)


def test_baseline_metrics_computed_correctly():
    events = setup_events(100)
    bl = BaselineSimulator(seed=42)
    results = bl.run_batch(events)
    metrics = BaselineSimulator.compute_metrics(results)

    assert metrics["mode"] == "BASELINE"
    assert metrics["total_events"] == 100
    assert metrics["recovered_count"] + metrics["failed_count"] == 100
    assert 0.0 <= metrics["recovery_rate_pct"] <= 100.0
    assert metrics["policy_violations"] == 0
    assert metrics["avg_retries"] == 1.0


def test_baseline_recovery_rate_is_real():
    """Recovery rate must be computed from actual simulation — not fabricated."""
    events = setup_events(200)
    bl = BaselineSimulator(seed=42)
    results = bl.run_batch(events)
    metrics = BaselineSimulator.compute_metrics(results)

    recovered_paise = sum(r.amount_recovered for r in results if r.outcome == "RECOVERED")
    at_risk_paise = sum(r.amount_paise for r in results)
    expected_rate = recovered_paise / at_risk_paise * 100 if at_risk_paise else 0

    assert abs(metrics["recovery_rate_pct"] - expected_rate) < 0.01


def test_baseline_reproducible():
    """Same seed produces same results every time."""
    events = setup_events(50, seed=99)
    r1 = BaselineSimulator(seed=99).run_batch(events)
    r2 = BaselineSimulator(seed=99).run_batch(events)
    assert [r.outcome for r in r1] == [r.outcome for r in r2]
