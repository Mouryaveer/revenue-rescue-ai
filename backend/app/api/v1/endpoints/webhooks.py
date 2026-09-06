"""Razorpay Test Mode webhooks: raw-body HMAC validation and replay protection."""

from __future__ import annotations

import hashlib
import hmac
import json

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.recovery import RecoveryCase
from app.models.webhook import ProviderWebhook

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(None),
    x_razorpay_event_id: str | None = Header(None),
    x_razorpay_event: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept Razorpay events only after raw-body signature validation.

    A provider event id is stored behind a unique constraint before side effects,
    making duplicate delivery safe even with concurrent requests.  Unknown events
    are retained as processed receipts but never interpreted as payment success.
    """
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Webhook receiver is not configured")
    if not x_razorpay_signature or not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="Missing Razorpay signature or event id")

    raw = await request.body()
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        logger.warning("razorpay_webhook_signature_invalid", event_id=x_razorpay_event_id)
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON payload") from exc

    receipt = ProviderWebhook(
        provider="razorpay", event_id=x_razorpay_event_id,
        event_type=x_razorpay_event or payload.get("event", "unknown"),
        signature_valid=True, payload=payload,
    )
    try:
        db.add(receipt)
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"status": "DUPLICATE", "event_id": x_razorpay_event_id}

    receipt.processed = True
    event_type = str(receipt.event_type)
    entity = ((payload.get("payload") or {}).get("payment") or {}).get("entity") or {}
    payment_id = entity.get("id")
    order_id = entity.get("order_id")
    if event_type == "payment.captured" and payment_id and order_id:
        result = await db.execute(
            select(RecoveryCase)
            .where(RecoveryCase.razorpay_order_id == str(order_id))
            .with_for_update()
        )
        case = result.scalar_one_or_none()
        if case:
            from app.api.v1.endpoints.razorpay_checkout import _reconcile_captured_payment

            reconciliation = await _reconcile_captured_payment(
                db=db,
                case=case,
                payment_id=str(payment_id),
                order_id=str(order_id),
                source="webhook",
                event_id=x_razorpay_event_id,
            )
            logger.info(
                "razorpay_webhook_reconciled",
                event_id=x_razorpay_event_id,
                case_id=str(case.id),
                reconciliation_status=reconciliation.status,
            )
        else:
            logger.info("razorpay_webhook_unmatched_order", event_id=x_razorpay_event_id)
    logger.info("razorpay_webhook_received", event_id=x_razorpay_event_id, event_type=receipt.event_type)
    return {"status": "ACCEPTED", "event_id": x_razorpay_event_id}
