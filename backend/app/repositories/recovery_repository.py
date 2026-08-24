"""
RecoveryCase repository — all DB queries for recovery cases.
Services call this; they don't write SQLAlchemy queries directly.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RecoveryCaseStatus
from app.models.recovery import RecoveryCase


class RecoveryCaseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, case_id: str) -> RecoveryCase | None:
        result = await self._db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        )
        return result.scalar_one_or_none()

    async def get_by_idempotency_key(self, key: str) -> RecoveryCase | None:
        result = await self._db.execute(
            select(RecoveryCase).where(RecoveryCase.source_event_key == key)
        )
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        status_filter: str | None = None,
        scenario: str | None = None,
        failure_reason: str | None = None,
        simulation_run_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecoveryCase]:
        q = select(RecoveryCase).order_by(RecoveryCase.created_at.desc())
        if status_filter:
            q = q.where(RecoveryCase.status == status_filter)
        if scenario:
            q = q.where(RecoveryCase.scenario == scenario)
        if failure_reason:
            q = q.where(RecoveryCase.failure_reason == failure_reason)
        if simulation_run_id:
            q = q.where(RecoveryCase.simulation_run_id == uuid.UUID(simulation_run_id))
        q = q.limit(limit).offset(offset)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        result = await self._db.execute(
            select(RecoveryCase.status, func.count(RecoveryCase.id))
            .group_by(RecoveryCase.status)
        )
        return {row[0]: row[1] for row in result.all()}

    async def total_recovered_paise(
        self, simulation_run_id: str | None = None
    ) -> int:
        q = select(func.coalesce(func.sum(RecoveryCase.amount_recovered_paise), 0)).where(
            RecoveryCase.is_recovered == True  # noqa: E712
        )
        if simulation_run_id:
            q = q.where(RecoveryCase.simulation_run_id == uuid.UUID(simulation_run_id))
        result = await self._db.execute(q)
        return result.scalar_one() or 0

    async def total_at_risk_paise(
        self, simulation_run_id: str | None = None
    ) -> int:
        q = select(func.coalesce(func.sum(RecoveryCase.amount_at_risk_paise), 0))
        if simulation_run_id:
            q = q.where(RecoveryCase.simulation_run_id == uuid.UUID(simulation_run_id))
        result = await self._db.execute(q)
        return result.scalar_one() or 0
