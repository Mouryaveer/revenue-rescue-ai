"""
Synthetic customer generator.
All data is faker-generated. No real PII ever stored.
Seeded RNG ensures reproducible datasets across runs.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field

from faker import Faker


@dataclass
class SyntheticCustomer:
    customer_id: str
    name: str
    email_display: str          # synthetic email — not real
    email_hash: str             # sha256 of synthetic email
    phone_display: str
    segment: str                # standard | premium | enterprise | at_risk
    country: str
    opted_out_communication: bool
    opted_out_email: bool
    opted_out_sms: bool
    is_suspended: bool
    total_transactions: int
    successful_transactions: int
    failed_transactions: int
    lifetime_value_paise: int   # in paise
    is_synthetic: bool = True


SEGMENTS = ["standard", "standard", "standard", "premium", "premium", "enterprise", "at_risk"]


class CustomerGenerator:
    def __init__(self, seed: int = 42) -> None:
        self._fake = Faker("en_IN")
        self._rng = random.Random(seed)
        Faker.seed(seed)

    def generate(self, count: int) -> list[SyntheticCustomer]:
        return [self._make_customer(i) for i in range(count)]

    def _make_customer(self, idx: int) -> SyntheticCustomer:
        rng = self._rng
        fake = self._fake

        name = fake.name()
        email = fake.email()
        email_hash = hashlib.sha256(email.encode()).hexdigest()
        phone = fake.phone_number()
        segment = rng.choice(SEGMENTS)

        total_txn = rng.randint(1, 50)
        success_rate = {"standard": 0.85, "premium": 0.92, "enterprise": 0.95, "at_risk": 0.60}[segment]
        successful = round(total_txn * success_rate)
        failed = total_txn - successful
        ltv = successful * rng.randint(50000, 500000)  # paise per txn

        opt_out_rate = 0.05 if segment != "at_risk" else 0.15
        opted_out = rng.random() < opt_out_rate

        return SyntheticCustomer(
            customer_id=f"CUST-{idx+1:05d}",
            name=name,
            email_display=email,
            email_hash=email_hash,
            phone_display=phone,
            segment=segment,
            country="IN",
            opted_out_communication=opted_out,
            opted_out_email=opted_out,
            opted_out_sms=opted_out,
            is_suspended=rng.random() < 0.01,
            total_transactions=total_txn,
            successful_transactions=successful,
            failed_transactions=failed,
            lifetime_value_paise=ltv,
        )
