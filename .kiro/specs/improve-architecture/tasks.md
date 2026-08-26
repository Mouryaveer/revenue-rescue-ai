# Implementation Plan: improve-architecture

## Overview

Four self-contained phases, each corresponding to one requirement. Each phase ends with a full
test run assertion. No phase breaks the existing 130/130 baseline.

**Sequence:** Phase 1 (node split) → Phase 2 (async agent) → Phase 3 (structured logging) →
Phase 4 (namespaced state). Each phase depends on the previous because Phase 2 uses the split
modules, Phase 3 wraps the nodes, and Phase 4 restructures the state that all phases touch.

## Tasks

### Phase 1 — Node Module Separation (Requirement 1)

- [ ] 1. Create `agents/nodes/node_utils.py` with shared helpers
  - Move `_add_trace`, `_strategy_to_action_type`, `_fallback_diagnosis`, `_fallback_strategy` from `nodes.py`
  - Export all four from `node_utils.py`
  - _Requirements: 1.3_

- [ ] 2. Create `agents/nodes/deterministic_nodes.py`
  - Move `node_risk_detection`, `node_context_builder`, `node_policy_check`, `node_action_execution`, `node_observation`, `node_verification`, `node_escalation`, `node_completion`, `increment_replan`
  - Import helpers from `node_utils`; do NOT import from `llm_nodes.py`
  - _Requirements: 1.2, 1.4_

- [ ] 3. Create `agents/nodes/llm_nodes.py`
  - Move `node_diagnosis` and `node_strategy`
  - Import helpers from `node_utils`; do NOT import from `deterministic_nodes.py`
  - _Requirements: 1.1, 1.4_

- [ ] 4. Update `agents/nodes/__init__.py` to re-export all nodes from new modules

- [ ] 5. Update `agents/graph/recovery_graph.py` imports to reference new modules
  - `node_diagnosis`, `node_strategy` from `agents.nodes.llm_nodes`
  - All other nodes from `agents.nodes.deterministic_nodes`
  - _Requirements: 1.6_

- [ ] 6. Delete `agents/nodes/nodes.py`
  - _Requirements: 1.5_

- [ ] 7. Run `python -m pytest agents/tests/ -q` — assert 0 new failures
  - _Requirements: 1.8_

### Phase 2 — Async Agent Execution (Requirement 2)

- [ ] 8. Add `async def ainvoke(self, initial_state: AgentState) -> AgentState` to `RecoveryAgent`
  - Validate `case_id` and `agent_run_id` present; raise `ValueError` if missing
  - Wrap `self._graph.invoke(initial_state)` in `asyncio.get_event_loop().run_in_executor(None, ...)`
  - _Requirements: 2.7, 2.8_

- [ ] 9. Create `agents/tasks/agent_tasks.py` (Celery task)
  - `@celery_app.task(bind=True, max_retries=3)` function `run_recovery_agent_task`
  - On start: if `AgentRun.run_status != "RUNNING"`, return existing run ID without executing
  - Call `RecoveryAgent.ainvoke(initial_state)`
  - On success: persist via `_apply_agent_result` equivalent
  - On exception: set `run_status="ERROR"`, persist `error` truncated to 2048 chars, retry ≤ 3×
  - _Requirements: 2.2, 2.3, 2.4, 2.5_

- [ ] 10. Update `RecoveryService.run_recovery_agent` to enqueue the Celery task
  - Create `AgentRun` with `run_status="RUNNING"` before enqueue
  - Call `run_recovery_agent_task.delay(...)` and return immediately
  - Remove inline synchronous `agent.run(initial_state)` call
  - _Requirements: 2.1, 2.6_

- [ ] 11. Run `python -m pytest agents/tests/ backend/tests/ tests/integration/ -q` — assert 0 new failures

### Phase 3 — Per-Node Structured Execution Logging (Requirement 3)

- [ ] 12. Define `NodeExecutionRecord` TypedDict in `agents/schemas/agent_schemas.py`
  - Fields: `node_name`, `run_id`, `started_at`, `finished_at`, `duration_ms`, `output_snapshot`, `error`

- [ ] 13. Add `node_observation_log: list` to `AgentState` and initialise to `[]` in `make_initial_state`
  - _Requirements: 3.7_

- [ ] 14. Create `_wrap_node` helper in `node_utils.py`
  - Pre-call: record `node_name`, `started_at`, `run_id`
  - Post-call: `finished_at`, `duration_ms`, sanitise `output_snapshot` (truncate keys > 4096 bytes; `"[unserializable]"` on JSON failure)
  - On exception: set `error` (truncated to 1024 chars), re-raise
  - Emit structlog `INFO` event `"node_execution_record"`
  - Append record to `state["node_observation_log"]` and node name to `state["node_trace"]`
  - _Requirements: 3.1–3.6, 3.9_

- [ ] 15. Apply `_wrap_node` to all node calls in `build_recovery_graph`
  - _Requirements: 3.7_

- [ ] 16. Update `RecoveryService._apply_agent_result` to persist `node_observation_log` to `AgentRun.node_trace`
  - _Requirements: 3.8_

- [ ] 17. Run `python -m pytest agents/tests/ backend/tests/ -q` — assert 0 new failures; verify `result.get("node_trace")` still returns `list[str]`

### Phase 4 — Namespaced Agent State (Requirement 4)

- [ ] 18. Define four namespace TypedDicts in `agents/schemas/agent_schemas.py`
  - `AgentInputState`, `AgentControlState`, `AgentOutputsState`, `AgentTraceState`
  - _Requirements: 4.1–4.5_

- [ ] 19. Restructure `AgentState` to use the four namespace keys: `input`, `control`, `outputs`, `trace`
  - _Requirements: 4.1_

- [ ] 20. Update `make_initial_state` to build namespaced state; keep public parameter signature unchanged
  - _Requirements: 4.7_

- [ ] 21. Add `input`-namespace write protection in `_wrap_node`
  - After any node call, if `state["input"]` differs from pre-call snapshot, raise `ValueError` with node name and mutated key, then restore original
  - _Requirements: 4.8_

- [ ] 22. Update all node functions in `llm_nodes.py` and `deterministic_nodes.py` to use namespaced access
  - `state["input"]["case_id"]`, `state["control"]["retry_count"]`, `state["outputs"]["diagnosis"]`, `state["trace"]["node_trace"]`
  - _Requirements: 4.6_

- [ ] 23. Update `RecoveryService._apply_agent_result` and `run_recovery_agent` call sites for namespaced state
  - _Requirements: 4.7_

- [ ] 24. Update routing functions in `recovery_graph.py` for namespaced access

- [ ] 25. Run full suite `python -m pytest policies/tests/ simulator/tests/ agents/tests/ tests/redteam/ tests/integration/ backend/tests/unit/ backend/tests/integration/ -q` — document any new failures per Requirement 4.9

- [ ] 26. Commit: `refactor: improve-architecture — node split, async agent, structured logging, namespaced state`

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": [1] },
    { "wave": 2, "tasks": [2, 3, 4] },
    { "wave": 3, "tasks": [5] },
    { "wave": 4, "tasks": [6] },
    { "wave": 5, "tasks": [7] },
    { "wave": 6, "tasks": [8] },
    { "wave": 7, "tasks": [9, 10] },
    { "wave": 8, "tasks": [11] },
    { "wave": 9, "tasks": [12, 13] },
    { "wave": 10, "tasks": [14] },
    { "wave": 11, "tasks": [15, 16] },
    { "wave": 12, "tasks": [17] },
    { "wave": 13, "tasks": [18, 19, 20] },
    { "wave": 14, "tasks": [21, 22, 23, 24] },
    { "wave": 15, "tasks": [25] },
    { "wave": 16, "tasks": [26] }
  ]
}
```

## Notes

- Phases 1–4 must be implemented in order — later phases depend on the split modules and state schema.
- The 130/130 test baseline must be verified before committing each phase. Do not proceed to the next phase if new failures are introduced.
- Phase 4 (namespaced state) is the highest-risk change. If it introduces regressions that cannot be fixed inline, document them per Requirement 4.9 and continue — do not revert Phase 4.
- `RecoveryService` callers (`events.py`, `recovery_cases.py`) should require no changes because `make_initial_state`'s public signature is preserved.
- The Celery worker (`rr_worker` in docker-compose) does not need a new container — the new `agent_tasks.py` is registered on the existing `celery_app`.
