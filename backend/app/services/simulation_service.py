"""
Simulation service — runs batch experiments.
All results computed from real simulation execution — never fabricated.
Reproducible via random_seed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.simulation import SimulationRun
from app.schemas.recovery import SimulationRunRequest

logger = structlog.get_logger(__name__)

AGENT_VERSION = "0.1.0"
DATASET_VERSION = "1.0.0"


async def execute_run_standalone(run_db_id: str) -> None:
    """Background entrypoint — must not reuse the request-scoped session."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = SimulationService(db)
        try:
            await service.execute_run(run_db_id)
            await db.commit()
        except Exception:
            await db.rollback()
            raise


class SimulationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_run(self, request: SimulationRunRequest) -> SimulationRun:
        run = SimulationRun(
            simulation_id=f"SIM-{uuid.uuid4().hex[:8].upper()}",
            label=request.label,
            random_seed=request.random_seed,
            policy_version="1.0.0",
            agent_version=AGENT_VERSION,
            dataset_version=DATASET_VERSION,
            num_customers=request.num_customers,
            num_events=request.num_events,
            failure_rate=request.failure_rate,
            is_baseline=request.is_baseline,
            config=request.config,
            status="PENDING",
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def execute_run(self, run_db_id: str) -> None:
        """
        Execute the batch simulation.
        Generates synthetic events, runs recovery (or baseline), records results.
        """
        from simulator.generators.customer_generator import CustomerGenerator
        from simulator.generators.payment_generator import PaymentEventGenerator
        from simulator.engine.payment_simulator import PaymentSimulator, SimulatedOutcome
        from simulator.engine.recovery_verifier import RecoveryVerifier, VerificationOutcome
        from app.services.policy_service import PolicyService
        from agents.graph.recovery_graph import RecoveryAgent
        from agents.schemas.agent_schemas import make_initial_state as _make_state  # noqa: F401 (used in loop)
        from app.core.config import settings

        result = await self._db.execute(
            select(SimulationRun).where(SimulationRun.id == uuid.UUID(run_db_id))
        )
        run = result.scalar_one_or_none()
        if not run:
            return

        run.status = "RUNNING"
        await self._db.flush()

        try:
            seed = run.random_seed
            cust_gen = CustomerGenerator(seed=seed)
            pay_gen = PaymentEventGenerator(seed=seed)
            simulator = PaymentSimulator(seed=seed)
            verifier = RecoveryVerifier()

            customers = cust_gen.generate(run.num_customers)
            events = pay_gen.generate_batch(
                customers=customers,
                num_events=run.num_events,
                simulation_run_id=run.simulation_id,
            )

            policy_svc = PolicyService(self._db)
            policy_config = await policy_svc.get_active_policy_config()

            total_at_risk = sum(e.amount_paise for e in events)
            total_recovered = 0
            recovered_cases = 0
            escalated_cases = 0
            policy_violations = 0
            baseline = None

            for i, event in enumerate(events):
                if run.is_baseline:
                    from simulator.engine.baseline_simulator import BaselineSimulator

                    if i == 0:
                        baseline = BaselineSimulator(seed=seed)
                    bl_result = baseline._process_event(event)
                    recovered = bl_result.outcome == "RECOVERED"
                else:
                    from agents.schemas.agent_schemas import make_initial_state
                    state = make_initial_state(
                        case_id=f"sim-{run.simulation_id}-{i}",
                        agent_run_id=str(uuid.uuid4()),
                        event_type=event.event_type,
                        failure_reason=event.failure_reason,
                        amount_paise=event.amount_paise,
                        currency=event.currency,
                        customer_id=event.customer_id,
                        customer_segment=event.customer.segment,
                        customer_opted_out=event.customer.opted_out_communication,
                        customer_suspended=event.customer.is_suspended,
                        checkout_timeout_elapsed=event.event_type == "CHECKOUT_ABANDONED",
                        llm_provider=settings.LLM_PROVIDER,
                    )
                    agent = RecoveryAgent(
                        policy=policy_config,
                        llm_provider=settings.LLM_PROVIDER,
                        api_key=settings.OPENAI_API_KEY,
                        simulator_seed=seed + i,
                    )
                    final = agent.run(state)
                    recovered = final.get("case_is_recovered", False)
                    if final.get("escalation_reason"):
                        escalated_cases += 1
                    decision = (final.get("policy_result") or {}).get("decision")
                    if decision == "DENIED":
                        policy_violations += 1

                if recovered:
                    total_recovered += event.amount_paise
                    recovered_cases += 1

                # Update progress
                if i % max(1, run.num_events // 20) == 0:
                    run.progress_pct = (i / run.num_events) * 100
                    await self._db.flush()

            run.status = "COMPLETED"
            run.progress_pct = 100.0
            run.revenue_at_risk_paise = total_at_risk
            run.revenue_recovered_paise = total_recovered
            run.recovery_rate_pct = round(total_recovered / total_at_risk * 100, 2) if total_at_risk > 0 else 0.0
            run.total_cases = len(events)
            run.recovered_cases = recovered_cases
            run.escalated_cases = escalated_cases
            run.policy_violations = policy_violations
            run.results = {
                "revenue_at_risk_paise": total_at_risk,
                "revenue_recovered_paise": total_recovered,
                "recovery_rate_pct": run.recovery_rate_pct,
                "simulation_id": run.simulation_id,
                "seed": seed,
                "note": "All numbers computed from real simulation execution",
            }
            await self._db.flush()
            logger.info("simulation_completed", simulation_id=run.simulation_id, rate=run.recovery_rate_pct)

        except Exception as e:
            run.status = "FAILED"
            run.error = str(e)
            await self._db.flush()
            logger.error("simulation_failed", error=str(e))

    async def get_run(self, simulation_id: str) -> SimulationRun | None:
        result = await self._db.execute(
            select(SimulationRun).where(SimulationRun.simulation_id == simulation_id)
        )
        return result.scalar_one_or_none()

    async def list_runs(self) -> list[dict]:
        result = await self._db.execute(
            select(SimulationRun).order_by(SimulationRun.created_at.desc())
        )
        runs = []
        for r in result.scalars().all():
            runs.append({
                "simulation_id": r.simulation_id,
                "label": r.label,
                "status": r.status,
                "is_baseline": r.is_baseline,
                "num_events": r.num_events,
                "random_seed": r.random_seed,
                "progress_pct": r.progress_pct or 0.0,
                "recovery_rate_pct": r.recovery_rate_pct or 0.0,
                "revenue_at_risk_paise": r.revenue_at_risk_paise or 0,
                "revenue_recovered_paise": r.revenue_recovered_paise or 0,
                "total_cases": r.total_cases or 0,
                "recovered_cases": r.recovered_cases or 0,
                "escalated_cases": r.escalated_cases or 0,
                "policy_violations": r.policy_violations or 0,
                "results": r.results,
                "created_at": r.created_at,
            })
        return runs
