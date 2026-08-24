"""
Customer model — stores synthetic customer data only. No real PII beyond email hash.
"""

import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel


class Customer(TimestampedModel):
    __tablename__ = "customers"

    # Synthetic identity — no real card/banking data stored
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    email_display: Mapped[str] = mapped_column(String(255), nullable=False)  # synthetic email
    phone_display: Mapped[str] = mapped_column(String(50), nullable=True)    # synthetic phone
    segment: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    country: Mapped[str] = mapped_column(String(10), nullable=False, default="IN")

    # Preferences / compliance
    opted_out_communication: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_out_email: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_out_sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Payment history summary (denormalized for quick scoring)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lifetime_value_paise: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # in paise

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="customer")
    payment_methods: Mapped[list["PaymentMethod"]] = relationship("PaymentMethod", back_populates="customer")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="customer")
    checkout_sessions: Mapped[list["CheckoutSession"]] = relationship("CheckoutSession", back_populates="customer")
    recovery_cases: Mapped[list["RecoveryCase"]] = relationship("RecoveryCase", back_populates="customer")
