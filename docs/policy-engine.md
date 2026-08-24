# Policy Engine

## Principle

The Policy Engine is the safety boundary of the system. It is:
- **Deterministic** — same inputs always produce the same output
- **Independent** — callable and testable without the agent or LLM
- **Fail-closed** — any error returns ESCALATE, never APPROVED
- **Versioned** — every decision records `policy_id` + `policy_version`

The LLM has zero involvement in policy decisions. Ever.

## Authorization pipeline (sequential)

```
1. Validate input schema
2. Load active policy (by version)
3. Check stopping conditions    ← highest priority
   - case already RECOVERED → STOP
   - payment already succeeded → STOP
4. Check customer state
   - opted out → DENY
   - suspended → DENY
5. Check monetary limits
   - amount > max_auto_recovery → ESCALATE
   - amount <= 0 → DENY
6. Check retry limits
   - retry_count >= max_retries → ESCALATE
7. Check communication limits
   - communication_count >= max → DENY
8. Check checkout-specific rules
   - timeout not elapsed → DENY
   - amount below minimum → DENY
   - message limit exceeded → DENY
9. Check timing rules
   - hours_since_last < min_interval → DENY
10. Check escalation triggers
    - failure_reason == UNKNOWN → ESCALATE
    - diagnosis_confidence < threshold → ESCALATE
11. APPROVED
```

Conflict resolution: **specific restriction beats general permission**. If ambiguous → ESCALATE.

## Decision output

```json
{
  "allowed": false,
  "decision": "ESCALATE",
  "reason": "MAX_RETRIES_EXCEEDED",
  "policy_id": "merchant_default_v1",
  "policy_version": 1,
  "violations": ["MAX_RETRIES_EXCEEDED"]
}
```

## Testing

`policies/tests/test_policy_engine.py` — 40+ tests covering every rule, including all 25 red-team cases. Run before wiring to anything else.

## Policy versioning

When a policy changes, a new version is created. Old `recovery_actions` and `audit_events` retain their `policy_version` reference — historical decisions remain fully explainable even after policy updates.
