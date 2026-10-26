"""
SimulatorPaymentProvider — wraps the existing PaymentSimulator.
Used for all batch experiments and when PAYMENT_PROVIDER=simulator.
All data is synthetic. No real money. No real credentials.
"""

from __future__ import annotations

import uuid

import structlog

from app.providers.base import (
    OrderResult,
    PaymentProvider,
    PaymentResult,
    PaymentStatus,
    ProviderMode,
    RetryResult,
)
from simulator.engine.payment_simulator import PaymentSimulator, SimulatedOutcome

logger = structlog.get_logger(__name__)


class SimulatorPaymentProvider(PaymentProvider):
    """
    Deterministic synthetic payment provider.
    Wraps the existing PaymentSimulator for use through the PaymentProvider interface.
    """

    def __init__(self, seed: int = 42, customer_segment: str = "standard") -> None:
        self._simulator = PaymentSimulator(seed=seed)
        self._default_segment = customer_segment
        self._payment_results: dict[str, PaymentResult] = {}

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.SIMULATION

    def get_payment(self, payment_id: str) -> PaymentResult:
        # Return stored result if available, otherwise PENDING for unknown IDs
        if payment_id in self._payment_results:
            return self._payment_results[payment_id]
        return PaymentResult(
            payment_id=payment_id,
            status=PaymentStatus.PENDING,
            amount_paise=0,
            currency="INR",
            provider=self.mode,
            is_synthetic=True,
        )

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str = "INR",
        case_id: str,
        customer_id: str,
        notes: dict | None = None,
    ) -> OrderResult:
        """Create a simulated order for a recovery case."""
        # Generate a synthetic order ID
        order_id = f"order_sim_{uuid.uuid4().hex[:16]}"

        logger.info(
            "simulator_order_created",
            order_id=order_id,
            amount=amount_paise,
            case_id=case_id,
        )

        return OrderResult(
            order_id=order_id,
            amount_paise=amount_paise,
            currency=currency,
            provider=self.mode,
            is_synthetic=True,
        )

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
        retry_number = kwargs.get("retry_number", 1)
        failure_reason = kwargs.get("failure_reason", "UNKNOWN")
        customer_segment = kwargs.get("customer_segment", None)

        result = self._simulator.execute_retry(
            case_id=case_id,
            customer_id=customer_id,
            customer_segment=customer_segment or self._default_segment,
            failure_reason=failure_reason,
            retry_number=retry_number,
            amount_paise=amount_paise,
            currency=currency,
        )
        retry_result = RetryResult(
            attempt_id=result.attempt_id,
            payment_id=result.transaction_id,
            status=PaymentStatus.SUCCESS
            if result.outcome == SimulatedOutcome.SUCCESS
            else PaymentStatus.FAILED,
            amount_paise=result.amount_paise,
            currency=currency,
            provider=self.mode,
            failure_reason=result.failure_reason,
            is_synthetic=True,
        )
        # Store the payment result for later retrieval by get_payment
        self._payment_results[retry_result.payment_id] = PaymentResult(
            payment_id=retry_result.payment_id,
            status=retry_result.status,
            amount_paise=retry_result.amount_paise,
            currency=retry_result.currency,
            provider=retry_result.provider,
            failure_reason=retry_result.failure_reason,
            is_synthetic=True,
        )
        return retry_result

    def schedule_retry(
        self,
        *,
        case_id: str,
        original_payment_id: str,
        amount_paise: int,
        currency: str = "INR",
        customer_id: str,
        delay_hours: int,
        idempotency_key: str,
        **kwargs,
    ) -> RetryResult:
        # Simulator executes immediately (no real scheduling)
        return self.retry_payment(
            case_id=case_id,
            original_payment_id=original_payment_id,
            amount_paise=amount_paise,
            currency=currency,
            customer_id=customer_id,
            idempotency_key=idempotency_key,
            **kwargs,
        )

    def check_status(self, payment_id: str) -> PaymentStatus:
        # Return stored status if available, otherwise PENDING for unknown IDs
        if payment_id in self._payment_results:
            return self._payment_results[payment_id].status
        return PaymentStatus.PENDING
