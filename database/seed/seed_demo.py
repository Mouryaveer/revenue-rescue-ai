"""
Seeded demo dataset — deterministic, reproducible (seed=42).
Creates 20 synthetic cases covering every scenario in the 5-minute demo.
Run: python -m database.seed.seed_demo

All data is SYNTHETIC. No real payments, no real customers. Ever.

Case manifest:
 1. Failed payment → insufficient funds → RECOVERED (retry #2)
 2. Failed payment → gateway temporary → RECOVERED (retry #1)
 3. Failed payment → expired card → ESCALATED (needs method update)
 4. Failed payment → bank decline → ESCALATED (3 retries failed)
 5. Failed payment → auth failure → WAITING (reminder sent)
 6. Failed subscription → mandate failure → RECOVERED
 7. Failed subscription → insufficient funds → RECOVERED
 8. Checkout abandonment → recovery message → RECOVERED
 9. Checkout abandonment → opted-out customer → STOPPED (DENIED)
10. Checkout abandonment → 2nd message → RECOVERED
11. High-value payment (₹60K) → ESCALATED (auto-limit exceeded)
12. 4th retry attempt → ESCALATED (MAX_RETRIES — red-team demo)
13. Opted-out payment reminder → STOPPED (DENIED — red-team demo)
14. Already recovered (idempotency demo)
15. UNKNOWN failure → ESCALATED (human review)
16. Suspicious activity → ESCALATED
17. Quick gateway recovery → RECOVERED
18. Subscription grace period → RECOVERED
19. Checkout timeout not reached → STOPPED (DENIED)
20. Genuinely failed recovery → FAILED
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[3] / "backend"))

from app.core.config import settings
from app.core.database import Base
from app.models.audit import AuditEvent
from app.models.enums import ActorType, AuditEventType, RecoveryScenario
from app.models.recovery import RecoveryCase
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DEMO_CASES = [
    # (scenario, failure_reason, amount_paise, status, is_recovered, description)
    (RecoveryScenario.FAILED_PAYMENT, "INSUFFICIENT_FUNDS", 499900, "RECOVERED", True, "[SYNTHETIC] Retry #2 success"),
    (RecoveryScenario.FAILED_PAYMENT, "GATEWAY_TEMPORARY", 199900, "RECOVERED", True, "[SYNTHETIC] Retry #1 success"),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "EXPIRED_METHOD",
        299900,
        "ESCALATED",
        False,
        "[SYNTHETIC] Card expired — manual update needed",
    ),
    (RecoveryScenario.FAILED_PAYMENT, "BANK_DECLINE", 899900, "ESCALATED", False, "[SYNTHETIC] 3 retries exhausted"),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "AUTH_FAILURE",
        149900,
        "WAITING",
        False,
        "[SYNTHETIC] Reminder sent — awaiting action",
    ),
    (
        RecoveryScenario.FAILED_SUBSCRIPTION,
        "MANDATE_FAILURE",
        99900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Mandate retry success",
    ),
    (
        RecoveryScenario.FAILED_SUBSCRIPTION,
        "INSUFFICIENT_FUNDS",
        199900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Subscription retry success",
    ),
    (
        RecoveryScenario.CHECKOUT_ABANDONMENT,
        "CHECKOUT_ABANDONED",
        349900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Recovery message → customer resumed",
    ),
    (
        RecoveryScenario.CHECKOUT_ABANDONMENT,
        "CHECKOUT_ABANDONED",
        249900,
        "STOPPED",
        False,
        "[SYNTHETIC] Opted-out → DENIED by policy",
    ),
    (
        RecoveryScenario.CHECKOUT_ABANDONMENT,
        "CHECKOUT_ABANDONED",
        499900,
        "RECOVERED",
        True,
        "[SYNTHETIC] 2nd message → customer resumed",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "BANK_DECLINE",
        6000000,
        "ESCALATED",
        False,
        "[SYNTHETIC] ₹60,000 exceeds auto-recovery limit",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "INSUFFICIENT_FUNDS",
        299900,
        "ESCALATED",
        False,
        "[SYNTHETIC] RED-TEAM: 4th retry → POLICY DENIED",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "INSUFFICIENT_FUNDS",
        199900,
        "STOPPED",
        False,
        "[SYNTHETIC] RED-TEAM: opted-out → DENIED",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "GATEWAY_TEMPORARY",
        99900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Idempotency demo — already recovered",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "UNKNOWN",
        399900,
        "ESCALATED",
        False,
        "[SYNTHETIC] UNKNOWN failure → human review",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "AUTH_FAILURE",
        599900,
        "ESCALATED",
        False,
        "[SYNTHETIC] Suspicious activity → automation halted",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "INSUFFICIENT_FUNDS",
        149900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Quick recovery — retry #1 success",
    ),
    (
        RecoveryScenario.FAILED_SUBSCRIPTION,
        "SUBSCRIPTION_GRACE",
        299900,
        "RECOVERED",
        True,
        "[SYNTHETIC] Grace period retry success",
    ),
    (
        RecoveryScenario.CHECKOUT_ABANDONMENT,
        "CHECKOUT_ABANDONED",
        89900,
        "STOPPED",
        False,
        "[SYNTHETIC] Timeout not reached → DENIED",
    ),
    (
        RecoveryScenario.FAILED_PAYMENT,
        "BANK_DECLINE",
        399900,
        "FAILED",
        False,
        "[SYNTHETIC] All retries exhausted — genuine failure",
    ),
]


async def seed() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with session_factory() as session:
        import hashlib

        from app.models.customer import Customer

        for i, (scenario, failure_reason, amount, status, is_recovered, desc) in enumerate(DEMO_CASES):
            # Create a stub synthetic customer for each case
            customer_id = uuid.uuid4()
            customer = Customer(
                id=customer_id,
                name=f"Demo Customer {i + 1}",
                email_hash=hashlib.sha256(f"demo{i + 1}@synthetic.test".encode()).hexdigest(),
                email_display=f"demo{i + 1}@synthetic.test",
                segment="standard",
                country="IN",
                is_synthetic=True,
            )
            session.add(customer)
            await session.flush()

            case_id = uuid.uuid4()
            case = RecoveryCase(
                id=case_id,
                customer_id=customer_id,
                scenario=scenario,
                failure_reason=failure_reason,
                status=status,
                amount_at_risk_paise=amount,
                amount_recovered_paise=amount if is_recovered else 0,
                currency="INR",
                retry_count=min(i % 3, 3),
                communication_count=0,
                recovery_score=max(10.0, 80.0 - (i * 3)),
                is_recovered=is_recovered,
                is_stopped=status in ("STOPPED", "RECOVERED", "ESCALATED", "FAILED"),
                source_event_key=f"DEMO-{i + 1:03d}-{uuid.uuid4().hex[:8]}",
                escalation_reason=desc if status == "ESCALATED" else None,
                diagnosis={
                    "diagnosis": f"fallback_{failure_reason.lower()}",
                    "diagnosis_confidence": 0.75 if failure_reason != "UNKNOWN" else 0.15,
                    "failure_category": failure_reason,
                    "likely_cause": desc,
                    "is_recoverable": is_recovered or status == "WAITING",
                    "recommended_strategy": "ESCALATE" if status == "ESCALATED" else "RETRY_NOW",
                    "needs_human_review": failure_reason == "UNKNOWN",
                    "notes": "DEMO_SEED",
                }
                if status != "DETECTED"
                else None,
                policy_decision="APPROVED"
                if is_recovered
                else ("ESCALATE" if status == "ESCALATED" else "DENIED" if status == "STOPPED" else None),
            )
            session.add(case)
            await session.flush()

            # CASE_CREATED event
            session.add(
                AuditEvent(
                    recovery_case_id=case_id,
                    event_type=AuditEventType.CASE_CREATED,
                    actor=ActorType.RISK_DETECTOR,
                    amount_paise=amount,
                    currency="INR",
                    result="CREATED",
                    reason=desc,
                )
            )

            # POLICY event
            if status in ("ESCALATED", "STOPPED"):
                session.add(
                    AuditEvent(
                        recovery_case_id=case_id,
                        event_type=AuditEventType.POLICY_DENIED
                        if status == "STOPPED"
                        else AuditEventType.POLICY_ESCALATE,
                        actor=ActorType.POLICY_ENGINE,
                        amount_paise=amount,
                        currency="INR",
                        policy_id="merchant_default_v1",
                        policy_version=1,
                        result=status,
                        reason=desc,
                    )
                )

            # REVENUE_RECOVERED event
            if is_recovered:
                session.add(
                    AuditEvent(
                        recovery_case_id=case_id,
                        event_type=AuditEventType.REVENUE_RECOVERED,
                        actor=ActorType.RECOVERY_VERIFIER,
                        amount_paise=amount,
                        currency="INR",
                        policy_id="merchant_default_v1",
                        policy_version=1,
                        result="SUCCESS",
                        reason=f"Verified by simulator — {desc}",
                    )
                )

        await session.commit()
        recovered_count = sum(1 for _, _, _, _, r, _ in DEMO_CASES if r)
        total_recovered = sum(a for _, _, a, _, r, _ in DEMO_CASES if r)
        print(f"✓ Seeded {len(DEMO_CASES)} synthetic demo cases.")
        print(f"  Recovered: {recovered_count} cases = ₹{total_recovered / 100:,.0f}")
        print("  All data is SYNTHETIC — no real payments.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
