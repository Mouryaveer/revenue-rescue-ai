"""Case-bound Razorpay Test Mode Checkout and verification endpoints."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.enums import ActorType, AuditEventType, RecoveryCaseStatus
from app.models.recovery import RecoveryCase
from app.providers.base import PaymentStatus
from app.providers.razorpay_test_provider import get_payment_provider
from app.services.audit_service import AuditService

logger = structlog.get_logger(__name__)
router = APIRouter()


def checkout_signature(*, order_id: str, payment_id: str, secret: str) -> str:
    """Build the server-side Checkout HMAC; secrets never leave this function."""
    return hmac.new(
        secret.encode("utf-8"),
        f"{order_id}|{payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


class CreateOrderRequest(BaseModel):
    case_id: str = Field(min_length=1, max_length=64)


class CreateOrderResponse(BaseModel):
    order_id: str
    amount_paise: int
    currency: str
    key_id: str
    case_id: str
    provider: str


class VerifyPaymentRequest(BaseModel):
    razorpay_payment_id: str = Field(min_length=1, max_length=128)
    razorpay_order_id: str = Field(min_length=1, max_length=128)
    razorpay_signature: str = Field(min_length=64, max_length=128)
    case_id: str | None = Field(default=None, max_length=64)


class VerifyPaymentResponse(BaseModel):
    status: str
    case_id: str | None = None
    amount_recovered_paise: int | None = None
    message: str | None = None


async def _reconcile_captured_payment(
    *,
    db: AsyncSession,
    case: RecoveryCase,
    payment_id: str,
    order_id: str,
    source: str,
    event_id: str | None = None,
) -> VerifyPaymentResponse:
    """Reconcile only provider-fetched state; callers must already authenticate input."""
    if case.is_recovered:
        return VerifyPaymentResponse(
            status="already_verified",
            case_id=str(case.id),
            amount_recovered_paise=case.amount_recovered_paise,
            message="Payment was already independently verified",
        )
    try:
        provider = get_payment_provider(
            provider_name="razorpay_test",
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
            razorpay_key_secret=settings.RAZORPAY_KEY_SECRET,
        )
        payment = provider.get_payment(payment_id)
    except Exception as exc:
        logger.error("provider_verification_failed", case_id=str(case.id), error=str(exc))
        return VerifyPaymentResponse(
            status="verification_failed",
            case_id=str(case.id),
            message="Provider verification failed",
        )

    raw = payment.raw or {}
    if raw.get("order_id") != order_id:
        raise HTTPException(status_code=400, detail="Payment order ID mismatch")
    if payment.amount_paise != case.amount_at_risk_paise:
        raise HTTPException(status_code=400, detail="Payment amount mismatch")
    if payment.currency.upper() != case.currency.upper():
        raise HTTPException(status_code=400, detail="Payment currency mismatch")
    if payment.status is not PaymentStatus.SUCCESS:
        return VerifyPaymentResponse(
            status="pending" if payment.status is PaymentStatus.PENDING else "verification_failed",
            case_id=str(case.id),
            message="Payment is not captured; revenue remains unrecovered",
        )

    case.razorpay_payment_id = payment_id
    case.provider_payment_status = str(raw.get("status", "captured"))
    case.provider_payment_timestamp = datetime.now(UTC)
    case.amount_recovered_paise = payment.amount_paise
    case.status = RecoveryCaseStatus.RECOVERED
    case.is_recovered = True
    case.is_stopped = True
    payload = {
        "razorpay_order_id": order_id,
        "razorpay_payment_id": payment_id,
        "provider": "razorpay_test",
        "source": source,
    }
    if event_id:
        payload["razorpay_event_id"] = event_id
    audit = AuditService(db)
    await audit.record(
        event_type=AuditEventType.PAYMENT_SUCCESS,
        actor=ActorType.RECOVERY_VERIFIER,
        recovery_case_id=str(case.id),
        amount_paise=payment.amount_paise,
        currency=case.currency,
        result="PROVIDER_CAPTURED",
        payload=payload,
    )
    await audit.record(
        event_type=AuditEventType.REVENUE_RECOVERED,
        actor=ActorType.RECOVERY_VERIFIER,
        recovery_case_id=str(case.id),
        amount_paise=payment.amount_paise,
        currency=case.currency,
        result="VERIFIED",
        reason="Captured payment confirmed by Razorpay API",
        payload=payload,
    )
    await db.commit()
    return VerifyPaymentResponse(
        status="recovered",
        case_id=str(case.id),
        amount_recovered_paise=payment.amount_paise,
        message="Payment captured and independently verified by Razorpay",
    )


@router.post("/orders", response_model=CreateOrderResponse)
async def create_order(
    request: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateOrderResponse:
    if not settings.razorpay_test_ready:
        raise HTTPException(status_code=503, detail="Razorpay Test Mode is not configured")
    try:
        case_uuid = uuid.UUID(request.case_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid case_id") from exc

    result = await db.execute(
        select(RecoveryCase).where(RecoveryCase.id == case_uuid).with_for_update()
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    if (
        case.status
        in {
            RecoveryCaseStatus.RECOVERED,
            RecoveryCaseStatus.STOPPED,
            RecoveryCaseStatus.ESCALATED,
        }
        or case.is_recovered
        or case.is_stopped
    ):
        raise HTTPException(status_code=409, detail="Recovery case is terminal")
    if case.razorpay_order_id:
        return CreateOrderResponse(
            order_id=case.razorpay_order_id,
            amount_paise=case.amount_at_risk_paise,
            currency=case.currency,
            key_id=settings.RAZORPAY_KEY_ID,
            case_id=str(case.id),
            provider="RAZORPAY_TEST",
        )

    try:
        provider = get_payment_provider(
            provider_name="razorpay_test",
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
            razorpay_key_secret=settings.RAZORPAY_KEY_SECRET,
        )
        order = provider.create_order(
            amount_paise=case.amount_at_risk_paise,
            currency=case.currency,
            case_id=str(case.id),
            customer_id=str(case.customer_id),
            notes={"failure_reason": str(case.failure_reason), "scenario": str(case.scenario)},
        )
        case.razorpay_order_id = order.order_id
        await db.commit()
        await db.refresh(case)
        return CreateOrderResponse(
            order_id=order.order_id,
            amount_paise=order.amount_paise,
            currency=order.currency,
            key_id=settings.RAZORPAY_KEY_ID,
            case_id=str(case.id),
            provider=order.provider.value,
        )
    except ValueError as exc:
        await db.rollback()
        logger.error("razorpay_order_creation_failed", case_id=str(case.id), error=str(exc))
        raise HTTPException(status_code=502, detail="Razorpay order creation failed") from exc


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    request: VerifyPaymentRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyPaymentResponse:
    if not settings.razorpay_test_ready:
        raise HTTPException(status_code=503, detail="Razorpay Test Mode is not configured")

    result = await db.execute(
        select(RecoveryCase)
        .where(RecoveryCase.razorpay_order_id == request.razorpay_order_id)
        .with_for_update()
    )
    case = result.scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="No recovery case found for this order")
    order_id = case.razorpay_order_id
    if order_id is None:
        raise HTTPException(status_code=409, detail="Recovery case has no Razorpay order")
    if request.case_id and request.case_id != str(case.id):
        raise HTTPException(status_code=400, detail="Case does not own this order")

    expected = checkout_signature(
        order_id=order_id,
        payment_id=request.razorpay_payment_id,
        secret=settings.RAZORPAY_KEY_SECRET,
    )
    if not hmac.compare_digest(expected, request.razorpay_signature):
        await AuditService(db).record(
            event_type=AuditEventType.UNAUTHORIZED_ACTION_ATTEMPT,
            actor=ActorType.SYSTEM,
            recovery_case_id=str(case.id),
            result="REJECTED",
            reason="Invalid Razorpay Checkout signature",
        )
        await db.commit()
        raise HTTPException(status_code=400, detail="Invalid payment signature")

    if case.is_recovered:
        if case.razorpay_payment_id != request.razorpay_payment_id:
            raise HTTPException(
                status_code=400, detail="Payment does not match the verified case payment"
            )
        return VerifyPaymentResponse(
            status="already_verified",
            case_id=str(case.id),
            amount_recovered_paise=case.amount_recovered_paise,
            message="Payment was already independently verified",
        )

    return await _reconcile_captured_payment(
        db=db,
        case=case,
        payment_id=request.razorpay_payment_id,
        order_id=order_id,
        source="checkout_callback",
    )


@router.get("/health")
async def razorpay_health() -> dict:
    return {
        "status": "healthy" if settings.razorpay_test_ready else "unavailable",
        "provider": "razorpay_test" if settings.razorpay_test_ready else settings.PAYMENT_PROVIDER,
        "test_mode": settings.razorpay_test_ready,
        "key_configured": bool(settings.RAZORPAY_KEY_ID),
    }
