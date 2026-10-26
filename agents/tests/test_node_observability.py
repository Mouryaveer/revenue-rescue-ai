"""
Per-node structured observability tests (improve-architecture Requirement 3).
"""

import json
from datetime import datetime

import pytest
from app.providers.simulator_provider import SimulatorPaymentProvider
from structlog.testing import capture_logs

from agents.graph.recovery_graph import RecoveryAgent
from agents.nodes.node_utils import _add_trace, _fallback_diagnosis, _wrap_node
from agents.schemas.agent_schemas import make_initial_state
from policies.schemas.policy_schema import PolicyConfig


def _state(**overrides):
    base = {
        "case_id": "case-obs",
        "agent_run_id": "run-obs",
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "amount_paise": 299900,
        "customer_id": "cust-obs",
    }
    base.update(overrides)
    return make_initial_state(**base)


def test_initial_state_has_empty_observation_log():
    assert _state()["node_observation_log"] == []


def test_wrapped_node_appends_record_with_timing_and_snapshot():
    def node(state):
        return {**_add_trace(state, "demo"), "retry_count": 2}

    update = _wrap_node("demo", node)(_state())

    (record,) = update["node_observation_log"]
    assert record["node_name"] == "demo"
    assert record["run_id"] == "run-obs"
    assert datetime.fromisoformat(record["finished_at"]) >= datetime.fromisoformat(
        record["started_at"]
    )
    assert isinstance(record["duration_ms"], int) and record["duration_ms"] >= 0
    assert record["output_snapshot"] == {"current_node": "demo", "retry_count": 2}
    assert "error" not in record
    assert update["node_trace"] == ["demo"]
    json.dumps(record)  # must be persistable as JSONB


def test_wrapper_adds_node_trace_for_nodes_that_do_not_trace_themselves():
    update = _wrap_node("replan", lambda s: {"replan_count": 1})(_state())
    assert update["node_trace"] == ["replan"]
    assert [r["node_name"] for r in update["node_observation_log"]] == ["replan"]


def test_pydantic_outputs_are_snapshotted_as_json():
    diag = _fallback_diagnosis("INSUFFICIENT_FUNDS")
    update = _wrap_node("diagnosis", lambda s: {"case_diagnosis": diag})(_state())
    snapshot = update["node_observation_log"][0]["output_snapshot"]
    assert snapshot["case_diagnosis"]["failure_category"] == "INSUFFICIENT_FUNDS"


def test_large_top_level_value_is_truncated():
    update = _wrap_node("big", lambda s: {"blob": "x" * 5000, "small": 1})(_state())
    snapshot = update["node_observation_log"][0]["output_snapshot"]
    assert snapshot == {"blob": "[truncated]", "small": 1}


def test_unserializable_output_does_not_raise():
    update = _wrap_node("odd", lambda s: {"thing": object()})(_state())
    assert update["node_observation_log"][0]["output_snapshot"] == "[unserializable]"
    assert "thing" in update  # the real state update is untouched


def test_node_exception_is_logged_with_truncated_error_and_reraised():
    def boom(state):
        raise RuntimeError("e" * 2000)

    with capture_logs() as logs, pytest.raises(RuntimeError):
        _wrap_node("boom", boom)(_state())

    (entry,) = (e for e in logs if e["event"] == "node_execution_record")
    assert entry["node_name"] == "boom"
    assert len(entry["error"]) == 1024
    assert entry["log_level"] == "info"


def test_full_run_observation_log_matches_node_trace():
    agent = RecoveryAgent(
        policy=PolicyConfig(policy_id="test", version=1),
        llm_provider="mock",
        payment_provider=SimulatorPaymentProvider(seed=42),
    )
    with capture_logs() as logs:
        result = agent.run(_state())

    log = result["node_observation_log"]
    trace = result["node_trace"]
    assert [r["node_name"] for r in log] == trace
    assert trace[0] == "risk_detection" and trace[-1] == "completion"
    assert [r["started_at"] for r in log] == sorted(r["started_at"] for r in log)
    emitted = [e for e in logs if e["event"] == "node_execution_record"]
    assert len(emitted) == len(log)
    json.dumps(log)
