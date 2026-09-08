"""
RazorpayTestProvider unit tests.
Tests the Razorpay test provider implementation.
"""

import pytest
from unittest.mock import MagicMock, patch

from app.providers.razorpay_test_provider import RazorpayTestProvider, get_payment_provider
from app.providers.base import PaymentStatus, ProviderMode


def test_razorpay_test_provider_initialization_with_valid_test_credentials():
    """Test provider initialization with valid test credentials."""
    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )
    assert provider.mode == ProviderMode.RAZORPAY_TEST
    assert provider._key_id == "rzp_test_12345678"
    assert provider._key_secret == "test_secret"


def test_razorpay_test_provider_rejects_missing_credentials():
    """Test that provider rejects missing credentials."""
    with pytest.raises(ValueError):
        RazorpayTestProvider(key_id="", key_secret="test_secret")

    with pytest.raises(ValueError):
        RazorpayTestProvider(key_id="rzp_test_12345678", key_secret="")


def test_razorpay_test_provider_rejects_production_credentials():
    """Test that provider rejects production credentials."""
    with pytest.raises(ValueError):
        RazorpayTestProvider(key_id="rzp_live_12345678", key_secret="live_secret")

    with pytest.raises(ValueError):
        RazorpayTestProvider(key_id="some_other_key", key_secret="secret")


def test_razorpay_test_provider_handles_missing_razorpay_sdk():
    """Test that provider handles missing Razorpay SDK gracefully."""
    with patch('app.providers.razorpay_test_provider.razorpay', None):
        provider = RazorpayTestProvider(
            key_id="rzp_test_12345678",
            key_secret="test_secret"
        )
        assert provider._client is None


def test_get_payment_unavailable_when_client_missing():
    """Test get_payment returns unavailable when client is missing."""
    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )
    provider._client = None

    result = provider.get_payment("pay_12345678")

    assert result.payment_id == "pay_12345678"
    assert result.status == PaymentStatus.FAILED
    assert result.amount_paise == 0
    assert result.currency == "INR"
    assert result.provider == ProviderMode.RAZORPAY_TEST
    assert result.failure_reason == "PROVIDER_UNAVAILABLE"
    assert result.is_synthetic is False


@patch('app.providers.razorpay_test_provider.razorpay')
def test_get_payment_success(mock_razorpay):
    """Test get_payment returns correct result for successful payment."""
    mock_client = MagicMock()
    mock_client.payment.fetch.return_value = {
        "id": "pay_12345678",
        "amount": 499900,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay.Client.return_value = mock_client

    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )

    result = provider.get_payment("pay_12345678")

    assert result.payment_id == "pay_12345678"
    assert result.status == PaymentStatus.SUCCESS
    assert result.amount_paise == 499900
    assert result.currency == "INR"
    assert result.provider == ProviderMode.RAZORPAY_TEST
    assert result.is_synthetic is False


@patch('app.providers.razorpay_test_provider.razorpay')
def test_get_payment_failed(mock_razorpay):
    """Test get_payment returns correct result for failed payment."""
    mock_client = MagicMock()
    mock_client.payment.fetch.return_value = {
        "id": "pay_12345678",
        "amount": 499900,
        "currency": "INR",
        "status": "failed",
        "error_code": "BAD_REQUEST_ERROR",
    }
    mock_razorpay.Client.return_value = mock_client

    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )

    result = provider.get_payment("pay_12345678")

    assert result.payment_id == "pay_12345678"
    assert result.status == PaymentStatus.FAILED
    assert result.amount_paise == 499900
    assert result.failure_reason == "BAD_REQUEST_ERROR"


@patch('app.providers.razorpay_test_provider.razorpay')
def test_get_payment_pending(mock_razorpay):
    """Test get_payment returns correct result for pending payment."""
    mock_client = MagicMock()
    mock_client.payment.fetch.return_value = {
        "id": "pay_12345678",
        "amount": 499900,
        "currency": "INR",
        "status": "authorized",
    }
    mock_razorpay.Client.return_value = mock_client

    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )

    result = provider.get_payment("pay_12345678")

    assert result.payment_id == "pay_12345678"
    assert result.status == PaymentStatus.PENDING


@patch('app.providers.razorpay_test_provider.razorpay')
def test_retry_payment_success(mock_razorpay):
    """Test retry_payment creates order successfully."""
    mock_client = MagicMock()
    mock_client.order.create.return_value = {
        "id": "order_12345678",
        "amount": 499900,
        "currency": "INR",
        "receipt": "receipt-001",
        "status": "created",
    }
    mock_razorpay.Client.return_value = mock_client

    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )

    result = provider.retry_payment(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=499900,
        currency="INR",
        customer_id="cust-001",
        idempotency_key="key-001",
    )

    assert result.attempt_id == "order_12345678"
    assert result.payment_id == "order_12345678"
    assert result.status == PaymentStatus.PENDING
    assert result.amount_paise == 499900
    assert result.currency == "INR"
    assert result.provider == ProviderMode.RAZORPAY_TEST
    assert result.is_synthetic is False

    # Verify order was created with correct data
    mock_client.order.create.assert_called_once()
    call_args = mock_client.order.create.call_args[0][0]
    assert call_args["amount"] == 499900
    assert call_args["currency"] == "INR"
    assert call_args["receipt"] == "key-001"
    assert call_args["notes"]["case_id"] == "case-001"
    assert call_args["notes"]["customer_id"] == "cust-001"
    assert call_args["notes"]["environment"] == "TEST_MODE"
    assert call_args["notes"]["original_payment_id"] == "pay-001"


def test_retry_payment_unavailable_when_client_missing():
    """Test retry_payment returns unavailable when client is missing."""
    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )
    provider._client = None

    result = provider.retry_payment(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=499900,
        currency="INR",
        customer_id="cust-001",
        idempotency_key="key-001",
    )

    assert result.attempt_id == "key-001"
    assert result.payment_id == ""
    assert result.status == PaymentStatus.FAILED
    assert result.amount_paise == 0
    assert result.failure_reason == "PROVIDER_UNAVAILABLE"


@patch('app.providers.razorpay_test_provider.razorpay')
def test_check_status(mock_razorpay):
    """Test check_status returns correct payment status."""
    mock_client = MagicMock()
    mock_client.payment.fetch.return_value = {
        "id": "pay_12345678",
        "amount": 499900,
        "currency": "INR",
        "status": "captured",
    }
    mock_razorpay.Client.return_value = mock_client

    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )

    status = provider.check_status("pay_12345678")
    assert status == PaymentStatus.SUCCESS


def test_schedule_retry_delegates_to_retry_payment():
    """Test that schedule_retry delegates to retry_payment."""
    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )
    provider._client = None

    result = provider.schedule_retry(
        case_id="case-001",
        original_payment_id="pay-001",
        amount_paise=499900,
        currency="INR",
        customer_id="cust-001",
        delay_hours=24,
        idempotency_key="key-001",
    )

    # Should return the same as retry_payment
    assert result.attempt_id == "key-001"
    assert result.status == PaymentStatus.FAILED


def test_get_payment_provider_factory_razorpay_test():
    """Test get_payment_provider factory returns RazorpayTestProvider."""
    provider = get_payment_provider(
        provider_name="razorpay_test",
        razorpay_key_id="rzp_test_12345678",
        razorpay_key_secret="test_secret"
    )

    assert isinstance(provider, RazorpayTestProvider)
    assert provider.mode == ProviderMode.RAZORPAY_TEST


def test_get_payment_provider_factory_simulator():
    """Test get_payment_provider factory returns SimulatorPaymentProvider."""
    provider = get_payment_provider(
        provider_name="simulator",
        razorpay_key_id="rzp_test_12345678",
        razorpay_key_secret="test_secret"
    )

    assert provider.mode == ProviderMode.SIMULATION


def test_get_payment_provider_factory_unknown():
    """Test get_payment_provider factory raises error for unknown provider."""
    with pytest.raises(ValueError):
        get_payment_provider(
            provider_name="unknown_provider",
            razorpay_key_id="rzp_test_12345678",
            razorpay_key_secret="test_secret"
        )


def test_map_status_captured():
    """Test status mapping for captured payments."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("captured") == PaymentStatus.SUCCESS


def test_map_status_authorized():
    """Test status mapping for authorized payments."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("authorized") == PaymentStatus.PENDING


def test_map_status_created():
    """Test status mapping for created payments."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("created") == PaymentStatus.PENDING


def test_map_status_failed():
    """Test status mapping for failed payments."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("failed") == PaymentStatus.FAILED


def test_map_status_refunded():
    """Test status mapping for refunded payments."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("refunded") == PaymentStatus.CANCELLED


def test_map_status_unknown():
    """Test status mapping for unknown payment statuses."""
    from app.providers.razorpay_test_provider import RazorpayTestProvider
    assert RazorpayTestProvider._map_status("unknown_status") == PaymentStatus.FAILED


def test_provider_label():
    """Test provider label method."""
    provider = RazorpayTestProvider(
        key_id="rzp_test_12345678",
        key_secret="test_secret"
    )
    assert provider.label() == "RAZORPAY TEST MODE"
