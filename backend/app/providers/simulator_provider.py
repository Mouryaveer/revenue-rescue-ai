"""
SimulatorPaymentProvider — wraps the existing PaymentSimulator.
Used for all batch experiments and when PAYMENT_PROVIDER=simulator.
All data is synthetic. No real money. No real credentials.
"""

from __future__ import annotations

import uuid

from app.providers.base import PaymentProvider, PaymentResult, PaymentStatus, ProviderMode, RetryResult
from simulator.engine.payment_simulator import PaymentSimulator, SimulatedOutcome


class SimulatorPaymentProvider(PaymentProvider):
    """
    Deterministic synthetic payment provider.
    Wraps the existing PaymentSimulator for use through the PaymentProvider interface.
    """

    def __init__(self, seed: int = 42, customer_segment: str = "standard") -> None:
        self._simulator = PaymentSimulator(seed=seed)
        self._default_segment = customer_segment

    @property
    def mode(self) -> ProviderMode:
        return ProviderMode.SIMULATION

    def get_payment(self, payment_id: str) -> PaymentResult:
        # In simulator mode, payment state is ephemeral — always return PENDING
        # Real state comes from the DB after retry execution
        return PaymentResult(
            payment_id=payment_id,
            status=PaymentStatus.PENDING,
            amount_paise=0,
            currency="INR",
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
        retry_number: int = 1,
        failure_reason: str = "UNKNOWN",
        customer_segment: str | None = None,
    ) -> RetryResult:
        result = self._simulator.execute_retry(
            case_id=case_id,
            customer_id=customer_id,
            customer_segment=customer_segment or self._default_segment,
            failure_reason=failure_reason,
            retry_number=retry_number,
            amount_paise=amount_paise,
            currency=currency,
        )
        return RetryResult(
            attempt_id=result.attempt_id,
            payment_id=result.transaction_id,
            status=PaymentStatus.SUCCESS if result.outcome == SimulatedOutcome.SUCCESS else PaymentStatus.FAILED,
            amount_paise=result.amount_paise,
            currency=currency,
            provider=self.mode,
            failure_reason=result.failure_reason,
            is_synthetic=True,
        )

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
        retry_number: int = 1,
        failure_reason: str = "UNKNOWN",
        customer_segment: str | None = None,
    ) -> RetryResult:
        # Simulator executes immediately (no real scheduling)
        return self.retry_payment(
            case_id=case_id,
            original_payment_id=original_payment_id,
            amount_paise=amount_paise,
            currency=currency,
            customer_id=customer_id,
            idempotency_key=idempotency_key,
            retry_number=retry_number,
            failure_reason=failure_reason,
            customer_segment=customer_segment,
        )

    def check_status(self, payment_id: str) -> PaymentStatus:
        # Simulator has no persistent state per payment_id
        return PaymentStatus.PENDING
