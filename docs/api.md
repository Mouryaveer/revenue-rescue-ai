# API Reference

FastAPI auto-generates interactive docs at: http://localhost:8000/docs

## Base URL

`http://localhost:8000/api/v1`

## Auth

```
POST /auth/login      { username, password } → { access_token, role }
POST /auth/register   { username, password, role } → { access_token, role }
```

Include token in header: `Authorization: Bearer <token>`

## Events (idempotent)

```
POST /events/payment-failed
Body: {
  idempotency_key: str,      # required — duplicate keys ignored
  customer_id: str,
  amount_paise: int,         # must be > 0
  currency: str,             # "INR"
  failure_reason: str,       # one of the FailureReason enum values
  failure_message?: str,
  subscription_id?: str
}
Response 202: { recovery_case_id, status, message, is_duplicate }

POST /events/checkout-abandoned
Body: {
  idempotency_key: str,
  customer_id: str,
  checkout_session_id: str,
  amount_paise: int,
  currency: str
}
Response 202: { recovery_case_id, status, message, is_duplicate }
```

## Recovery Cases

```
GET  /recovery-cases?status=&scenario=&failure_reason=&limit=&offset=
GET  /recovery-cases/{id}
POST /recovery-cases/{id}/run       → trigger agent (async)
POST /recovery-cases/{id}/escalate  → manual escalation
GET  /recovery-cases/{id}/audit     → case audit trail
```

## Metrics

```
GET /metrics/overview?simulation_run_id=
    → { revenue_at_risk_paise, revenue_recovered_paise, recovery_rate_pct,
        active_cases, escalated_cases, policy_violations, by_scenario, by_failure_reason }

GET /metrics/revenue-recovered?simulation_run_id=

GET /metrics/baseline-comparison?ai_run_id=&baseline_run_id=
    → { REVENUERESCUE_AI: {...}, BASELINE: {...}, improvement_pct }
```

## Simulation

```
POST /simulation/run
Body: {
  num_customers: int,
  num_events: int,
  failure_rate: float,
  random_seed: int,        # reproducibility
  is_baseline: bool,
  label: str
}
Response 202: { simulation_id, status, ... }

GET /simulation/{simulation_id}  → status + results
GET /simulation                   → list all runs
```

## Policies

```
GET  /policies          → list all versions
GET  /policies/active   → current active policy
POST /policies          → create new policy version (deactivates old)
```

## Audit

```
GET /audit?event_type=&actor=&limit=&offset=
```

## Error codes

| Code | Meaning |
|---|---|
| 400 | Validation error — check request schema |
| 401 | Missing or invalid JWT |
| 403 | Insufficient role |
| 404 | Resource not found |
| 409 | Conflict (duplicate username) |
| 422 | Pydantic validation failure |
| 500 | Server error — check logs |
