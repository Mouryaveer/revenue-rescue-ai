"""
Agent run execution and dispatch tests (improve-architecture Requirement 2). No DB/broker:
session, audit, and Celery are mocked.
"""

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

RUN_ID = str(uuid.uuid4())
CASE_ID = uuid.uuid4()


def _service(run, case=None):
    from app.services.recovery_service import RecoveryService

    db = MagicMock()
    db.flush = AsyncMock()

    async def _get(model, pk):
        return run if model.__name__ == "AgentRun" else case

    db.get = AsyncMock(side_effect=_get)
    svc = RecoveryService(db)
    svc._audit = MagicMock(record=AsyncMock())
    return svc


def _run(status="RUNNING"):
    return SimpleNamespace(
        id=uuid.UUID(RUN_ID), recovery_case_id=CASE_ID, run_status=status, error=None
    )


def _case():
    return SimpleNamespace(
        id=CASE_ID,
        scenario="FAILED_PAYMENT",
        failure_reason="INSUFFICIENT_FUNDS",
        amount_at_risk_paise=299900,
        currency="INR",
        customer_id=uuid.uuid4(),
        retry_count=0,
        communication_count=0,
        is_recovered=False,
    )


@pytest.mark.parametrize("status", ["COMPLETED", "ERROR"])
def test_execute_skips_runs_that_are_not_running(status, monkeypatch):
    from app.services import recovery_service

    agent_cls = MagicMock()
    monkeypatch.setattr(recovery_service, "RecoveryAgent", agent_cls)
    run = _run(status)
    svc = _service(run, _case())

    assert asyncio.run(svc.execute_agent_run(RUN_ID)) == status
    agent_cls.assert_not_called()
    assert run.run_status == status


def _failing_policy(monkeypatch, message):
    from app.services import recovery_service

    policy_svc = MagicMock()
    policy_svc.return_value.get_active_policy_config = AsyncMock(side_effect=RuntimeError(message))
    monkeypatch.setattr(recovery_service, "PolicyService", policy_svc)


def test_final_attempt_failure_marks_error_with_truncated_message(monkeypatch):
    _failing_policy(monkeypatch, "x" * 5000)
    run = _run()
    svc = _service(run, _case())

    assert asyncio.run(svc.execute_agent_run(RUN_ID, final_attempt=True)) == "ERROR"
    assert run.run_status == "ERROR"
    assert len(run.error) == 2048


def test_non_final_attempt_failure_reraises_and_keeps_running(monkeypatch):
    _failing_policy(monkeypatch, "transient")
    run = _run()
    svc = _service(run, _case())

    with pytest.raises(RuntimeError, match="transient"):
        asyncio.run(svc.execute_agent_run(RUN_ID, final_attempt=False))
    assert run.run_status == "RUNNING"


def test_execute_uses_ainvoke_and_persists_result(monkeypatch):
    from app.services import recovery_service

    policy_svc = MagicMock()
    policy_svc.return_value.get_active_policy_config = AsyncMock(return_value=object())
    monkeypatch.setattr(recovery_service, "PolicyService", policy_svc)
    monkeypatch.setattr(recovery_service, "get_payment_provider", MagicMock())
    agent = MagicMock()
    agent.ainvoke = AsyncMock(return_value={"node_trace": ["completion"]})
    agent.run = MagicMock(side_effect=AssertionError("sync run must not be used"))
    monkeypatch.setattr(recovery_service, "RecoveryAgent", MagicMock(return_value=agent))

    run = _run()
    svc = _service(run, _case())
    svc._apply_agent_result = AsyncMock(
        side_effect=lambda c, r, s: setattr(r, "run_status", "COMPLETED")
    )

    assert asyncio.run(svc.execute_agent_run(RUN_ID)) == "COMPLETED"
    state = agent.ainvoke.await_args.args[0]
    assert state["agent_run_id"] == RUN_ID and state["case_id"] == str(CASE_ID)


# ── Dispatch ──────────────────────────────────────────────────────────────────


def _dispatch(monkeypatch, backend, delay_side_effect=None):
    from app.services import agent_dispatch

    monkeypatch.setattr(agent_dispatch.settings, "AGENT_EXECUTION_BACKEND", backend)
    monkeypatch.setattr(
        agent_dispatch.RecoveryService, "start_agent_run", AsyncMock(return_value=RUN_ID)
    )
    import app.tasks

    delay = MagicMock(side_effect=delay_side_effect)
    monkeypatch.setattr(app.tasks.run_recovery_agent_task, "delay", delay)
    db = MagicMock(commit=AsyncMock())
    bg = MagicMock()
    result = asyncio.run(agent_dispatch.dispatch_agent_run(db, str(CASE_ID), bg))
    return result, db, bg, delay, agent_dispatch


def test_inline_backend_uses_background_tasks(monkeypatch):
    result, db, bg, delay, mod = _dispatch(monkeypatch, "inline")
    assert result == RUN_ID
    db.commit.assert_awaited_once()
    bg.add_task.assert_called_once_with(mod.run_agent_inline, RUN_ID)
    delay.assert_not_called()


def test_celery_backend_enqueues_run_id(monkeypatch):
    result, db, bg, delay, _ = _dispatch(monkeypatch, "celery")
    assert result == RUN_ID
    db.commit.assert_awaited_once()
    delay.assert_called_once_with(RUN_ID)
    bg.add_task.assert_not_called()


def test_celery_enqueue_failure_falls_back_to_inline(monkeypatch):
    result, _, bg, delay, mod = _dispatch(
        monkeypatch, "celery", delay_side_effect=ConnectionError("no broker")
    )
    assert result == RUN_ID
    delay.assert_called_once()
    bg.add_task.assert_called_once_with(mod.run_agent_inline, RUN_ID)


def test_dispatch_returns_none_when_no_run_started(monkeypatch):
    from app.services import agent_dispatch

    monkeypatch.setattr(
        agent_dispatch.RecoveryService, "start_agent_run", AsyncMock(return_value=None)
    )
    db = MagicMock(commit=AsyncMock())
    bg = MagicMock()
    assert asyncio.run(agent_dispatch.dispatch_agent_run(db, str(CASE_ID), bg)) is None
    db.commit.assert_not_awaited()
    bg.add_task.assert_not_called()


# ── Celery task ───────────────────────────────────────────────────────────────


def test_celery_task_allows_three_attempts_total():
    from app.tasks import run_recovery_agent_task

    assert run_recovery_agent_task.max_retries == 2


def test_celery_task_executes_by_run_id_and_disposes_engine(monkeypatch):
    import app.tasks
    from app.services import agent_dispatch

    execute = AsyncMock(return_value="COMPLETED")
    monkeypatch.setattr(agent_dispatch, "execute_agent_run_in_new_session", execute)
    dispose = AsyncMock()
    monkeypatch.setattr(app.tasks, "engine", MagicMock(dispose=dispose))

    result = app.tasks.run_recovery_agent_task.apply(args=[RUN_ID]).get()

    assert result == {"status": "COMPLETED", "agent_run_id": RUN_ID}
    # First attempt (retries=0 < max_retries=2) is not final: failures propagate to retry.
    assert execute.await_args.kwargs == {"final_attempt": False}
    dispose.assert_awaited_once()
