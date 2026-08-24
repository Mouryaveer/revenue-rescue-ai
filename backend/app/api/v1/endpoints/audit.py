"""
Global audit trail endpoint.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.recovery import AuditEventResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get("", response_model=list[AuditEventResponse])
async def get_audit_log(
    event_type: str | None = None,
    actor: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventResponse]:
    service = AuditService(db)
    events = await service.list_events(
        event_type=event_type, actor=actor, limit=limit, offset=offset
    )
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
