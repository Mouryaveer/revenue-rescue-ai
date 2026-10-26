"""
LangGraph recovery agent state machine.
Uses TypedDict state for full LangGraph 0.2+ compatibility.

Node order:
  risk_detection → context_builder → diagnosis → strategy →
  policy_check → action_execution → observation → verification →
  [RECOVERED → completion] | [REPLAN → strategy] |
  [ESCALATED → escalation → completion] | [DENIED → completion]

Only diagnosis and strategy use the LLM.
All routing decisions are deterministic.
"""

from __future__ import annotations

import os
from functools import partial

import structlog
from app.providers.base import PaymentProvider

from agents.nodes.deterministic_nodes import (
    increment_replan,
    node_action_execution,
    node_completion,
    node_context_builder,
    node_escalation,
    node_observation,
    node_policy_check,
    node_risk_detection,
    node_verification,
)
from agents.nodes.llm_nodes import node_diagnosis, node_strategy
from agents.nodes.llm_provider import LLMProvider, get_llm_provider
from agents.nodes.node_utils import _wrap_node
from agents.schemas.agent_schemas import AgentState
from policies.engine.policy_engine import PolicyEngine
from policies.schemas.policy_schema import PolicyConfig
from simulator.engine.recovery_verifier import RecoveryVerifier

# Disable langsmith tracing to avoid Pydantic v1 import issues
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")

logger = structlog.get_logger(__name__)


# ── Routing functions (deterministic, use dict access) ────────────────────────


def route_after_risk_detection(state: AgentState) -> str:
    if state.get("case_is_stopped") or state.get("error"):
        return "completion"
    return "context_builder"


def route_after_policy_check(state: AgentState) -> str:
    decision = (state.get("policy_result") or {}).get("decision")
    if decision == "APPROVED":
        return "action_execution"
    if decision in ("ESCALATE", "STOP"):
        return "escalation"
    # DENIED → completion (node_completion sets case_is_stopped)
    return "completion"


def route_after_verification(state: AgentState) -> str:
    if state.get("case_is_recovered"):
        return "completion"

    outcome = (state.get("verification_result") or {}).get("outcome", "FAILED")
    replan_count = state.get("replan_count", 0)
    max_replans = state.get("max_replans", 3)

    if outcome == "COMMUNICATION_SENT":
        if replan_count < max_replans:
            return "replan"
        return "escalation"

    # Payment failed
    if replan_count < max_replans:
        return "replan"

    return "escalation"


# ── Graph builder ──────────────────────────────────────────────────────────────


def build_recovery_graph(
    llm: LLMProvider,
    policy_engine: PolicyEngine,
    provider: PaymentProvider,
    verifier: RecoveryVerifier,
):
    from langgraph.graph import END, StateGraph

    graph = StateGraph(AgentState)

    diag_node = partial(node_diagnosis, llm=llm)
    strat_node = partial(node_strategy, llm=llm)
    policy_node = partial(node_policy_check, policy_engine=policy_engine)
    exec_node = partial(node_action_execution, provider=provider)
    verify_node = partial(node_verification, provider=provider, verifier=verifier)

    nodes = {
        "risk_detection": node_risk_detection,
        "context_builder": node_context_builder,
        "diagnosis": diag_node,
        "strategy": strat_node,
        "policy_check": policy_node,
        "action_execution": exec_node,
        "observation": node_observation,
        "verification": verify_node,
        "escalation": node_escalation,
        "completion": node_completion,
        # Replan node: increments counter then routes back to strategy
        "replan": increment_replan,
    }
    for name, fn in nodes.items():
        graph.add_node(name, _wrap_node(name, fn))

    graph.set_entry_point("risk_detection")

    graph.add_conditional_edges("risk_detection", route_after_risk_detection)
    graph.add_edge("context_builder", "diagnosis")
    graph.add_edge("diagnosis", "strategy")
    graph.add_edge("strategy", "policy_check")
    graph.add_conditional_edges("policy_check", route_after_policy_check)
    graph.add_edge("action_execution", "observation")
    graph.add_edge("observation", "verification")
    graph.add_conditional_edges("verification", route_after_verification)
    graph.add_edge("replan", "strategy")  # replan → strategy (counter already incremented)
    graph.add_edge("escalation", "completion")
    graph.add_edge("completion", END)

    return graph.compile()


# ── High-level runner ─────────────────────────────────────────────────────────


class RecoveryAgent:
    def __init__(
        self,
        policy: PolicyConfig,
        llm_provider: str = "mock",
        api_key: str = "",
        model: str = "gpt-4o",
        *,
        payment_provider: PaymentProvider,
        cloudflare_account_id: str = "",
        cloudflare_api_token: str = "",
        **kwargs,
    ) -> None:
        self._llm = get_llm_provider(
            provider=llm_provider,
            api_key=api_key,
            model=model,
            cloudflare_account_id=cloudflare_account_id,
            cloudflare_api_token=cloudflare_api_token,
        )
        self._policy_engine = PolicyEngine(policy)
        self._provider = payment_provider
        self._verifier = RecoveryVerifier()

        self._graph = build_recovery_graph(
            self._llm, self._policy_engine, self._provider, self._verifier
        )

    def run(self, initial_state: AgentState) -> AgentState:
        logger.info(
            "agent_run_start",
            case_id=initial_state.get("case_id"),
            agent_run_id=initial_state.get("agent_run_id"),
        )
        result = self._graph.invoke(initial_state)
        return result  # already a dict (TypedDict), no need to convert
