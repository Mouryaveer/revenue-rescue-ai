"""
Demo Mode endpoints.
Provides 7 deterministic scenarios for a controlled 5-minute demo.
Reset reseeds the demo data. All data is synthetic.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()

DEMO_SCENARIOS = [
    {
        "id": "demo-001",
        "name": "Insufficient Funds → Delayed Retry → Recovered",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "amount_paise": 499900,
        "expected": "RECOVERED",
        "description": "Customer had insufficient funds. Agent schedules retry after 24h. Payment succeeds on retry #2.",
    },
    {
        "id": "demo-002",
        "name": "Gateway Failure → Immediate Retry → Recovered",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "GATEWAY_TEMPORARY",
        "amount_paise": 199900,
        "expected": "RECOVERED",
        "description": "Temporary gateway issue. Agent retries immediately. Payment succeeds first attempt.",
    },
    {
        "id": "demo-003",
        "name": "4th Retry Proposed → Policy Blocks → Escalated",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "BANK_DECLINE",
        "amount_paise": 299900,
        "expected": "ESCALATED",
        "description": "RED-TEAM: Agent proposes 4th retry. Policy Engine rejects (MAX_RETRIES). Executor does NOT fire. Audit records the denial.",
    },
    {
        "id": "demo-004",
        "name": "Checkout Abandoned → Recovery Message → Recovered",
        "scenario": "CHECKOUT_ABANDONMENT",
        "failure_reason": "CHECKOUT_ABANDONED",
        "amount_paise": 349900,
        "expected": "RECOVERED",
        "description": "Customer abandoned checkout. Agent sends recovery message. Customer resumes. Payment succeeds.",
    },
    {
        "id": "demo-005",
        "name": "High-Value Transaction → Human Escalation",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "BANK_DECLINE",
        "amount_paise": 6000000,
        "expected": "ESCALATED",
        "description": "₹60,000 exceeds auto-recovery limit. Policy escalates immediately to human operator.",
    },
    {
        "id": "demo-006",
        "name": "Customer Opted Out → No Communication",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "amount_paise": 149900,
        "expected": "STOPPED",
        "description": "RED-TEAM: Customer opted out of contact. Policy denies all communication attempts. Hard stop.",
    },
    {
        "id": "demo-007",
        "name": "Payment Already Succeeded → Agent Stops Immediately",
        "scenario": "FAILED_PAYMENT",
        "failure_reason": "GATEWAY_TEMPORARY",
        "amount_paise": 99900,
        "expected": "STOPPED",
        "description": "Payment succeeded before agent ran. Recovery Verifier confirms. Agent stops — no duplicate action.",
    },
]


@router.get("/scenarios")
async def list_demo_scenarios() -> list[dict]:
    """Return all 7 demo scenarios with descriptions."""
    return DEMO_SCENARIOS


@router.post("/reset")
async def reset_demo(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset demo data — reseed all 20 deterministic demo cases."""
    background_tasks.add_task(_reset_demo_task)
    return {"status": "ACCEPTED", "message": "Demo reset queued — takes ~5 seconds"}


async def _reset_demo_task() -> None:
    """Background task: drop and reseed demo data."""
    import pathlib
    import sys

    sys.path.insert(0, str(pathlib.Path(__file__).parents[6]))
    sys.path.insert(0, str(pathlib.Path(__file__).parents[6] / "backend"))
    try:
        from database.seed.seed_demo import seed

        await seed()
        logger.info("demo_reset_complete")
    except Exception as e:
        logger.error("demo_reset_failed", error=str(e))


@router.post("/run/{scenario_id}")
async def run_demo_scenario(
    scenario_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger a specific demo scenario end-to-end."""
    scenario = next((s for s in DEMO_SCENARIOS if s["id"] == scenario_id), None)
    if not scenario:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Demo scenario {scenario_id} not found")

    import uuid

    from app.schemas.events import CheckoutAbandonedEvent, PaymentFailedEvent
    from app.services.recovery_service import RecoveryService

    ikey = f"demo-{scenario_id}-{uuid.uuid4().hex[:8]}"

    if scenario["scenario"] == "CHECKOUT_ABANDONMENT":
        event = CheckoutAbandonedEvent(
            idempotency_key=ikey,
            customer_id=f"demo-cust-{scenario_id}",
            checkout_session_id=f"demo-sess-{scenario_id}",
            amount_paise=scenario["amount_paise"],
            currency="INR",
            checkout_timeout_minutes=0,  # already elapsed in demo
        )
        service = RecoveryService(db)
        case = await service.create_case_from_checkout_abandonment(event)
    else:
        event = PaymentFailedEvent(
            idempotency_key=ikey,
            customer_id=f"demo-cust-{scenario_id}",
            amount_paise=scenario["amount_paise"],
            currency="INR",
            failure_reason=scenario["failure_reason"],
        )
        service = RecoveryService(db)
        case = await service.create_case_from_payment_failure(event)

    from app.api.v1.endpoints.events import _run_agent_background

    background_tasks.add_task(_run_agent_background, str(case.id))

    return {
        "case_id": str(case.id),
        "scenario": scenario,
        "status": "RUNNING",
        "message": f"Demo scenario '{scenario['name']}' started",
    }
