# Implementation Progress

Each entry records the commands run and their real results. Nothing is marked done without evidence.

## Phase 1 — Audit and baseline (in progress)

- [x] Git state, branches and recent commits inspected (`main` @ `c6280fe`, uncommitted user edits preserved)
- [x] Python 3.11 venv rebuilt; `pip install -r backend/requirements.txt` OK
- [x] Baseline Python tests: 165 passed
- [x] Baseline lint/bandit recorded (see BASELINE.md)
- [x] Frontend: old `frontend/` removed, `replaced-frontend/` promoted to `frontend/`;
      `tsc --noEmit` and `vite build` pass
- [x] Frontend references updated: CI workflow (pnpm), Dockerfile (pnpm), docker-compose, Makefile, README
- [x] Read Razorpay provider, checkout and webhook endpoints, models, LangGraph graph and nodes
- [x] Live Razorpay credential check: `client.order.all({'count':3})` returned
      **`BadRequestError: Authentication failed`**. The `.env` key has the `rzp_test_` prefix, but the
      key/secret pair is rejected (revoked, or the secret doesn't match the key).
      `RAZORPAY_WEBHOOK_SECRET` is **not set** in `.env`.
- [ ] Read policies / simulator / services in depth

### Audit findings (to fix in Phases 3–5)

Razorpay:
- R1 `_map_status`: `refunded` maps to CANCELLED, and unknown statuses map to **FAILED**. Unknown
  must map to UNKNOWN, and AUTHORIZED/REFUNDED need their own states (spec §4.5).
- R2 `get_payment`: any exception returns FAILED/`PROVIDER_UNAVAILABLE`. A timeout should be UNKNOWN,
  not FAILED.
- R3 `retry_payment` creates a *new order* and returns it as `payment_id`. The verifier node
  then calls `payment.fetch(order_id)`, which can never succeed. Order creation ≠ payment.
- R4 `get_payment_provider` docstring says it falls back to the simulator, but the code (correctly)
  does not. Fix the docstring.
- R5 Webhook: verifies the raw body (matches the official doc) and dedupes on `x-razorpay-event-id`.
  Gaps: only `payment.captured` is handled, so `payment.failed`, `order.paid`, `refund.*` and
  `subscription.*` are ignored. No outbox/retry. The `processed=True` flag is set before processing.
  If reconciliation raises HTTPException (amount mismatch), the receipt rolls back.
- R6 Checkout signature `HMAC(key_secret, order_id|payment_id)` is correct and kept separate from
  the webhook HMAC. Good.
- R7 No auth on `/orders` or `/verify` (public by necessity for checkout). Needs a per-case
  checkout token so arbitrary case UUIDs can't be used.
- R8 There is no `recovery_attempts`/`provider_orders` table, so one order is allowed per case.

Agent graph:
- A1 Nodes record only node names. There's no per-node timing, status or error, and no correlation ID.
- A2 `_fallback_diagnosis` is used when the mock LLM output fails to parse, so a deterministic
  provider-code mapping isn't the primary path.
- A3 No ML prediction node. `scoring_service` is heuristic.
- A4 Checkout recovery and communications return `delivered: True` without any real sender.
  These need to be labelled as simulated/not-implemented.

Lint: F821 forward refs in models; B904 ×3; md5 in recovery_service.
- [ ] `.kiro/specs/revenue-rescue/{requirements,design,tasks}.md`
- [ ] `ACCEPTANCE_MATRIX.md`

## Notebooks (ML phases 6–8, offline only)

- [x] Both notebooks rewritten and executed locally. Details are in `NOTEBOOKS.md`.
- [x] Test ROC-AUC on the chronological split: rule baseline 0.6383; LightGBM 0.6640; Transformer 0.6628; hybrid 0.6648.
      The hybrid is not significantly better than LightGBM alone.
- [x] Artifacts saved to `models/artifacts/`, reloaded, and checked to give identical predictions.
- [ ] Load the artifacts in the backend and agent (ML prediction node)

## Known blockers

| Blocker | Impact | Unblock |
| --- | --- | --- |
| Docker daemon not running | No Postgres/Redis/Kafka/HDFS/Spark integration tests | Start Docker Desktop |
| Razorpay test key/secret rejected (`Authentication failed`, verified 2026-10-12) | No live order/checkout/payment verification possible | Regenerate Test Mode keys in Razorpay Dashboard → Settings → API Keys and update `.env`. Also set `RAZORPAY_WEBHOOK_SECRET` |
| Java 24 only | PySpark 3.5 needs JDK 17 | Install Temurin 17, or run Spark in Docker |
