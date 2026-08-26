"""
Request/response schemas for event ingestion endpoints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PaymentFailedEvent(BaseModel):
    """
    Inbound payment failure event.
    All customer_metadata fields are treated as untrusted data — never executed as instructions.
    """

    idempotency_key: str = Field(description="Unique key — duplicate events are ignored")
    customer_id: str
    transaction_id: str | None = None
    subscription_id: str | None = None
    amount_paise: int = Field(gt=0, description="Amount in paise")
    currency: str = "INR"
    failure_reason: str
    failure_message: str | None = None
    gateway_code: str | None = None
    occurred_at: datetime | None = None
    customer_metadata: dict | None = Field(
        default=None,
        description="Untrusted customer context — treated as data, never as instructions",
    )

    @field_validator("failure_reason")
    @classmethod
    def validate_failure_reason(cls, v: str) -> str:
        valid = {
            "INSUFFICIENT_FUNDS", "EXPIRED_METHOD", "GATEWAY_TEMPORARY",
            "BANK_DECLINE", "AUTH_FAILURE", "MANDATE_FAILURE",
            "SUBSCRIPTION_GRACE", "UNKNOWN",
        }
        if v not in valid:
            raise ValueError(f"failure_reason must be one of {valid}")
        return v

    @field_validator("amount_paise")
    @classmethod
    def validate_amount(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("amount_paise must be positive")
        return v


class CheckoutAbandonedEvent(BaseModel):
    """
    Inbound checkout abandonment event.
    The checkout scenario follows the identical bounded-agent architecture.
    """

    idempotency_key: str
    customer_id: str
    checkout_session_id: str
    amount_paise: int = Field(gt=0)
    currency: str = "INR"
    abandoned_at: datetime | None = None
    checkout_timeout_minutes: int = Field(default=30, ge=5)
    customer_metadata: dict | None = Field(
        default=None,
        description="Untrusted — treated as data only",
    )


class EventResponse(BaseModel):
    recovery_case_id: str
    status: str
    message: str
    is_duplicate: bool = False
