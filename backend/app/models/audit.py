"""
AuditEvent — append-only event ledger.
Never update or delete rows in this table.
"""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedModel
from app.models.enums import ActorType, AuditEventType


class AuditEvent(TimestampedModel):
    __tablename__ = "audit_events"

    recovery_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recovery_cases.id"), nullable=True, index=True
    )

    event_type: Mapped[AuditEventType] = mapped_column(String(100), nullable=False, index=True)
    actor: Mapped[ActorType] = mapped_column(String(100), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # user id or service id

    # Financial fields
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="INR")

    # Policy
    policy_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Result
    result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Correlation
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Full event payload snapshot
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    recovery_case: Mapped["RecoveryCase | None"] = relationship("RecoveryCase", back_populates="audit_events")
