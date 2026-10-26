"""
Event ingestion endpoints.
POST /events/payment-failed
POST /events/checkout-abandoned

Idempotency: duplicate idempotency_key returns 200 with is_duplicate=True — no double processing.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.events import CheckoutAbandonedEvent, EventResponse, PaymentFailedEvent
from app.services.agent_dispatch import dispatch_agent_run
from app.services.recovery_service import RecoveryService

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post(
    "/payment-failed",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a payment failure event",
)
async def payment_failed(
    event: PaymentFailedEvent,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """
    Ingest a payment failure and create a recovery case.
    Idempotent — duplicate idempotency_key returns existing case without reprocessing.
    All customer_metadata is treated as untrusted data.
    """
    service = RecoveryService(db)

    # Idempotency check
    existing = await service.get_case_by_idempotency_key(event.idempotency_key)
    if existing:
        logger.info("duplicate_event_ignored", idempotency_key=event.idempotency_key)
        return EventResponse(
            recovery_case_id=str(existing.id),
            status="DUPLICATE",
            message="Duplicate event — existing case returned",
            is_duplicate=True,
        )

    case = await service.create_case_from_payment_failure(event)
    await db.commit()
    agent_run_id = await dispatch_agent_run(db, str(case.id), background_tasks)

    logger.info(
        "payment_failed_event_accepted", case_id=str(case.id), idempotency_key=event.idempotency_key
    )
    return EventResponse(
        recovery_case_id=str(case.id),
        status="ACCEPTED",
        message="Recovery case created — agent running",
        agent_run_id=agent_run_id,
    )


@router.post(
    "/checkout-abandoned",
    response_model=EventResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a checkout abandonment event",
)
async def checkout_abandoned(
    event: CheckoutAbandonedEvent,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> EventResponse:
    """
    Ingest a checkout abandonment and create a recovery case.
    Same bounded-agent architecture as payment failures.
    """
    service = RecoveryService(db)

    existing = await service.get_case_by_idempotency_key(event.idempotency_key)
    if existing:
        return EventResponse(
            recovery_case_id=str(existing.id),
            status="DUPLICATE",
            message="Duplicate checkout event — existing case returned",
            is_duplicate=True,
        )

    case = await service.create_case_from_checkout_abandonment(event)
    await db.commit()
    agent_run_id = await dispatch_agent_run(db, str(case.id), background_tasks)

    logger.info("checkout_abandoned_event_accepted", case_id=str(case.id))
    return EventResponse(
        recovery_case_id=str(case.id),
        status="ACCEPTED",
        message="Checkout recovery case created — agent running",
        agent_run_id=agent_run_id,
    )
