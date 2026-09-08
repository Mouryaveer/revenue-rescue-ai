# Architecture — RevenueRescue AI

## Core principle

```
AI PROPOSES
     ↓
POLICY AUTHORIZES   (deterministic — LLM cannot touch this)
     ↓
EXECUTOR ACTS       (only on APPROVED actions)
     ↓
SYSTEM OBSERVES     (payment simulator)
     ↓
VERIFIER CONFIRMS   (authoritative simulator/DB state — never LLM output)
     ↓
STOP / REPLAN / ESCALATE
```

## Components

### 1. Event Ingestion
- `POST /events/payment-failed` — FAILED_PAYMENT, FAILED_SUBSCRIPTION
- `POST /events/checkout-abandoned` — CHECKOUT_ABANDONMENT
- Idempotency key on every event — duplicates ignored, not double-processed
- Input validated by Pydantic before any processing

### 2. Risk Detector
- Checks: amount > 0, not already recovered, payment hasn't already succeeded
- Creates `RecoveryCase` with `status=DETECTED`
- Appends `CASE_CREATED` to audit ledger

### 3. Context Builder
- Assembles typed context object from DB state
- All customer metadata treated as untrusted data (prompt injection boundary)
- Re-fetches authoritative state before passing to agent — never stale

### 4. Diagnosis Agent (LLM node)
- LLM input: structured context object (case_id, failure_reason, amount, segment, retry_count)
- LLM output: `DiagnosisOutput` Pydantic schema — validated on every call
- On malformed output: reject → use deterministic fallback → log the failure
- `UNKNOWN` failure → low confidence → `needs_human_review=True`

### 5. Strategy Agent (LLM node)
- LLM input: diagnosis output + case context
- LLM output: `StrategyOutput` Pydantic schema
- Fallback: rule-based strategy map keyed on failure_reason

### 6. Policy Engine
- Deterministic, zero LLM involvement
- Sequential check pipeline (see `policies/engine/policy_engine.py`)
- Fail closed: engine error → ESCALATE, never APPROVED
- Every decision records `policy_id` + `policy_version`
- Output: `PolicyEvaluationResult` — APPROVED / DENIED / ESCALATE / STOP

### 7. Action Executor
- Only executes if `policy_result.decision == "APPROVED"`
- Calls Payment Simulator or Communication Simulator
- Records `action_idempotency_key` — replays blocked

### 8. Payment Simulator
- Self-contained, no real gateway, no real credentials
- Seeded RNG (reproducible outcomes)
- Returns `SimulatedPaymentResult` — the authoritative outcome

### 9. Recovery Verifier
- Reads simulator result — never LLM output
- Only component that can set `case_is_recovered=True`
- Records `REVENUE_RECOVERED` audit event with verified amount

### 10. Audit Ledger
- Append-only PostgreSQL table (`audit_events`)
- Every significant event recorded: policy_id, policy_version, actor, result, amount
- Never updated, never deleted

## Security boundaries

```
Untrusted zone:   customer_metadata, external events
Trust boundary:   Pydantic schema validation + type system
Trusted zone:     Policy Engine, Recovery Verifier, Audit Ledger
```

## Failure handling

| Failure | Response |
|---|---|
| LLM unavailable | Deterministic MockProvider fallback |
| Policy engine error | Fail closed → ESCALATE |
| Duplicate event | Idempotency key → return existing case |
| Malformed LLM output | Reject → fallback → log |
| Already recovered | STOP — no further actions |
| Payment simulator error | Escalate — no financial action |
