"""
Payment models: Subscription, PaymentMethod, Transaction, PaymentAttempt, PaymentFailure.
No real card numbers, CVVs, or banking credentials — synthetic data only.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel
from app.models.enums import FailureReason, SubscriptionStatus, TransactionStatus


class PaymentMethod(TimestampedModel):
    __tablename__ = "payment_methods"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    # Synthetic method data — no real card numbers
    method_type: Mapped[str] = mapped_column(String(50), nullable=False)  # card, upi, netbanking, wallet
    display_label: Mapped[str] = mapped_column(String(100), nullable=False)  # "•••• 4242", "upi@synthetic"
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expiry_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expiry_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="payment_methods")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="payment_method")


class Subscription(TimestampedModel):
    __tablename__ = "subscriptions"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)

    plan_name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_interval: Mapped[str] = mapped_column(String(50), nullable=False)  # monthly, annual, weekly
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)  # amount in paise
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[SubscriptionStatus] = mapped_column(String(30), nullable=False, default=SubscriptionStatus.ACTIVE)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="subscriptions")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="subscription")


class Transaction(TimestampedModel):
    __tablename__ = "transactions"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True)
    checkout_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("checkout_sessions.id"), nullable=True)

    # Idempotency key — prevents duplicate processing
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[TransactionStatus] = mapped_column(String(30), nullable=False, default=TransactionStatus.PENDING)
    failure_reason: Mapped[FailureReason | None] = mapped_column(String(50), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Simulator metadata
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    simulation_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("simulation_runs.id"), nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="transactions")
    payment_method: Mapped["PaymentMethod | None"] = relationship("PaymentMethod", back_populates="transactions")
    subscription: Mapped["Subscription | None"] = relationship("Subscription", back_populates="transactions")
    checkout_session: Mapped["CheckoutSession | None"] = relationship("CheckoutSession", back_populates="transactions")
    payment_failures: Mapped[list["PaymentFailure"]] = relationship("PaymentFailure", back_populates="transaction")


class PaymentFailure(TimestampedModel):
    __tablename__ = "payment_failures"

    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)

    failure_reason: Mapped[FailureReason] = mapped_column(String(50), nullable=False)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    gateway_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    # Processed flag — prevents duplicate case creation (idempotency)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recovery_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=True)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="payment_failures")


class CheckoutSession(TimestampedModel):
    __tablename__ = "checkout_sessions"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False, index=True)
    payment_method_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("payment_methods.id"), nullable=True)

    session_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="STARTED")

    # Abandonment / recovery tracking
    abandoned_at: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ISO timestamp
    recovery_message_sent_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    recovery_message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resumed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    recovery_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="checkout_sessions")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="checkout_session")
