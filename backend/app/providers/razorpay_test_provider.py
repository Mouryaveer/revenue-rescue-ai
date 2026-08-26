"""
RazorpayTestProvider — Razorpay test/sandbox mode adapter.

SAFETY RULES (non-negotiable):
- ONLY test-mode credentials (RAZORPAY_KEY_ID starts with "rzp_test_")
- NEVER production keys
- NEVER real customer data
- NEVER real card numbers (use Razorpay test card numbers only)
- All transactions are clearly labeled TEST MODE in the UI

This provider is available ONLY when:
  PAYMENT_PROVIDER=razorpay_test
  RAZORPAY_KEY_ID is set AND starts with "rzp_test_"
  RAZORPAY_KEY_SECRET is set

If credentials are missing or are production keys, falls back to SIMULATION.
"""

from __future__ import annotations

import structlog

from app.providers.base import (
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    ProviderMode,
    RetryResult,
)

logger = structlog.get_logger(__name__)


class RazorpayTestProvider(PaymentProvider):
    """
    Razorpay test-mode payment provider.
    Uses Razorpay's sandbox/test environment only.
    Never moves real money.
    """

    def __init__(self, key_id: str, key_secret: str) -> None:
        self._validate_test_credentials(key_id, key_secret)
        self._key_id = key_id
        self._key_secret = key_secret
        self._client = self._init_client(key_id, key_secret)
        logger.info("razorpay_test_provider_initialized", key_id_prefix=key_id[:12])

    @staticmethod
    def _validate_test_credentials(key_id: str, key_secret: str) -> None:
        """Hard check: reject any non-test credentials."""
        if not key_id or not key_secret:
            raise ValueError("Razorpay credentials not configured. Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET.")
        if not key_id.startswith("rzp_test_"):
            raise ValueError(
                f"SAFETY: Razorpay key '{key_id[:12]}...' does not appear to be a test key. "
                "Only keys starting with 'rzp_test_' are allowed. "
                "RazorpayTestProvider refuses to operate with production credentials."
            )

    @staticmethod
    def _init_client(key_id: str, key_secret: str):
        try:
            import razorpay

            return razorpay.Client(auth=(key_id, key_secret))
        except ImportError:
            logger.warning("razorpay_sdk_not_installed", msg="Install razorpay package: pip install razorpay")
            return None

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.RAZORPAY_TEST

    def get_payment(self, payment_id: str) -> PaymentResult:
        if not self._client:
            return self._unavailable(payment_id)
        try:
            payment = self._client.payment.fetch(payment_id)
            status = self._map_status(payment.get("status", "failed"))
            return PaymentResult(
                payment_id=payment_id,
                status=status,
                amount_paise=payment.get("amount", 0),
                currency=payment.get("currency", "INR"),
                provider=self.mode,
                failure_reason=payment.get("error_code"),
                is_synthetic=False,
                raw=payment,
            )
        except Exception as e:
            logger.error("razorpay_get_payment_failed", payment_id=payment_id, error=str(e))
            return self._unavailable(payment_id)

    def retry_payment(
        self,
        *,
        case_id: str,
        original_payment_id: str,
        amount_paise: int,
        currency: str = "INR",
        customer_id: str,
        idempotency_key: str,
        **kwargs,
    ) -> RetryResult:
        """
        Create a new Razorpay test-mode payment order.
        Uses test card: 4111111111111111 (standard Razorpay test card).
        """
        if not self._client:
            return self._unavailable_retry(idempotency_key)
        try:
            order = self._client.order.create(
                {
                    "amount": amount_paise,
                    "currency": currency,
                    "receipt": idempotency_key[:40],
                    "notes": {
                        "case_id": case_id,
                        "customer_id": customer_id,
                        "environment": "TEST_MODE",
                        "original_payment_id": original_payment_id,
                    },
                }
            )
            logger.info("razorpay_test_order_created", order_id=order["id"], amount=amount_paise, case_id=case_id)
            # Note: full payment capture requires frontend integration (Razorpay checkout)
            # For API-only test, order creation demonstrates the integration
            return RetryResult(
                attempt_id=order["id"],
                payment_id=order["id"],
                status=PaymentStatus.PENDING,  # Pending frontend capture
                amount_paise=amount_paise,
                currency=currency,
                provider=self.mode,
                is_synthetic=False,
            )
        except Exception as e:
            logger.error("razorpay_retry_failed", case_id=case_id, error=str(e))
            return self._unavailable_retry(idempotency_key)

    def schedule_retry(self, **kwargs) -> RetryResult:
        return self.retry_payment(**kwargs)

    def check_status(self, payment_id: str) -> PaymentStatus:
        result = self.get_payment(payment_id)
        return result.status

    @staticmethod
    def _map_status(razorpay_status: str) -> PaymentStatus:
        return {
            "captured": PaymentStatus.SUCCESS,
            "authorized": PaymentStatus.PENDING,
            "created": PaymentStatus.PENDING,
            "failed": PaymentStatus.FAILED,
            "refunded": PaymentStatus.CANCELLED,
        }.get(razorpay_status, PaymentStatus.FAILED)

    @staticmethod
    def _unavailable(payment_id: str) -> PaymentResult:
        return PaymentResult(
            payment_id=payment_id,
            status=PaymentStatus.FAILED,
            amount_paise=0,
            currency="INR",
            provider=ProviderMode.RAZORPAY_TEST,
            failure_reason="PROVIDER_UNAVAILABLE",
            is_synthetic=False,
        )

    @staticmethod
    def _unavailable_retry(idempotency_key: str) -> RetryResult:
        return RetryResult(
            attempt_id=idempotency_key,
            payment_id="",
            status=PaymentStatus.FAILED,
            amount_paise=0,
            currency="INR",
            provider=ProviderMode.RAZORPAY_TEST,
            failure_reason="PROVIDER_UNAVAILABLE",
            is_synthetic=False,
        )


def get_payment_provider(
    provider_name: str = "simulator",
    razorpay_key_id: str = "",
    razorpay_key_secret: str = "",  # nosec B107 — empty default, real value from env
    simulator_seed: int = 42,
) -> PaymentProvider:
    """
    Factory — returns the correct PaymentProvider based on config.
    Falls back to SimulatorPaymentProvider if Razorpay credentials are missing/invalid.
    """
    from app.providers.simulator_provider import SimulatorPaymentProvider

    if provider_name == "razorpay_test":
        try:
            return RazorpayTestProvider(razorpay_key_id, razorpay_key_secret)
        except ValueError as e:
            logger.warning("razorpay_provider_fallback", reason=str(e))
            return SimulatorPaymentProvider(seed=simulator_seed)

    return SimulatorPaymentProvider(seed=simulator_seed)
