"""Persisted Razorpay webhook receipts.  event_id is the replay-protection key."""

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TimestampedModel


class ProviderWebhook(TimestampedModel):
    __tablename__ = "provider_webhooks"

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
