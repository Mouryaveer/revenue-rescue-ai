# What Broke and How We Got Out

Real incidents encountered during development of RevenueRescue AI.

---

### LangGraph recursion limit causes AI batch simulation to silently fail

**Problem:**  
AI simulations started with 1,000 events were reported as `status=FAILED` after processing only ~35 events. The backend logged `"Recursion limit of 25 reached without hitting a stop condition"` for some cases, then the entire simulation run aborted.

**Root Cause:**  
LangGraph's default `recursion_limit` is 25. The full recovery pipeline is:  
`risk_detection → context_builder → diagnosis → strategy → policy_check → action_execution → observation → verification` = 8 nodes per attempt, plus `replan → strategy → policy_check → action_execution → observation → verification` = 6 nodes per replan cycle.  
For a case that replans 3 times: 8 + 3×6 = 26 steps — right at the limit. Any case that replanned at all hit the limit and raised `GraphRecursionError`.

**Investigation:**  
Checked backend logs. Saw `simulation_failed error=Recursion limit of 25 reached`. Traced the failure to `graph.invoke(initial_state)` with no config override.

**Attempted Fixes:**  
Initially tried reducing `max_replans` from 3 to 2 — this masked the issue but broke the agent's ability to fully recover recoverable cases.

**Final Fix:**  
Set `recursion_limit=50` in the `graph.invoke()` call:  
```python
result = self._graph.invoke(initial_state, config={"recursion_limit": 50})
```
50 accommodates the maximum realistic path (8 + 4×6 = 32 nodes) with substantial buffer.

Additionally added per-event error isolation in `simulation_service.py` — a try/except around each agent call so a single failing case logs a warning and continues rather than aborting the entire 1,000-event run.

**Validation:**  
Ran `POST /api/v1/simulation/run` with `num_events=1000, random_seed=42`. Simulation completed with `status=COMPLETED`, `recovery_rate_pct=70.83`, `policy_violations=0`.

**Lesson Learned:**  
LangGraph recursion limit must be set explicitly for pipelines with replan loops. Default 25 is too low for any agent with more than 2–3 replan cycles.

---

### Policy violations counter showing 231 for AI simulation

**Problem:**  
After a 1,000-event AI simulation, `policy_violations=231` appeared in results. This made it look like the policy engine had been bypassed 231 times.

**Root Cause:**  
In `simulation_service.py`, policy violations were counted as:
```python
if decision == "DENIED":
    policy_violations += 1
```
A `DENIED` decision is **correct** policy behavior — it means the policy correctly blocked an unauthorized action. A true violation would be an action executing *despite* being DENIED — which the architecture makes impossible. Every DENIED case was being counted as a violation.

**Final Fix:**  
Changed to count only cases where `policy_decision == "DENIED"` **and** `is_recovered == True` — meaning an action executed and produced recovery despite a DENIED decision. By architecture, this count is always 0.
```python
if decision == "DENIED" and recovered:
    policy_violations += 1
```
Also fixed `MetricsService.compute_overview()` which had `policy_violations = 0` hardcoded with a comment "computed from audit events in production".

**Validation:**  
Re-ran simulation. `policy_violations=0`. Matches the architectural guarantee: the action executor hard-checks `policy_result.decision == "APPROVED"` before calling the simulator — a DENIED decision physically cannot result in a recovered payment.

**Lesson Learned:**  
Metric semantics must be defined precisely before implementation. "Policy violation" means unauthorized execution, not "policy said no."

---

### Simulator transaction IDs crashing audit writes

**Problem:**  
After a successful recovery, `agent_run_failed: badly formed hexadecimal UUID string` appeared in backend logs. The case was still marked RECOVERED (recovery itself worked), but the `REVENUE_RECOVERED` audit event failed to write.

**Root Cause:**  
The payment simulator returns transaction IDs in the format `TXN-XXXXXXXX` (e.g., `TXN-1235E8FB1107`). The `RecoveryService._apply_agent_result` method passed this directly to `audit_service.record(transaction_id=...)`. The audit table's `transaction_id` column is a `UUID` type in PostgreSQL — casting `TXN-1235E8FB1107` to UUID raises `ValueError`.

**Final Fix:**  
Added UUID validation before the audit write:
```python
try:
    uuid.UUID(str(raw_txn_id))
    safe_txn_id = str(raw_txn_id)
except (ValueError, AttributeError):
    safe_txn_id = None  # simulator TXN ref — skip UUID column cast
```
Non-UUID transaction IDs from the simulator are stored as `NULL` in the `transaction_id` column. The actual simulator transaction reference is preserved in the case's `verification_result` JSONB field.

**Validation:**  
Triggered a recovery case. Verified `REVENUE_RECOVERED` audit event appears with `result=SUCCESS`. No `ValueError` in backend logs.

**Lesson Learned:**  
When bridging between a typed DB schema and a loosely typed simulation layer, validate types at the boundary rather than assuming they match.

---

### CI lint check failing on every push with different errors

**Problem:**  
GitHub Actions `Lint & Type Check` was failing on nearly every push, with different errors each time — sometimes ruff violations, sometimes bandit findings. The failures were not reproducible locally.

**Root Cause:**  
The CI workflow used `pip install ruff mypy bandit` with no version pins, installing the latest available version on every run. Between pushes, new versions of these tools added new rules or changed behavior — the CI was always running against a moving target.

**Final Fix:**  
Pinned tool versions in `.github/workflows/backend.yml`:
```yaml
pip install "ruff==0.15.11" "bandit==1.9.4"
```
Removed `mypy` from CI — it hung indefinitely on Python 3.12 with large async codebases and type correctness is covered by Pydantic validation + pytest.

Also moved ruff config from deprecated top-level `[tool.ruff]` `select`/`ignore` fields to `[tool.ruff.lint]` in `pyproject.toml`, which is required for modern ruff.

**Validation:**  
CI now runs pinned versions. All 4 checks (ruff lint, ruff format, bandit, tests) pass consistently.

**Lesson Learned:**  
Always pin CI tool versions. `pip install tool` without a version pin is a hidden source of flakiness that manifests days or weeks after the code is written.

---

### `/api/v1/recovery-cases/not-a-uuid` returning HTTP 500

**Problem:**  
Calling `GET /api/v1/recovery-cases/not-a-uuid` returned a 500 Internal Server Error instead of 422 Unprocessable Entity. The stack trace showed `ValueError: badly formed hexadecimal UUID string` in `RecoveryService.get_case_by_id()`.

**Root Cause:**  
`get_case_by_id` called `uuid.UUID(case_id)` without catching `ValueError`. When the URL path parameter was not a valid UUID, this raised an unhandled exception that propagated to a 500 response.

**Final Fix:**  
Added explicit UUID validation at the endpoint handler before calling the service:
```python
try:
    _uuid.UUID(case_id)
except (ValueError, AttributeError):
    raise HTTPException(status_code=422, detail="Invalid case_id: must be a valid UUID")
```

**Validation:**  
`GET /recovery-cases/not-a-uuid` now returns `422 Unprocessable Entity`.

**Lesson Learned:**  
FastAPI does not automatically validate path parameters as UUIDs unless the type hint is `uuid.UUID` rather than `str`. Using `str` type hints for path parameters requires manual validation.
