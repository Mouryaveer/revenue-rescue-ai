"""
Recovery service — orchestrates case creation and agent execution.
Wires: Event → RecoveryCase → AgentRun → AuditTrail → DB.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agents.graph.recovery_graph import RecoveryAgent
from app.core.config import settings
from app.models.enums import (
    ActorType,
    AuditEventType,
    FailureReason,
    RecoveryCaseStatus,
    RecoveryScenario,
)
from app.models.recovery import AgentRun, RecoveryCase
from app.schemas.events import CheckoutAbandonedEvent, PaymentFailedEvent
from app.schemas.recovery import RecoveryCaseDetail
from app.services.audit_service import AuditService
from app.services.policy_service import PolicyService
from app.services.scoring_service import RecoveryScoringService

logger = structlog.get_logger(__name__)


class RecoveryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._audit = AuditService(db)

    async def get_case_by_idempotency_key(self, key: str) -> RecoveryCase | None:
        result = await self._db.execute(
            select(RecoveryCase).where(RecoveryCase.source_event_key == key)
        )
        return result.scalar_one_or_none()

    async def get_case_by_id(self, case_id: str) -> RecoveryCase | None:
        result = await self._db.execute(
            select(RecoveryCase).where(RecoveryCase.id == uuid.UUID(case_id))
        )
        return result.scalar_one_or_none()

    async def list_cases(
        self,
        status_filter: str | None = None,
        scenario: str | None = None,
        failure_reason: str | None = None,
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
        q = q.limit(limit).offset(offset)
        result = await self._db.execute(q)
        return list(result.scalars().all())

    async def _get_or_create_customer_id(self, customer_id_str: str) -> uuid.UUID:
        """Resolve customer_id string to a UUID, creating a synthetic customer stub if needed."""
        import hashlib
        from app.models.customer import Customer

        # Derive a deterministic UUID from the customer_id string
        try:
            cust_uuid = uuid.UUID(customer_id_str)
        except (ValueError, AttributeError):
            cust_uuid = uuid.UUID(hashlib.md5(customer_id_str.encode()).hexdigest())

        # Check if customer exists
        result = await self._db.execute(
            select(Customer).where(Customer.id == cust_uuid)
        )
        if result.scalar_one_or_none():
            return cust_uuid

        # Create synthetic stub
        email = f"synthetic-{cust_uuid.hex[:8]}@synthetic.invalid"
        email_hash = hashlib.sha256(email.encode()).hexdigest()

        # Avoid duplicate on email_hash
        result2 = await self._db.execute(
            select(Customer).where(Customer.email_hash == email_hash)
        )
        existing = result2.scalar_one_or_none()
        if existing:
            return existing.id

        customer = Customer(
            id=cust_uuid,
            name=f"Synthetic Customer {cust_uuid.hex[:8]}",
            email_hash=email_hash,
            email_display=email,
            segment="standard",
            country="IN",
            is_synthetic=True,
        )
        self._db.add(customer)
        await self._db.flush()
        return cust_uuid

    async def create_case_from_payment_failure(self, event: PaymentFailedEvent) -> RecoveryCase:
        scorer = RecoveryScoringService()
        score = scorer.score(
            failure_reason=event.failure_reason,
            amount_paise=event.amount_paise,
            retry_count=0,
        )
        customer_uuid = await self._get_or_create_customer_id(event.customer_id)

        case = RecoveryCase(
            customer_id=customer_uuid,
            scenario=RecoveryScenario.FAILED_PAYMENT,
            failure_reason=event.failure_reason,
            status=RecoveryCaseStatus.DETECTED,
            amount_at_risk_paise=event.amount_paise,
            amount_recovered_paise=0,
            currency=event.currency,
            recovery_score=score,
            source_event_key=event.idempotency_key,
        )
        self._db.add(case)
        await self._db.flush()

        await self._audit.record(
            event_type=AuditEventType.CASE_CREATED,
            actor=ActorType.RISK_DETECTOR,
            recovery_case_id=str(case.id),
            amount_paise=event.amount_paise,
            currency=event.currency,
            result="CREATED",
            reason=f"Payment failure: {event.failure_reason}",
        )
        return case

    async def create_case_from_checkout_abandonment(self, event: CheckoutAbandonedEvent) -> RecoveryCase:
        scorer = RecoveryScoringService()
        score = scorer.score(
            failure_reason="CHECKOUT_ABANDONED",
            amount_paise=event.amount_paise,
            retry_count=0,
        )
        customer_uuid = await self._get_or_create_customer_id(event.customer_id)

        case = RecoveryCase(
            customer_id=customer_uuid,
            scenario=RecoveryScenario.CHECKOUT_ABANDONMENT,
            failure_reason=FailureReason.CHECKOUT_ABANDONED,
            status=RecoveryCaseStatus.DETECTED,
            amount_at_risk_paise=event.amount_paise,
            amount_recovered_paise=0,
            currency=event.currency,
            recovery_score=score,
            source_event_key=event.idempotency_key,
        )
        self._db.add(case)
        await self._db.flush()

        await self._audit.record(
            event_type=AuditEventType.CASE_CREATED,
            actor=ActorType.RISK_DETECTOR,
            recovery_case_id=str(case.id),
            amount_paise=event.amount_paise,
            currency=event.currency,
            result="CREATED",
            reason="Checkout abandonment detected",
        )
        return case

    async def run_recovery_agent(self, case_id: str) -> None:
        """
        Execute the recovery agent for a case.
        Called as a background task — handles its own error isolation.
        """
        case = await self.get_case_by_id(case_id)
        if not case:
            logger.error("case_not_found_for_agent", case_id=case_id)
            return

        if case.is_recovered or case.is_stopped:
            logger.info("case_already_resolved", case_id=case_id)
            return

        policy_svc = PolicyService(self._db)
        policy_config = await policy_svc.get_active_policy_config()

        agent_run_id = str(uuid.uuid4())

        # Create agent run record
        agent_run = AgentRun(
            recovery_case_id=case.id,
            llm_provider=settings.LLM_PROVIDER,
            run_status="RUNNING",
        )
        self._db.add(agent_run)
        await self._db.flush()

        await self._audit.record(
            event_type=AuditEventType.AGENT_RUN_STARTED,
            actor=ActorType.RECOVERY_AGENT,
            recovery_case_id=case_id,
            agent_run_id=str(agent_run.id),
            result="STARTED",
        )

        # Build initial state using make_initial_state helper
        from agents.schemas.agent_schemas import make_initial_state
        initial_state = make_initial_state(
            case_id=case_id,
            agent_run_id=str(agent_run.id),
            event_type=case.scenario,
            failure_reason=case.failure_reason,
            amount_paise=case.amount_at_risk_paise,
            currency=case.currency,
            customer_id=str(case.customer_id),
            retry_count=case.retry_count,
            communication_count=case.communication_count,
            case_is_recovered=case.is_recovered,
            llm_provider=settings.LLM_PROVIDER,
        )

        try:
            agent = RecoveryAgent(
                policy=policy_config,
                llm_provider=settings.LLM_PROVIDER,
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL,
            )
            final_state = agent.run(initial_state)
            await self._apply_agent_result(case, agent_run, final_state)

        except Exception as e:
            logger.error("agent_run_failed", case_id=case_id, error=str(e))
            agent_run.run_status = "ERROR"
            agent_run.error = str(e)
            await self._db.flush()
            await self._audit.record(
                event_type=AuditEventType.AGENT_RUN_COMPLETED,
                actor=ActorType.RECOVERY_AGENT,
                recovery_case_id=case_id,
                result="ERROR",
                reason=str(e),
            )

    async def _apply_agent_result(
        self, case: RecoveryCase, agent_run: AgentRun, state: dict
    ) -> None:
        """Write agent run results back to DB and audit trail. State is a dict (TypedDict)."""
        agent_run.run_status = "COMPLETED"
        agent_run.node_trace = state.get("node_trace", [])
        strat = state.get("case_strategy")
        agent_run.llm_output = strat.model_dump() if strat else None

        # Update case state
        case.retry_count = state.get("retry_count", case.retry_count)
        case.communication_count = state.get("communication_count", case.communication_count)
        case.is_recovered = state.get("case_is_recovered", False)
        case.is_stopped = state.get("case_is_stopped", False)

        diag = state.get("case_diagnosis")
        if diag:
            case.diagnosis = diag.model_dump()
        if strat:
            case.strategy = strat.model_dump()

        policy_result = state.get("policy_result")
        if policy_result:
            case.policy_decision = policy_result.get("decision")

        verification_result = state.get("verification_result")
        if case.is_recovered and verification_result:
            case.amount_recovered_paise = verification_result.get("amount_recovered_paise", 0)
            case.status = RecoveryCaseStatus.RECOVERED
            # transaction_id from simulator is "TXN-XXXX" format (not UUID) — pass as None
            # to avoid DB cast error; the transaction ref is stored in verification_result
            raw_txn_id = verification_result.get("transaction_id")
            safe_txn_id: str | None = None
            if raw_txn_id:
                try:
                    uuid.UUID(str(raw_txn_id))
                    safe_txn_id = str(raw_txn_id)
                except (ValueError, AttributeError):
                    safe_txn_id = None  # non-UUID simulator TXN ref — skip column cast
            await self._audit.record(
                event_type=AuditEventType.REVENUE_RECOVERED,
                actor=ActorType.RECOVERY_VERIFIER,
                recovery_case_id=str(case.id),
                amount_paise=case.amount_recovered_paise,
                result="SUCCESS",
                reason=verification_result.get("reason"),
                transaction_id=safe_txn_id,
            )
        elif state.get("escalation_reason"):
            case.status = RecoveryCaseStatus.ESCALATED
            case.escalation_reason = state.get("escalation_reason")
            await self._audit.record(
                event_type=AuditEventType.ESCALATED,
                actor=ActorType.POLICY_ENGINE,
                recovery_case_id=str(case.id),
                result="ESCALATED",
                reason=state.get("escalation_reason"),
            )
        elif case.is_stopped:
            case.status = RecoveryCaseStatus.STOPPED

        await self._db.flush()
        try:
            await self._audit.record(
                event_type=AuditEventType.AGENT_RUN_COMPLETED,
                actor=ActorType.RECOVERY_AGENT,
                recovery_case_id=str(case.id),
                result="COMPLETED",
                payload={"node_trace": state.get("node_trace", [])},
            )
        except Exception as audit_err:
            logger.warning("audit_completion_record_failed", error=str(audit_err), case_id=str(case.id))

    async def escalate_case(self, case_id: str, reason: str) -> None:
        case = await self.get_case_by_id(case_id)
        if not case:
            return
        case.status = RecoveryCaseStatus.ESCALATED
        case.escalation_reason = reason
        case.is_stopped = True
        await self._db.flush()
        await self._audit.record(
            event_type=AuditEventType.ESCALATED,
            actor=ActorType.HUMAN_OPERATOR,
            recovery_case_id=case_id,
            result="ESCALATED",
            reason=reason,
        )

    async def get_audit_trail(self, case_id: str):
        from app.models.audit import AuditEvent
        result = await self._db.execute(
            select(AuditEvent)
            .where(AuditEvent.recovery_case_id == uuid.UUID(case_id))
            .order_by(AuditEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_case_with_details(self, case_id: str) -> RecoveryCaseDetail | None:
        case = await self.get_case_by_id(case_id)
        if not case:
            return None
        audit = await self.get_audit_trail(case_id)
        return RecoveryCaseDetail(
            id=str(case.id),
            scenario=case.scenario,
            failure_reason=case.failure_reason,
            status=case.status,
            amount_at_risk_paise=case.amount_at_risk_paise,
            amount_recovered_paise=case.amount_recovered_paise,
            currency=case.currency,
            retry_count=case.retry_count,
            communication_count=case.communication_count,
            recovery_score=case.recovery_score,
            customer_id=str(case.customer_id),
            is_recovered=case.is_recovered,
            is_stopped=case.is_stopped,
            created_at=case.created_at,
            updated_at=case.updated_at,
            transaction_id=str(case.transaction_id) if case.transaction_id else None,
            subscription_id=str(case.subscription_id) if case.subscription_id else None,
            checkout_session_id=str(case.checkout_session_id) if case.checkout_session_id else None,
            diagnosis=case.diagnosis,
            strategy=case.strategy,
            policy_decision=case.policy_decision,
            escalation_reason=case.escalation_reason,
            actions=[],
            agent_runs=[],
        )
