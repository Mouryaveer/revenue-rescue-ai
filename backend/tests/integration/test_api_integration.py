"""
Backend API integration tests.
These test the FastAPI endpoints without a real DB — using TestClient and mocked services.
Full DB integration tests run inside Docker via `make test`.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── Schema-level validation tests (no DB required) ────────────────────────────

def test_payment_failed_event_schema_valid():
    from app.schemas.events import PaymentFailedEvent
    e = PaymentFailedEvent(
        idempotency_key=str(uuid.uuid4()),
        customer_id=str(uuid.uuid4()),
        amount_paise=499900,
        currency="INR",
        failure_reason="INSUFFICIENT_FUNDS",
    )
    assert e.amount_paise == 499900
    assert e.failure_reason == "INSUFFICIENT_FUNDS"
    assert e.currency == "INR"


def test_checkout_abandoned_event_schema_valid():
    from app.schemas.events import CheckoutAbandonedEvent
    e = CheckoutAbandonedEvent(
        idempotency_key=str(uuid.uuid4()),
        customer_id=str(uuid.uuid4()),
        checkout_session_id=f"chk-{uuid.uuid4().hex[:8]}",
        amount_paise=349900,
        currency="INR",
    )
    assert e.amount_paise == 349900


def test_simulation_request_defaults():
    from app.schemas.recovery import SimulationRunRequest
    req = SimulationRunRequest()
    assert req.num_customers == 100
    assert req.num_events == 500
    assert req.random_seed == 42
    assert req.is_baseline is False


def test_metrics_overview_schema():
    from app.schemas.recovery import MetricsOverview
    m = MetricsOverview(
        revenue_at_risk_paise=1000000,
        revenue_recovered_paise=450000,
        recovery_rate_pct=45.0,
        active_cases=3,
        escalated_cases=2,
        recovered_cases=5,
        failed_cases=1,
        policy_violations=0,
        avg_recovery_time_hours=None,
        total_cases=11,
        by_scenario={},
        by_failure_reason={},
    )
    assert m.policy_violations == 0
    assert m.recovery_rate_pct == 45.0


def test_recovery_case_summary_schema():
    from app.schemas.recovery import RecoveryCaseSummary
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    s = RecoveryCaseSummary(
        id=str(uuid.uuid4()),
        scenario="FAILED_PAYMENT",
        failure_reason="INSUFFICIENT_FUNDS",
        status="RECOVERED",
        amount_at_risk_paise=499900,
        amount_recovered_paise=499900,
        currency="INR",
        retry_count=2,
        communication_count=0,
        recovery_score=72.5,
        customer_id=str(uuid.uuid4()),
        is_recovered=True,
        is_stopped=True,
        created_at=now,
        updated_at=now,
    )
    assert s.is_recovered is True
    assert s.amount_recovered_paise == 499900


# ── Idempotency key generation ─────────────────────────────────────────────────

def test_idempotency_key_deterministic():
    from app.core.idempotency import make_idempotency_key
    k1 = make_idempotency_key("cust-001", 499900, "INSUFFICIENT_FUNDS")
    k2 = make_idempotency_key("cust-001", 499900, "INSUFFICIENT_FUNDS")
    assert k1 == k2
    assert len(k1) == 32


def test_idempotency_key_different_for_different_inputs():
    from app.core.idempotency import make_idempotency_key
    k1 = make_idempotency_key("cust-001", 499900, "INSUFFICIENT_FUNDS")
    k2 = make_idempotency_key("cust-002", 499900, "INSUFFICIENT_FUNDS")
    assert k1 != k2


# ── Scoring service ────────────────────────────────────────────────────────────

def test_scoring_all_failure_reasons():
    from app.services.scoring_service import RecoveryScoringService
    s = RecoveryScoringService()
    for reason in ["INSUFFICIENT_FUNDS", "EXPIRED_METHOD", "GATEWAY_TEMPORARY",
                   "BANK_DECLINE", "AUTH_FAILURE", "MANDATE_FAILURE",
                   "SUBSCRIPTION_GRACE", "CHECKOUT_ABANDONED", "UNKNOWN"]:
        score = s.score(failure_reason=reason, amount_paise=299900, retry_count=0)
        assert 0 <= score <= 100, f"Score out of range for {reason}: {score}"


# ── Policy config loading ──────────────────────────────────────────────────────

def test_default_policy_loads():
    import json, pathlib
    path = pathlib.Path("policies/defaults/merchant_default_v1.json")
    assert path.exists()
    config = json.loads(path.read_text())
    assert config["policy_id"] == "merchant_default_v1"
    assert config["version"] == 1
    assert config["limits"]["max_retries"] == 3
    assert config["communication"]["respect_opt_out"] is True
    assert config["checkout"]["abandonment_timeout_minutes"] == 30


def test_default_policy_parses_as_policy_config():
    import json, pathlib
    from policies.schemas.policy_schema import PolicyConfig
    raw = json.loads(pathlib.Path("policies/defaults/merchant_default_v1.json").read_text())
    policy = PolicyConfig(**raw)
    assert policy.policy_id == "merchant_default_v1"
    assert policy.limits.max_retries == 3
    assert policy.checkout.abandonment_timeout_minutes == 30
