"""
Celery tasks for background recovery execution and scheduled retries.
"""

import asyncio

import structlog

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal, engine

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, max_retries=2)  # 3 attempts total
def run_recovery_agent_task(self, agent_run_id: str) -> dict:
    """
    Execute a started AgentRun (status RUNNING) in the Celery worker.

    Idempotent: runs that are no longer RUNNING are skipped. Earlier attempts
    re-raise so Celery retries; the final attempt marks the run ERROR instead.
    Payment retries reuse the same provider idempotency key across attempts,
    because case.retry_count is only advanced on success.
    """
    from app.services.agent_dispatch import execute_agent_run_in_new_session

    final_attempt = self.request.retries >= self.max_retries

    async def _run() -> str:
        try:
            return await execute_agent_run_in_new_session(agent_run_id, final_attempt=final_attempt)
        finally:
            # Each asyncio.run() creates a new event loop; pooled asyncpg
            # connections bound to the old loop must not be reused.
            await engine.dispose()

    try:
        status = asyncio.run(_run())
        return {"status": status, "agent_run_id": agent_run_id}
    except Exception as exc:
        logger.error(
            "celery_task_failed",
            agent_run_id=agent_run_id,
            attempt=self.request.retries + 1,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=60) from exc


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
