"""
Celery tasks for background recovery execution and scheduled retries.
"""

import asyncio

import structlog

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=3)
def run_recovery_agent_task(self, case_id: str) -> dict:
    """
    Background task: run the recovery agent for a case.
    Called by Celery worker — safe to retry on transient failures.
    """

    async def _run():
        from app.services.recovery_service import RecoveryService

        async with AsyncSessionLocal() as db:
            service = RecoveryService(db)
            await service.run_recovery_agent(case_id)
            await db.commit()

    try:
        asyncio.run(_run())
        return {"status": "completed", "case_id": case_id}
    except Exception as exc:
        logger.error("celery_task_failed", case_id=case_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task
def execute_simulation_task(run_db_id: str) -> dict:
    """Background task: execute a batch simulation run."""

    async def _run():
        from app.services.simulation_service import SimulationService

        async with AsyncSessionLocal() as db:
            service = SimulationService(db)
            await service.execute_run(run_db_id)
            await db.commit()

    asyncio.run(_run())
    return {"status": "completed", "run_id": run_db_id}
