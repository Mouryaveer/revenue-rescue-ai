"""
Agent run dispatch: decides where a recovery agent run executes.

The AgentRun row (status RUNNING) is created and committed in the request, so its
id can be returned immediately and polled. Execution then happens either in the
Celery worker (AGENT_EXECUTION_BACKEND="celery") or in-process via FastAPI
BackgroundTasks ("inline", the default; also the fallback if enqueueing fails).
"""

from __future__ import annotations

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.recovery_service import RecoveryService

logger = structlog.get_logger(__name__)


async def dispatch_agent_run(
    db: AsyncSession, case_id: str, background_tasks: BackgroundTasks
) -> str | None:
    """Create a RUNNING AgentRun for the case and schedule its execution."""
    agent_run_id = await RecoveryService(db).start_agent_run(case_id)
    if agent_run_id is None:
        return None
    # Commit so another session (background task or worker) can see the run.
    await db.commit()

    if settings.AGENT_EXECUTION_BACKEND == "celery":
        try:
            from app.tasks import run_recovery_agent_task

            run_recovery_agent_task.delay(agent_run_id)
            logger.info("agent_run_enqueued", agent_run_id=agent_run_id, case_id=case_id)
            return agent_run_id
        except Exception as e:
            logger.error(
                "agent_enqueue_failed_running_inline",
                agent_run_id=agent_run_id,
                case_id=case_id,
                error=str(e),
            )

    background_tasks.add_task(run_agent_inline, agent_run_id)
    return agent_run_id


async def execute_agent_run_in_new_session(agent_run_id: str, *, final_attempt: bool = True) -> str:
    """Execute an AgentRun with its own DB session; commits on success."""
    async with AsyncSessionLocal() as db:
        try:
            status = await RecoveryService(db).execute_agent_run(
                agent_run_id, final_attempt=final_attempt
            )
            await db.commit()
            return status
        except Exception:
            await db.rollback()
            raise


async def run_agent_inline(agent_run_id: str) -> None:
    """BackgroundTasks entry point: never raises into the ASGI server."""
    try:
        await execute_agent_run_in_new_session(agent_run_id)
    except Exception as e:
        logger.error("background_agent_error", agent_run_id=agent_run_id, error=str(e))
