"""
Helpers shared by LLM nodes and deterministic nodes.

Must not import from llm_nodes, deterministic_nodes, or llm_provider, so that
deterministic nodes stay importable without any LLM dependency.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from pydantic import BaseModel

from agents.schemas.agent_schemas import (
    AgentState,
    DiagnosisOutput,
    NodeExecutionRecord,
    StrategyOutput,
)

logger = structlog.get_logger(__name__)

SNAPSHOT_MAX_VALUE_BYTES = 4096
NODE_ERROR_MAX_CHARS = 1024
# Bookkeeping keys that are already recorded elsewhere; left out of output_snapshot.
_SNAPSHOT_EXCLUDED_KEYS = frozenset({"node_trace", "node_observation_log"})


def _add_trace(state: AgentState, node: str) -> dict:
    """Return a partial state update that appends to node_trace."""
    current = list(state.get("node_trace", []))
    current.append(node)
    return {"node_trace": current, "current_node": node}


# ── Per-node observability ────────────────────────────────────────────────────


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sanitize_output(output: Any) -> dict | str:
    """
    JSON-safe snapshot of a node's return dict.

    Only top-level keys are inspected. A key whose encoded value exceeds
    SNAPSHOT_MAX_VALUE_BYTES becomes "[truncated]". If any top-level value cannot
    be encoded, the whole snapshot is "[unserializable]".
    """
    if not isinstance(output, dict):
        return "[unserializable]"
    snapshot: dict = {}
    try:
        for key, value in output.items():
            if key in _SNAPSHOT_EXCLUDED_KEYS:
                continue
            encoded = json.dumps(value, default=_json_default)
            if len(encoded.encode("utf-8")) > SNAPSHOT_MAX_VALUE_BYTES:
                snapshot[str(key)] = "[truncated]"
            else:
                snapshot[str(key)] = json.loads(encoded)
    except (TypeError, ValueError, OverflowError):
        return "[unserializable]"
    return snapshot


def _wrap_node(node_name: str, fn: Callable[[AgentState], dict]) -> Callable[[AgentState], dict]:
    """
    Wrap a graph node so each execution produces a NodeExecutionRecord.

    The record is logged as "node_execution_record" and appended to
    node_observation_log. node_trace is kept in the same order: if the node did
    not append itself (e.g. replan), the wrapper does.
    """

    def wrapped(state: AgentState) -> dict:
        record: NodeExecutionRecord = {
            "node_name": node_name,
            "run_id": state.get("agent_run_id"),
            "started_at": _utc_now_iso(),
        }
        t0 = time.perf_counter()
        try:
            output = fn(state)
        except Exception as exc:
            record["finished_at"] = _utc_now_iso()
            record["duration_ms"] = int((time.perf_counter() - t0) * 1000)
            record["error"] = str(exc)[:NODE_ERROR_MAX_CHARS]
            logger.info("node_execution_record", **record)
            raise

        record["finished_at"] = _utc_now_iso()
        record["duration_ms"] = int((time.perf_counter() - t0) * 1000)
        record["output_snapshot"] = _sanitize_output(output)
        logger.info("node_execution_record", **record)

        update = dict(output or {})
        update["node_observation_log"] = [*state.get("node_observation_log", []), record]
        if "node_trace" not in update:
            update["node_trace"] = [*state.get("node_trace", []), node_name]
        return update

    wrapped.__name__ = f"observed_{node_name}"
    return wrapped


def _fallback_diagnosis(
    failure_reason: str, ml_probability: float | None = None
) -> DiagnosisOutput:
    strategy_map = {
        "INSUFFICIENT_FUNDS": ("SCHEDULE_RETRY", 0.75),
        "EXPIRED_METHOD": ("PAYMENT_METHOD_UPDATE", 0.60),
        "GATEWAY_TEMPORARY": ("RETRY_NOW", 0.85),
        "BANK_DECLINE": ("SCHEDULE_RETRY", 0.55),
        "AUTH_FAILURE": ("REMINDER", 0.50),
        "MANDATE_FAILURE": ("SCHEDULE_RETRY", 0.65),
        "SUBSCRIPTION_GRACE": ("SCHEDULE_RETRY", 0.65),
        "CHECKOUT_ABANDONED": ("CHECKOUT_RECOVERY", 0.55),
        "UNKNOWN": ("ESCALATE", 0.20),
    }
    strategy, default_conf = strategy_map.get(failure_reason, ("ESCALATE", 0.20))
    confidence = (
        ml_probability if (ml_probability is not None and strategy != "ESCALATE") else default_conf
    )
    confidence = round(max(0.0, min(1.0, float(confidence))), 4)

    return DiagnosisOutput(
        diagnosis=f"fallback_{failure_reason.lower()}",
        diagnosis_confidence=confidence,
        failure_category=failure_reason,
        likely_cause=f"Deterministic fallback for {failure_reason}",
        is_recoverable=strategy != "ESCALATE",
        recommended_strategy=strategy,
        needs_human_review=failure_reason == "UNKNOWN",
        notes="FALLBACK_MODE",
    )


def _fallback_strategy(
    diag: DiagnosisOutput, amount_paise: int, delay_hours: int = 24
) -> StrategyOutput:
    strategy = diag.recommended_strategy
    delay = delay_hours if "RETRY" in strategy else 0
    return StrategyOutput(
        recovery_strategy=strategy,
        reason=f"Deterministic fallback strategy for {diag.failure_category}",
        requested_action={"type": strategy, "delay_hours": delay},
        expected_recovery_paise=amount_paise if strategy != "ESCALATE" else 0,
        confidence=diag.diagnosis_confidence,
        fallback_strategy="ESCALATE",
    )


def _strategy_to_action_type(strategy: str) -> str:
    return {
        "RETRY_NOW": "retry_payment",
        "SCHEDULE_RETRY": "schedule_retry",
        "PAYMENT_METHOD_UPDATE": "request_payment_method_update",
        "REMINDER": "send_payment_reminder",
        "CHECKOUT_RECOVERY": "send_checkout_recovery",
        "PROMISE_TO_PAY": "create_promise_to_pay",
        "ESCALATE": "escalate_to_human",
    }.get(strategy, "escalate_to_human")
