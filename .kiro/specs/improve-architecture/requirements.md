# Requirements Document

## Introduction

This feature improves the architecture of the RevenueRescue AI agent system, focusing on four
specific areas identified as the highest-friction points in the current codebase:

1. **Node module separation** — all 10 nodes live in a single `agents/nodes/nodes.py` file.
   LLM-dependent nodes (`node_diagnosis`, `node_strategy`) and deterministic nodes are mixed
   together, making the codebase harder to extend and navigate.

2. **Async agent execution** — `RecoveryAgent.run()` is synchronous; `RecoveryService` calls it
   via FastAPI's `BackgroundTasks`, which ties agent execution to the HTTP worker process and
   prevents true async Celery-backed isolation.

3. **Per-node structured observability** — agent runs produce a flat `node_trace` list of strings
   and basic error strings, but no per-node timing, input snapshots, or output snapshots.

4. **State schema growth** — `AgentState` is a single flat TypedDict with 30+ fields; all nodes
   read and write to the same dict, making it difficult to understand data ownership or add
   fields safely.

The system currently has 130/130 tests passing. All improvements must not regress any existing
test and must preserve all current behaviour (fail-closed policy engine, LangGraph graph topology,
idempotency guarantees).

---

## Glossary

- **Recovery_Agent**: The LangGraph-based orchestration class (`RecoveryAgent`) that runs a
  payment recovery workflow for a single `RecoveryCase`.
- **LLM_Node**: A graph node whose output is produced by an LLM call — `node_diagnosis` and
  `node_strategy`.
- **Deterministic_Node**: A graph node whose output is fully determined by its inputs with no LLM
  involvement — `node_risk_detection`, `node_context_builder`, `node_policy_check`,
  `node_action_execution`, `node_observation`, `node_verification`, `node_escalation`,
  `node_completion`, `increment_replan`.
- **AgentState**: The LangGraph `TypedDict` state object passed between nodes.
- **Node_Trace**: The ordered list of node name strings visited during a single agent run
  (backward-compatible field).
- **Node_Execution_Record**: A structured record capturing the name, start time, end time,
  duration, output snapshot, and optional error of a single node execution within an agent run.
- **Node_Observation_Log**: The ordered list of `Node_Execution_Records` produced during a single
  agent run, ordered by `started_at` ascending.
- **Recovery_Graph**: The compiled LangGraph `StateGraph` defined in
  `agents/graph/recovery_graph.py`.
- **RecoveryService**: The FastAPI service class in `backend/app/services/recovery_service.py`
  that orchestrates case creation and agent execution.
- **Celery_Worker**: The background Celery worker process (`rr_worker`) that runs long-lived
  tasks outside the HTTP request lifecycle.
- **State_Namespace**: A logically grouped sub-dict of `AgentState` fields that belong together
  and are primarily read/written by a specific phase of the graph.
- **Policy_Engine**: The deterministic, fail-closed authorization gate in
  `policies/engine/policy_engine.py`.
- **Async_Agent_Task**: A Celery task that invokes `RecoveryAgent.ainvoke()` and writes results
  back to the database.
- **node_utils.py**: A shared utility module at `agents/nodes/node_utils.py` that contains
  helpers used by both LLM and deterministic nodes (`_add_trace`, `_strategy_to_action_type`).

---

## Requirements

### Requirement 1: Separate LLM Nodes and Deterministic Nodes into Distinct Modules

**User Story:** As a developer extending the recovery agent, I want LLM-dependent and
deterministic nodes to live in separate modules, so that I can locate, modify, and test each
node type without touching unrelated code.

#### Acceptance Criteria

1. THE Recovery_Agent SHALL load LLM_Nodes from a dedicated module (`agents/nodes/llm_nodes.py`)
   that contains only the `node_diagnosis` and `node_strategy` functions, where they are distinct
   named functions with distinct implementation bodies.

2. THE Recovery_Agent SHALL load Deterministic_Nodes from a dedicated module
   (`agents/nodes/deterministic_nodes.py`) that contains all non-LLM node functions:
   `node_risk_detection`, `node_context_builder`, `node_policy_check`, `node_action_execution`,
   `node_observation`, `node_verification`, `node_escalation`, `node_completion`, and
   `increment_replan`.

3. A shared utility module (`agents/nodes/node_utils.py`) SHALL contain helper functions used
   by nodes in both modules (`_add_trace`, `_strategy_to_action_type`, `_fallback_diagnosis`,
   `_fallback_strategy`). Both `llm_nodes.py` and `deterministic_nodes.py` SHALL import from
   `node_utils.py`; neither SHALL import from the other.

4. THE `agents/nodes/llm_nodes.py` module SHALL NOT import from
   `agents/nodes/deterministic_nodes.py`, and `agents/nodes/deterministic_nodes.py` SHALL NOT
   import from `agents/nodes/llm_nodes.py`.

5. THE `agents/nodes/nodes.py` file SHALL be removed after all node functions and helpers are
   migrated to the new modules, leaving no remaining function definitions in that file.

6. THE `agents/graph/recovery_graph.py` SHALL be updated to import each node from its new
   module (`llm_nodes` or `deterministic_nodes`).

7. WHEN an LLM_Node raises an unhandled exception, `agents/nodes/deterministic_nodes.py` SHALL
   remain importable without triggering any LLM-related imports.

8. WHEN all tests in `agents/tests/` are executed after the refactoring, THE Test_Suite SHALL
   report 0 test failures that did not exist in the pre-refactor baseline run.

---

### Requirement 2: Async Agent Execution via Celery Worker

**User Story:** As a backend engineer, I want agent execution to run asynchronously inside a
Celery worker, so that the HTTP API returns immediately and agent failures are isolated from the
request lifecycle.

#### Acceptance Criteria

1. WHEN the `RecoveryService` triggers agent execution, THE RecoveryService SHALL create an
   `AgentRun` record with `run_status = "RUNNING"`, enqueue an `Async_Agent_Task` carrying the
   `agent_run_id`, and return the `agent_run_id` to the caller immediately, without blocking the
   HTTP response on agent completion.

2. THE `Async_Agent_Task` SHALL call `RecoveryAgent.ainvoke()` rather than `RecoveryAgent.run()`.

3. WHEN the `Async_Agent_Task` completes successfully, THE Celery_Worker SHALL persist the final
   `AgentState` to the database by calling the equivalent of `_apply_agent_result`, producing
   the same DB and audit trail writes as the current synchronous path.

4. WHEN the `Async_Agent_Task` raises an unhandled exception, THE Celery_Worker SHALL set
   `AgentRun.run_status = "ERROR"`, persist `AgentRun.error = str(exception)` (truncated to
   2048 characters), and stop retrying after a maximum of 3 attempts total (matching the
   existing `max_retries = 3` pattern in `backend/app/tasks.py`).

5. THE `Async_Agent_Task` SHALL be idempotent: IF a task is enqueued with an `agent_run_id`
   that already has `run_status != "RUNNING"` in the database, THEN THE Celery_Worker SHALL
   return the existing `agent_run_id` without re-executing the agent or raising an error.

6. WHILE an `Async_Agent_Task` is executing, THE Recovery_API SHALL return
   `run_status = "RUNNING"` when the `AgentRun` record is polled via any existing endpoint.

7. THE `RecoveryAgent` class SHALL expose an
   `async def ainvoke(self, initial_state: AgentState) -> AgentState` method that is the async
   entry point for all production execution paths; IF called with an `initial_state` that is
   missing `case_id` or `agent_run_id`, THEN `ainvoke` SHALL raise a `ValueError` before
   invoking the graph.

8. IF the compiled LangGraph graph does not expose an async invocation method, THEN `ainvoke`
   SHALL wrap `self._graph.invoke(initial_state)` in `asyncio.get_event_loop().run_in_executor`
   to prevent blocking the Celery async event loop.

---

### Requirement 3: Per-Node Structured Execution Logging

**User Story:** As a developer debugging a failed recovery run, I want to see per-node timing
and outputs in a structured log, so that I can quickly identify which node produced unexpected
behaviour.

#### Acceptance Criteria

1. WHEN a node begins execution, THE Recovery_Agent SHALL create a `Node_Execution_Record`
   dict containing: `node_name` (str), `started_at` (ISO 8601 UTC string), `run_id` (the
   `agent_run_id` from state).

2. WHEN a node completes execution, THE Recovery_Agent SHALL update the `Node_Execution_Record`
   with: `finished_at` (ISO 8601 UTC string), `duration_ms` (int, milliseconds), and
   `output_snapshot` (the dict returned by the node function, sanitised to be JSON-serialisable).

3. THE `output_snapshot` field SHALL include only top-level keys from the node's return dict;
   any top-level key whose JSON-encoded value exceeds 4096 bytes SHALL be replaced with the
   string `"[truncated]"`. Nested keys SHALL NOT be individually inspected.

4. IF a node's return dict cannot be serialised to JSON (e.g., contains non-serialisable types
   at the top level), THEN `output_snapshot` SHALL be set to the string `"[unserializable]"`
   instead of raising an exception.

5. IF a node raises an exception during execution, THEN THE Recovery_Agent SHALL set an `error`
   field on the `Node_Execution_Record` containing the exception message, truncated to 1024
   characters, before the exception propagates.

6. WHEN a node completes or raises, THE Recovery_Agent SHALL emit the `Node_Execution_Record`
   as a structured log line at `INFO` level via the existing `structlog` logger with event key
   `"node_execution_record"`.

7. WHEN an agent run completes (regardless of outcome), THE `AgentState` SHALL contain a
   `node_observation_log` field (type `list`) holding the `Node_Execution_Records` in execution
   order (ordered by `started_at` ascending), initialised to `[]` at run start.

8. THE `node_observation_log` SHALL be persisted to the `AgentRun.node_trace` database column
   as a JSON array, replacing the current flat `list[str]` value.

9. THE Recovery_Agent SHALL also populate the existing `node_trace` field (type `list[str]`)
   with `node_name` strings in the same execution order as `node_observation_log`, so that all
   existing test assertions on `result.get("node_trace")` pass without modification.

---

### Requirement 4: Namespaced Agent State Sub-schemas

**User Story:** As a developer adding new fields to the agent state, I want the `AgentState` to
be organised into logical namespaces so that I can add fields to one namespace without risking
unintended side-effects in unrelated nodes.

#### Acceptance Criteria

1. THE `AgentState` TypedDict SHALL be restructured to contain exactly four top-level namespace
   keys: `input`, `control`, `outputs`, and `trace`, each being a nested TypedDict.

2. THE `input` namespace TypedDict SHALL contain all fields set at agent initialisation and
   never written by any node during execution: `case_id`, `agent_run_id`, `event_type`,
   `failure_reason`, `amount_paise`, `currency`, `customer_id`, `customer_segment`,
   `customer_opted_out`, `customer_suspended`, `subscription_id`, `checkout_session_id`,
   `max_replans`.

3. THE `control` namespace TypedDict SHALL contain all flow-control fields updated during
   execution: `retry_count`, `communication_count`, `case_is_recovered`, `case_is_stopped`,
   `payment_already_succeeded`, `hours_since_last_attempt`, `checkout_timeout_elapsed`,
   `checkout_recovery_message_count`, `replan_count`, `current_node`, `error`,
   `escalation_reason`, `llm_provider`.

4. THE `outputs` namespace TypedDict SHALL contain one key per node that produces structured
   output, each initialised to `None` at agent start and set by its node upon completion:
   `diagnosis`, `strategy`, `policy_result`, `execution_result`, `verification_result`.

5. THE `trace` namespace TypedDict SHALL contain: `node_trace` (type `list[str]`, preserving
   backward compatibility with existing log consumers) and `node_observation_log`
   (type `list`, the `Node_Execution_Records` from Requirement 3).

6. ALL node functions SHALL access state fields by explicitly specifying the namespace key
   (e.g., `state["input"]["case_id"]`). Accessing a state field without a namespace key
   (e.g., `state["case_id"]`) SHALL NOT be permitted in any node function body after the
   refactor.

7. THE `make_initial_state` factory function SHALL be updated to construct the namespaced
   `AgentState`; its public parameter signature (all keyword arguments currently accepted)
   SHALL remain unchanged so that `RecoveryService` and test callers require no modification.

8. IF a node function attempts to write to the `input` namespace
   (`state["input"][key] = value`), THE Recovery_Agent SHALL raise a `ValueError` identifying
   the node name and the forbidden key, and the `input` sub-dict SHALL remain unchanged after
   the error is raised.

9. WHEN all tests in `agents/tests/` and `backend/` are executed after the state refactor,
   THE Test_Suite SHALL report 0 test failures that did not exist in the pre-refactor baseline
   run; IF new failures are introduced, each SHALL be documented in a tracking comment in the
   affected test file referencing this requirement, to be resolved in follow-up work.
