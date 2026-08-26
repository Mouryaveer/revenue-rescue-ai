"""
Synthetic payment event generator.
Produces FAILED_PAYMENT, FAILED_SUBSCRIPTION, and CHECKOUT_ABANDONED events
with configurable failure-reason distribution and seeded RNG for reproducibility.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from simulator.generators.customer_generator import SyntheticCustomer

# ── Failure reason distribution weights ───────────────────────────────────────
DEFAULT_FAILURE_DISTRIBUTION = {
    "INSUFFICIENT_FUNDS": 0.35,
    "BANK_DECLINE": 0.20,
    "EXPIRED_METHOD": 0.15,
    "GATEWAY_TEMPORARY": 0.15,
    "AUTH_FAILURE": 0.10,
    "MANDATE_FAILURE": 0.03,
    "UNKNOWN": 0.02,
}

# Probability that a failure reason resolves on retry attempt N (0-indexed)
RETRY_SUCCESS_PROB = {
    "INSUFFICIENT_FUNDS": [0.0, 0.40, 0.60, 0.75],
    "BANK_DECLINE": [0.0, 0.25, 0.45, 0.55],
    "EXPIRED_METHOD": [0.0, 0.0, 0.0, 0.0],  # needs method update
    "GATEWAY_TEMPORARY": [0.0, 0.70, 0.90, 0.95],
    "AUTH_FAILURE": [0.0, 0.20, 0.35, 0.45],
    "MANDATE_FAILURE": [0.0, 0.30, 0.50, 0.65],
    "SUBSCRIPTION_GRACE": [0.0, 0.40, 0.55, 0.70],
    "UNKNOWN": [0.0, 0.10, 0.15, 0.20],
}

# Probability a checkout abandonment recovers after receiving a message
CHECKOUT_RECOVERY_PROB = {
    "standard": 0.35,
    "premium": 0.50,
    "enterprise": 0.65,
    "at_risk": 0.20,
}


@dataclass
class PaymentEvent:
    event_id: str
    event_type: str  # FAILED_PAYMENT | FAILED_SUBSCRIPTION | CHECKOUT_ABANDONED
    customer_id: str
    customer: SyntheticCustomer
    amount_paise: int
    currency: str
    failure_reason: str
    idempotency_key: str
    occurred_at: datetime
    subscription_id: str | None = None
    checkout_session_id: str | None = None
    simulation_run_id: str | None = None
    metadata: dict | None = None


class PaymentEventGenerator:
    def __init__(
        self,
        seed: int = 42,
        failure_distribution: dict[str, float] | None = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._dist = failure_distribution or DEFAULT_FAILURE_DISTRIBUTION
        self._dist_keys = list(self._dist.keys())
        self._dist_weights = [self._dist[k] for k in self._dist_keys]

    def generate_batch(
        self,
        customers: list[SyntheticCustomer],
        num_events: int,
        simulation_run_id: str | None = None,
        base_time: datetime | None = None,
    ) -> list[PaymentEvent]:
        base_time = base_time or datetime.now(UTC) - timedelta(days=7)
        events: list[PaymentEvent] = []

        for i in range(num_events):
            customer = self._rng.choice(customers)
            # Skip suspended or opted-out (they still generate events — policy handles them)
            event_type = self._rng.choices(
                ["FAILED_PAYMENT", "FAILED_SUBSCRIPTION", "CHECKOUT_ABANDONED"],
                weights=[0.55, 0.25, 0.20],
            )[0]

            failure_reason = self._pick_failure_reason(event_type)
            amount_paise = self._pick_amount(customer, event_type)
            occurred_at = base_time + timedelta(
                hours=self._rng.randint(0, 168)  # spread over 7 days
            )

            event = PaymentEvent(
                event_id=f"EVT-{i + 1:06d}",
                event_type=event_type,
                customer_id=customer.customer_id,
                customer=customer,
                amount_paise=amount_paise,
                currency="INR",
                failure_reason=failure_reason,
                idempotency_key=str(uuid.uuid4()),
                occurred_at=occurred_at,
                subscription_id=f"SUB-{self._rng.randint(1, 1000):05d}"
                if event_type == "FAILED_SUBSCRIPTION"
                else None,
                checkout_session_id=f"CHK-{self._rng.randint(1, 1000):05d}"
                if event_type == "CHECKOUT_ABANDONED"
                else None,
                simulation_run_id=simulation_run_id,
                metadata={"synthetic": True, "segment": customer.segment},
            )
            events.append(event)

        return events

    def _pick_failure_reason(self, event_type: str) -> str:
        if event_type == "FAILED_SUBSCRIPTION":
            return self._rng.choices(
                ["MANDATE_FAILURE", "INSUFFICIENT_FUNDS", "SUBSCRIPTION_GRACE", "BANK_DECLINE"],
                weights=[0.35, 0.30, 0.20, 0.15],
            )[0]
        if event_type == "CHECKOUT_ABANDONED":
            return "CHECKOUT_ABANDONED"
        return self._rng.choices(self._dist_keys, weights=self._dist_weights)[0]

    def _pick_amount(self, customer: SyntheticCustomer, event_type: str) -> int:
        """Returns amount in paise. Skewed by customer segment."""
        ranges = {
            "standard": (50_000, 500_000),  # ₹500 – ₹5,000
            "premium": (200_000, 2_000_000),  # ₹2,000 – ₹20,000
            "enterprise": (500_000, 5_000_000),  # ₹5,000 – ₹50,000
            "at_risk": (20_000, 200_000),  # ₹200 – ₹2,000
        }
        lo, hi = ranges.get(customer.segment, (50_000, 500_000))
        return self._rng.randint(lo, hi)

    def simulate_retry_outcome(
        self,
        failure_reason: str,
        retry_number: int,  # 1-indexed
        customer: SyntheticCustomer,
    ) -> bool:
        """
        Deterministically simulate whether retry attempt N succeeds.
        Used by the payment simulator to generate outcomes.
        Returns True = payment succeeds.
        """
        probs = RETRY_SUCCESS_PROB.get(failure_reason, [0.0, 0.15, 0.25, 0.35])
        idx = min(retry_number, len(probs) - 1)
        base_prob = probs[idx]

        # Customer segment modifier
        modifier = {"standard": 1.0, "premium": 1.15, "enterprise": 1.25, "at_risk": 0.75}
        adjusted = min(base_prob * modifier.get(customer.segment, 1.0), 0.99)
        return self._rng.random() < adjusted

    def simulate_checkout_recovery(
        self,
        customer: SyntheticCustomer,
        message_number: int = 1,
    ) -> bool:
        """Returns True if customer resumes checkout after recovery message."""
        base = CHECKOUT_RECOVERY_PROB.get(customer.segment, 0.30)
        # Second message has lower marginal effect
        prob = base if message_number == 1 else base * 0.5
        return self._rng.random() < prob
