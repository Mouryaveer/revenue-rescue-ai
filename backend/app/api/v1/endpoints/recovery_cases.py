"""
Recovery case endpoints.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.recovery import AuditEventResponse, RecoveryCaseDetail, RecoveryCaseSummary
from app.services.recovery_service import RecoveryService

router = APIRouter()


@router.get("", response_model=list[RecoveryCaseSummary])
async def list_cases(
    status_filter: str | None = Query(None, alias="status"),
    scenario: str | None = None,
    failure_reason: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[RecoveryCaseSummary]:
    service = RecoveryService(db)
    cases = await service.list_cases(
        status_filter=status_filter,
        scenario=scenario,
        failure_reason=failure_reason,
        limit=limit,
        offset=offset,
    )
    return [_to_summary(c) for c in cases]


@router.get("/{case_id}", response_model=RecoveryCaseDetail)
async def get_case(case_id: str, db: AsyncSession = Depends(get_db)) -> RecoveryCaseDetail:
    service = RecoveryService(db)
    case = await service.get_case_with_details(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    return case


@router.post("/{case_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_agent(
    case_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RecoveryService(db)
    case = await service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    if case.is_recovered or case.is_stopped:
        return {"status": "NOOP", "message": "Case already resolved"}
    background_tasks.add_task(_run_agent_task, case_id)
    return {"status": "ACCEPTED", "message": "Agent run queued"}


async def _run_agent_task(case_id: str) -> None:
    """Runs in background with its own DB session."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            service = RecoveryService(db)
            await service.run_recovery_agent(case_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            import structlog

            structlog.get_logger(__name__).error("background_agent_failed", case_id=case_id, error=str(e))


@router.post("/{case_id}/escalate", status_code=status.HTTP_200_OK)
async def escalate_case(
    case_id: str,
    reason: str = "Manual escalation by operator",
    db: AsyncSession = Depends(get_db),
) -> dict:
    service = RecoveryService(db)
    await service.escalate_case(case_id, reason)
    return {"status": "ESCALATED", "case_id": case_id}


@router.get("/{case_id}/audit", response_model=list[AuditEventResponse])
async def get_audit_trail(
    case_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    service = RecoveryService(db)
    events = await service.get_audit_trail(case_id)
    return [
        AuditEventResponse(
            id=str(e.id),
            event_type=e.event_type,
            actor=e.actor,
            amount_paise=e.amount_paise,
            policy_version=e.policy_version,
            result=e.result,
            reason=e.reason,
            transaction_id=str(e.transaction_id) if e.transaction_id else None,
            created_at=e.created_at,
        )
        for e in events
    ]


def _to_summary(c) -> RecoveryCaseSummary:
    return RecoveryCaseSummary(
        id=str(c.id),
        scenario=c.scenario,
        failure_reason=c.failure_reason,
        status=c.status,
        amount_at_risk_paise=c.amount_at_risk_paise,
        amount_recovered_paise=c.amount_recovered_paise,
        currency=c.currency,
        retry_count=c.retry_count,
        communication_count=c.communication_count,
        recovery_score=c.recovery_score,
        customer_id=str(c.customer_id),
        is_recovered=c.is_recovered,
        is_stopped=c.is_stopped,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )
