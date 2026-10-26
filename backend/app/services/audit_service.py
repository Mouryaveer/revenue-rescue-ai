"""
Audit service — append-only event ledger.
Write once. Never update. Never delete.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.enums import ActorType, AuditEventType

logger = structlog.get_logger(__name__)


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(
        self,
        *,
        event_type: AuditEventType,
        actor: ActorType,
        recovery_case_id: str | None = None,
        transaction_id: str | None = None,
        amount_paise: int | None = None,
        currency: str = "INR",
        policy_id: str | None = None,
        policy_version: int | None = None,
        result: str | None = None,
        reason: str | None = None,
        correlation_id: str | None = None,
        agent_run_id: str | None = None,
        actor_id: str | None = None,
        payload: dict | None = None,
    ) -> AuditEvent:
        """
        Append an audit event. Never updates existing events.
        On write failure: logs the failure and raises — caller must handle safely.
        """
        event = AuditEvent(
            recovery_case_id=uuid.UUID(recovery_case_id) if recovery_case_id else None,
            event_type=event_type,
            actor=actor,
            actor_id=actor_id,
            transaction_id=uuid.UUID(transaction_id) if transaction_id else None,
            amount_paise=amount_paise,
            currency=currency,
            policy_id=policy_id,
            policy_version=policy_version,
            result=result,
            reason=reason,
            correlation_id=correlation_id,
            agent_run_id=uuid.UUID(agent_run_id) if agent_run_id else None,
            payload=payload,
        )

        try:
            self._db.add(event)
            await self._db.flush()
            logger.info(
                "audit_event_recorded",
                event_type=event_type,
                actor=actor,
                case_id=recovery_case_id,
                result=result,
            )
            return event
        except Exception as e:
            # Audit write failure — log loudly, do not silently swallow
            logger.error(
                "audit_write_failure",
                event_type=event_type,
                error=str(e),
                recovery_case_id=recovery_case_id,
            )
            raise

    async def list_events(
        self,
        event_type: str | None = None,
        actor: str | None = None,
        recovery_case_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]:
        q = select(AuditEvent).order_by(AuditEvent.created_at.desc())
        if event_type:
            q = q.where(AuditEvent.event_type == event_type)
        if actor:
            q = q.where(AuditEvent.actor == actor)
        if recovery_case_id:
            q = q.where(AuditEvent.recovery_case_id == uuid.UUID(recovery_case_id))
        q = q.limit(limit).offset(offset)
        result = await self._db.execute(q)
        return list(result.scalars().all())
