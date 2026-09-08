# Database Schema

PostgreSQL 16. All migrations via Alembic.

## Table overview

| Table | Purpose |
|---|---|
| `users` | Auth — RBAC roles |
| `customers` | Synthetic customer profiles — no real PII |
| `payment_methods` | Synthetic payment methods — no real card data |
| `subscriptions` | Subscription plans and status |
| `transactions` | Payment transaction records |
| `payment_failures` | Failure events linked to transactions |
| `checkout_sessions` | Checkout abandonment tracking |
| `recovery_cases` | Core: one per revenue-at-risk event |
| `recovery_actions` | Every action proposed + policy result |
| `agent_runs` | LangGraph execution records |
| `agent_decisions` | Per-node decision records |
| `escalations` | Escalation records with context snapshots |
| `audit_events` | **Append-only** event ledger — never updated |
| `policies` | Versioned merchant policies |
| `simulation_runs` | Batch simulation metadata + results |

## Key constraints

- `recovery_cases.source_event_key` — UNIQUE — idempotency for event ingestion
- `transactions.idempotency_key` — UNIQUE — idempotency for payment actions
- `recovery_actions.action_idempotency_key` — UNIQUE — idempotency for action replay
- `audit_events` — no UPDATE/DELETE ever called — append only by convention and code review
- `customers.is_synthetic = true` always — enforced at model level

## Circular FK resolution

`checkout_sessions` and `payment_failures` both reference `recovery_cases`. `recovery_cases` references `checkout_sessions`. This is handled in the migration by:
1. Creating `checkout_sessions` without the `recovery_case_id` FK
2. Creating `recovery_cases` with the FK to `checkout_sessions`
3. Adding `checkout_sessions.recovery_case_id` FK via `ALTER TABLE`

## Running migrations

```bash
# Apply all migrations
make migrate

# Generate a new migration after model changes
docker compose exec backend alembic revision --autogenerate -m "describe change"

# Rollback one step
docker compose exec backend alembic downgrade -1
```

## JSONB fields

- `recovery_cases.diagnosis` — validated `DiagnosisOutput` dict
- `recovery_cases.strategy` — validated `StrategyOutput` dict
- `agent_runs.node_trace` — list of node names visited
- `audit_events.payload` — full event context snapshot
- `simulation_runs.results` — computed metrics dict
- `policies.config` — full `PolicyConfig` dict
