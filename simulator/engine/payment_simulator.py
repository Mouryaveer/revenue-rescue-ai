"""
Payment Simulator — self-contained simulated payment execution engine.
No real gateways. No real credentials. No real card data. Ever.

The simulator is the AUTHORITATIVE source of transaction outcomes.
The Recovery Verifier reads simulator state — never LLM output.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from simulator.generators.payment_generator import PaymentEventGenerator


class SimulatedOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"


@dataclass
class SimulatedPaymentResult:
    attempt_id: str
    transaction_id: str
    outcome: SimulatedOutcome
    failure_reason: str | None
    amount_paise: int
    currency: str
    executed_at: datetime
    is_synthetic: bool = True
    notes: str = ""


@dataclass
class SimulatedCommunicationResult:
    message_id: str
    channel: str  # email | sms | push
    delivered: bool
    customer_resumed: bool  # did customer act on message?
    sent_at: datetime
    is_synthetic: bool = True


class PaymentSimulator:
    """
    Executes simulated payment retries and checkout recovery messages.
    Outcomes are determined by seeded RNG + failure-reason probability tables.
    """

    def __init__(self, seed: int = 42) -> None:
        self._rng = random.Random(seed)
        self._generator = PaymentEventGenerator(seed=seed)

    def execute_retry(
        self,
        *,
        case_id: str,
        customer_id: str,
        customer_segment: str,
        failure_reason: str,
        retry_number: int,
        amount_paise: int,
        currency: str = "INR",
    ) -> SimulatedPaymentResult:
        """
        Simulate a payment retry attempt.
        Returns authoritative outcome — not an LLM prediction.
        """
        from simulator.generators.customer_generator import SyntheticCustomer

        # Minimal synthetic customer object for probability lookup
        synthetic_customer = SyntheticCustomer(
            customer_id=customer_id,
            name="",
            email_display="",
            email_hash="",
            phone_display="",
            segment=customer_segment,
            country="IN",
            opted_out_communication=False,
            opted_out_email=False,
            opted_out_sms=False,
            is_suspended=False,
            total_transactions=0,
            successful_transactions=0,
            failed_transactions=0,
            lifetime_value_paise=0,
        )

        success = self._generator.simulate_retry_outcome(
            failure_reason=failure_reason,
            retry_number=retry_number,
            customer=synthetic_customer,
        )

        outcome = SimulatedOutcome.SUCCESS if success else SimulatedOutcome.FAILED
        fail_reason = None if success else failure_reason

        return SimulatedPaymentResult(
            attempt_id=f"ATT-{uuid.uuid4().hex[:8].upper()}",
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            outcome=outcome,
            failure_reason=fail_reason,
            amount_paise=amount_paise,
            currency=currency,
            executed_at=datetime.now(UTC),
            notes=f"Simulated retry #{retry_number} for case {case_id}",
        )

    def execute_checkout_recovery(
        self,
        *,
        case_id: str,
        customer_id: str,
        customer_segment: str,
        amount_paise: int,
        message_number: int = 1,
        currency: str = "INR",
    ) -> tuple[SimulatedCommunicationResult, SimulatedPaymentResult | None]:
        """
        Simulate sending a checkout recovery message and whether the customer resumes.
        Returns (communication_result, payment_result_if_resumed).
        payment_result is None if customer did not resume.
        """
        from simulator.generators.customer_generator import SyntheticCustomer

        synthetic_customer = SyntheticCustomer(
            customer_id=customer_id,
            name="",
            email_display="",
            email_hash="",
            phone_display="",
            segment=customer_segment,
            country="IN",
            opted_out_communication=False,
            opted_out_email=False,
            opted_out_sms=False,
            is_suspended=False,
            total_transactions=0,
            successful_transactions=0,
            failed_transactions=0,
            lifetime_value_paise=0,
        )

        resumed = self._generator.simulate_checkout_recovery(
            customer=synthetic_customer,
            message_number=message_number,
        )

        comm_result = SimulatedCommunicationResult(
            message_id=f"MSG-{uuid.uuid4().hex[:8].upper()}",
            channel="email",
            delivered=True,
            customer_resumed=resumed,
            sent_at=datetime.now(UTC),
        )

        if not resumed:
            return comm_result, None

        # Customer resumed — simulate the payment attempt
        # Checkout abandonment has higher success on resume than cold retry
        success = self._rng.random() < 0.80
        payment_result = SimulatedPaymentResult(
            attempt_id=f"ATT-{uuid.uuid4().hex[:8].upper()}",
            transaction_id=f"TXN-{uuid.uuid4().hex[:12].upper()}",
            outcome=SimulatedOutcome.SUCCESS if success else SimulatedOutcome.FAILED,
            failure_reason=None if success else "INSUFFICIENT_FUNDS",
            amount_paise=amount_paise,
            currency=currency,
            executed_at=datetime.now(UTC),
            notes=f"Checkout resumed for case {case_id} after recovery message #{message_number}",
        )

        return comm_result, payment_result
