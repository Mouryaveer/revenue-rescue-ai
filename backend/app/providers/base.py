"""
PaymentProvider — abstract interface for all payment execution environments.

The same Recovery Agent operates against:
  - SimulatorPaymentProvider (deterministic synthetic, batch experiments)
  - RazorpayTestProvider     (Razorpay test-mode, controlled live demo)

NEVER use real/production credentials. Test mode only.
NEVER move real money.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING   = "PENDING"
    SUCCESS   = "SUCCESS"
    FAILED    = "FAILED"
    CANCELLED = "CANCELLED"


class ProviderMode(str, Enum):
    SIMULATION    = "SIMULATION"    # Deterministic synthetic simulator
    RAZORPAY_TEST = "RAZORPAY_TEST" # Razorpay test/sandbox mode


@dataclass
class PaymentResult:
    payment_id: str
    status: PaymentStatus
    amount_paise: int
    currency: str
    provider: ProviderMode
    failure_reason: str | None = None
    is_synthetic: bool = True
    raw: dict | None = None


@dataclass
class RetryResult:
    attempt_id: str
    payment_id: str
    status: PaymentStatus
    amount_paise: int
    currency: str
    provider: ProviderMode
    failure_reason: str | None = None
    is_synthetic: bool = True


class PaymentProvider(ABC):
    """
    Abstract payment provider interface.
    The Action Executor calls these methods — never calls Razorpay/simulator directly.
    """

    @property
    @abstractmethod
    def mode(self) -> ProviderMode:
        """Return which execution environment this provider targets."""

    @abstractmethod
    def get_payment(self, payment_id: str) -> PaymentResult:
        """Fetch current authoritative payment status."""

    @abstractmethod
    def retry_payment(
        self,
        *,
        case_id: str,
        original_payment_id: str,
        amount_paise: int,
        currency: str = "INR",
        customer_id: str,
        idempotency_key: str,
    ) -> RetryResult:
        """Execute a payment retry. Policy must have approved before calling this."""

    @abstractmethod
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
    ) -> RetryResult:
        """Schedule a future payment retry."""

    @abstractmethod
    def check_status(self, payment_id: str) -> PaymentStatus:
        """Lightweight status check — used by the Recovery Verifier."""

    def label(self) -> str:
        """Human-readable label for the UI environment badge."""
        return {
            ProviderMode.SIMULATION:    "SIMULATION MODE",
            ProviderMode.RAZORPAY_TEST: "RAZORPAY TEST MODE",
        }[self.mode]
