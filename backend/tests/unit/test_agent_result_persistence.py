"""
RecoveryService._apply_agent_result persistence tests (no DB; session and audit mocked).
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def _service():
    from app.services.recovery_service import RecoveryService

    db = MagicMock()
    db.flush = AsyncMock()
    svc = RecoveryService(db)
    svc._audit = MagicMock(record=AsyncMock())
    return svc


def _case():
    return SimpleNamespace(
        id="case-1",
        retry_count=0,
        communication_count=0,
        is_recovered=False,
        is_stopped=False,
        diagnosis=None,
        strategy=None,
        policy_decision=None,
        status=None,
        escalation_reason=None,
        amount_recovered_paise=0,
    )


def test_apply_agent_result_persists_observation_log_to_node_trace_column():
    svc = _service()
    run = SimpleNamespace(run_status="RUNNING", node_trace=None, llm_output=None)
    records = [
        {"node_name": "risk_detection", "duration_ms": 1},
        {"node_name": "completion", "duration_ms": 0},
    ]
    state = {
        "node_trace": ["risk_detection", "completion"],
        "node_observation_log": records,
        "case_is_stopped": True,
    }

    asyncio.run(svc._apply_agent_result(_case(), run, state))

    assert run.run_status == "COMPLETED"
    assert run.node_trace == records
    # The audit trail keeps the flat list of node names.
    payloads = [c.kwargs.get("payload") for c in svc._audit.record.await_args_list]
    assert {"node_trace": ["risk_detection", "completion"]} in payloads


def test_apply_agent_result_falls_back_to_flat_trace_without_observation_log():
    svc = _service()
    run = SimpleNamespace(run_status="RUNNING", node_trace=None, llm_output=None)
    state = {"node_trace": ["risk_detection", "completion"], "case_is_stopped": True}

    asyncio.run(svc._apply_agent_result(_case(), run, state))

    assert run.node_trace == ["risk_detection", "completion"]
