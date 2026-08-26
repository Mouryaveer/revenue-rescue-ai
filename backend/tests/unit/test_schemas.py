"""
Schema validation unit tests.
Ensures Pydantic models reject invalid input at the API boundary.
"""

import pytest
import uuid
from app.schemas.events import PaymentFailedEvent, CheckoutAbandonedEvent


def test_valid_payment_failed_event():
    e = PaymentFailedEvent(
        idempotency_key="test-key-001",
        customer_id=str(uuid.uuid4()),
        amount_paise=299900,
        currency="INR",
        failure_reason="INSUFFICIENT_FUNDS",
    )
    assert e.amount_paise == 299900
    assert e.failure_reason == "INSUFFICIENT_FUNDS"


def test_invalid_failure_reason_rejected():
    with pytest.raises(Exception):
        PaymentFailedEvent(
            idempotency_key="k",
            customer_id=str(uuid.uuid4()),
            amount_paise=100000,
            currency="INR",
            failure_reason="FAKE_REASON",  # not in enum
        )


def test_zero_amount_rejected():
    with pytest.raises(Exception):
        PaymentFailedEvent(
            idempotency_key="k",
            customer_id=str(uuid.uuid4()),
            amount_paise=0,
            currency="INR",
            failure_reason="BANK_DECLINE",
        )


def test_negative_amount_rejected():
    with pytest.raises(Exception):
        PaymentFailedEvent(
            idempotency_key="k",
            customer_id=str(uuid.uuid4()),
            amount_paise=-500,
            currency="INR",
            failure_reason="BANK_DECLINE",
        )


def test_valid_checkout_abandoned_event():
    e = CheckoutAbandonedEvent(
        idempotency_key="chk-001",
        customer_id=str(uuid.uuid4()),
        checkout_session_id="sess-001",
        amount_paise=349900,
        currency="INR",
    )
    assert e.amount_paise == 349900


def test_checkout_timeout_below_minimum_rejected():
    with pytest.raises(Exception):
        CheckoutAbandonedEvent(
            idempotency_key="chk",
            customer_id=str(uuid.uuid4()),
            checkout_session_id="sess",
            amount_paise=100000,
            currency="INR",
            checkout_timeout_minutes=2,  # below min=5
        )
