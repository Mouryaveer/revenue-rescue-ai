"""
Recovery Verifier — authoritative recovery confirmation.

CRITICAL: Only this component can mark revenue as RECOVERED.
The LLM cannot declare recovery. Ever.
Revenue recovered = verified by simulator/DB state, not LLM claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from simulator.engine.payment_simulator import SimulatedOutcome, SimulatedPaymentResult


class VerificationOutcome(StrEnum):
    RECOVERED = "RECOVERED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    ALREADY_RECOVERED = "ALREADY_RECOVERED"


@dataclass
class VerificationResult:
    outcome: VerificationOutcome
    transaction_id: str | None
    amount_recovered_paise: int
    currency: str
    verified_at: datetime
    reason: str
    case_id: str


class RecoveryVerifier:
    """
    Reads authoritative simulator/DB state to determine if revenue was recovered.
    Never accepts LLM output as proof of recovery.
    """

    def verify_payment_attempt(
        self,
        *,
        case_id: str,
        payment_result: SimulatedPaymentResult,
        case_is_already_recovered: bool = False,
    ) -> VerificationResult:
        """
        Verify a payment attempt result.
        Returns VerificationResult with authoritative outcome.
        """
        now = datetime.now(UTC)

        if case_is_already_recovered:
            return VerificationResult(
                outcome=VerificationOutcome.ALREADY_RECOVERED,
                transaction_id=payment_result.transaction_id,
                amount_recovered_paise=0,
                currency=payment_result.currency,
                verified_at=now,
                reason="Case already marked RECOVERED — idempotency guard",
                case_id=case_id,
            )

        if payment_result.outcome == SimulatedOutcome.SUCCESS:
            return VerificationResult(
                outcome=VerificationOutcome.RECOVERED,
                transaction_id=payment_result.transaction_id,
                amount_recovered_paise=payment_result.amount_paise,
                currency=payment_result.currency,
                verified_at=now,
                reason=f"Payment verified SUCCESS by simulator — transaction {payment_result.transaction_id}",
                case_id=case_id,
            )

        return VerificationResult(
            outcome=VerificationOutcome.FAILED,
            transaction_id=payment_result.transaction_id,
            amount_recovered_paise=0,
            currency=payment_result.currency,
            verified_at=now,
            reason=f"Payment FAILED — reason: {payment_result.failure_reason}",
            case_id=case_id,
        )

    def verify_checkout_recovery(
        self,
        *,
        case_id: str,
        payment_result: SimulatedPaymentResult | None,
        case_is_already_recovered: bool = False,
    ) -> VerificationResult:
        """
        Verify checkout recovery outcome.
        payment_result=None means customer did not resume.
        """
        now = datetime.now(UTC)

        if case_is_already_recovered:
            return VerificationResult(
                outcome=VerificationOutcome.ALREADY_RECOVERED,
                transaction_id=None,
                amount_recovered_paise=0,
                currency="INR",
                verified_at=now,
                reason="Case already RECOVERED — no further action",
                case_id=case_id,
            )

        if payment_result is None:
            return VerificationResult(
                outcome=VerificationOutcome.FAILED,
                transaction_id=None,
                amount_recovered_paise=0,
                currency="INR",
                verified_at=now,
                reason="Customer did not resume checkout after recovery message",
                case_id=case_id,
            )

        return self.verify_payment_attempt(
            case_id=case_id,
            payment_result=payment_result,
            case_is_already_recovered=False,
        )
