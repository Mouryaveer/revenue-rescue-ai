"""
RecoveryAgent.ainvoke tests (improve-architecture Requirement 2.7 / 2.8).
"""

import asyncio
import threading

import pytest
from app.providers.simulator_provider import SimulatorPaymentProvider

from agents.graph.recovery_graph import RecoveryAgent
from agents.schemas.agent_schemas import make_initial_state
from policies.schemas.policy_schema import PolicyConfig


def _agent(seed: int = 42) -> RecoveryAgent:
    return RecoveryAgent(
        policy=PolicyConfig(policy_id="test", version=1),
        llm_provider="mock",
        payment_provider=SimulatorPaymentProvider(seed=seed),
    )


def _state(**overrides):
    base = {
        "case_id": "case-async",
        "agent_run_id": "run-async",
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "amount_paise": 299900,
        "customer_id": "cust-async",
    }
    base.update(overrides)
    return make_initial_state(**base)


def test_ainvoke_matches_sync_run():
    sync_result = _agent().run(_state())
    async_result = asyncio.run(_agent().ainvoke(_state()))
    assert async_result["node_trace"] == sync_result["node_trace"]
    assert async_result.get("case_is_recovered") == sync_result.get("case_is_recovered")
    assert async_result["node_trace"][-1] == "completion"


@pytest.mark.parametrize("missing", ["case_id", "agent_run_id"])
def test_ainvoke_rejects_missing_ids(missing):
    agent = _agent()
    called = []
    agent._graph = type("G", (), {"invoke": lambda self, s: called.append(s)})()
    with pytest.raises(ValueError, match=missing):
        asyncio.run(agent.ainvoke(_state(**{missing: ""})))
    assert called == []


def test_ainvoke_runs_graph_off_the_event_loop_thread():
    agent = _agent()
    seen: dict = {}

    class FakeGraph:
        def invoke(self, state):
            seen["thread"] = threading.get_ident()
            return state

    agent._graph = FakeGraph()

    async def main():
        seen["loop_thread"] = threading.get_ident()
        return await agent.ainvoke(_state())

    asyncio.run(main())
    assert seen["thread"] != seen["loop_thread"]
