"""Regression tests for the real case-bound Checkout contract."""

import hashlib
import hmac

import pytest
from pydantic import ValidationError

from app.api.v1.endpoints.razorpay_checkout import (
    CreateOrderRequest,
    VerifyPaymentRequest,
    checkout_signature,
)


def test_checkout_signature_matches_razorpay_construction() -> None:
    expected = hmac.new(
        b"test-secret",
        b"order_test|pay_test",
        hashlib.sha256,
    ).hexdigest()
    assert checkout_signature(
        order_id="order_test", payment_id="pay_test", secret="test-secret"
    ) == expected


def test_checkout_signature_changes_when_either_provider_id_changes() -> None:
    signature = checkout_signature(order_id="order_test", payment_id="pay_test", secret="test-secret")
    assert signature != checkout_signature(order_id="other", payment_id="pay_test", secret="test-secret")
    assert signature != checkout_signature(order_id="order_test", payment_id="other", secret="test-secret")


def test_order_request_is_case_bound() -> None:
    assert CreateOrderRequest(case_id="case-uuid").case_id == "case-uuid"
    with pytest.raises(ValidationError):
        CreateOrderRequest()


def test_verify_request_requires_all_checkout_callback_values() -> None:
    with pytest.raises(ValidationError):
        VerifyPaymentRequest(razorpay_payment_id="pay_only")


def test_verify_request_does_not_accept_empty_callback_values() -> None:
    with pytest.raises(ValidationError):
        VerifyPaymentRequest(
            razorpay_payment_id="",
            razorpay_order_id="order_test",
            razorpay_signature="x" * 64,
        )
