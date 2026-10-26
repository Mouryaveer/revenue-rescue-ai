"""
SimulatorPaymentProvider unit tests.
Tests provider-based independent verification behavior.
"""

from app.providers.base import PaymentStatus
from app.providers.simulator_provider import SimulatorPaymentProvider


def test_get_payment_returns_stored_result():
    """Test that get_payment returns the stored PaymentResult after retry_payment."""
    provider = SimulatorPaymentProvider(seed=42)

    # Execute a retry payment
    retry_result = provider.retry_payment(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=299900,
        currency="INR",
        customer_id="cust-001",
        idempotency_key="key-001",
        retry_number=1,
        failure_reason="INSUFFICIENT_FUNDS",
    )

    # Verify get_payment returns the stored result
    payment_result = provider.get_payment(retry_result.payment_id)
    assert payment_result.payment_id == retry_result.payment_id
    assert payment_result.status == retry_result.status
    assert payment_result.amount_paise == retry_result.amount_paise
    assert payment_result.currency == retry_result.currency
    assert payment_result.is_synthetic is True


def test_get_payment_returns_pending_for_unknown_id():
    """Test that get_payment returns PENDING for unknown payment IDs."""
    provider = SimulatorPaymentProvider(seed=42)

    # Query a payment ID that was never created
    payment_result = provider.get_payment("unknown-payment-id")
    assert payment_result.payment_id == "unknown-payment-id"
    assert payment_result.status == PaymentStatus.PENDING
    assert payment_result.amount_paise == 0
    assert payment_result.currency == "INR"
    assert payment_result.is_synthetic is True


def test_check_status_returns_stored_status():
    """Test that check_status returns the stored status after retry_payment."""
    provider = SimulatorPaymentProvider(seed=42)

    # Execute a retry payment
    retry_result = provider.retry_payment(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=299900,
        currency="INR",
        customer_id="cust-001",
        idempotency_key="key-001",
        retry_number=1,
        failure_reason="INSUFFICIENT_FUNDS",
    )

    # Verify check_status returns the stored status
    status = provider.check_status(retry_result.payment_id)
    assert status == retry_result.status


def test_check_status_returns_pending_for_unknown_id():
    """Test that check_status returns PENDING for unknown payment IDs."""
    provider = SimulatorPaymentProvider(seed=42)

    # Query a payment ID that was never created
    status = provider.check_status("unknown-payment-id")
    assert status == PaymentStatus.PENDING


def test_multiple_payments_stored_separately():
    """Test that multiple payment results are stored and retrieved correctly."""
    provider = SimulatorPaymentProvider(seed=42)

    # Execute multiple retry payments
    retry_result_1 = provider.retry_payment(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=299900,
        currency="INR",
        customer_id="cust-001",
        idempotency_key="key-001",
        retry_number=1,
        failure_reason="INSUFFICIENT_FUNDS",
    )

    retry_result_2 = provider.retry_payment(
        case_id="case-002",
        original_payment_id="pay-002",
        amount_paise=499900,
        currency="INR",
        customer_id="cust-002",
        idempotency_key="key-002",
        retry_number=1,
        failure_reason="GATEWAY_TEMPORARY",
    )

    # Verify each payment can be retrieved independently
    payment_result_1 = provider.get_payment(retry_result_1.payment_id)
    assert payment_result_1.payment_id == retry_result_1.payment_id
    assert payment_result_1.amount_paise == retry_result_1.amount_paise

    payment_result_2 = provider.get_payment(retry_result_2.payment_id)
    assert payment_result_2.payment_id == retry_result_2.payment_id
    assert payment_result_2.amount_paise == retry_result_2.amount_paise
