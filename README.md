# RevenueRescue AI

**"Find revenue that's slipping away and win it back."**

Razorpay Buildathon — Track 03: AI Revenue Recovery

---

## What it does

RevenueRescue AI is a bounded autonomous revenue recovery agent. It:

1. **Detects** failed payments, failed subscriptions, and abandoned checkouts
2. **Diagnoses** the failure using LLM reasoning (or deterministic fallback — no API key required)
3. **Proposes** a context-aware recovery strategy
4. **Enforces** merchant-defined policy before any action executes (deterministic, no LLM involvement)
5. **Executes** recovery actions through a simulated payment/communication layer
6. **Verifies** recovery from authoritative simulator state — never from LLM output
7. **Measures** verified recovered revenue across a batch with a complete, append-only audit trail

> ⚠ All data is synthetic. No real payments, no real customer data, no real gateways. Ever.

---

## Architecture

```
Revenue Risk Events (3 scenarios)
         │
┌────────┼────────────────────┐
▼        ▼                    ▼
FAILED_PAYMENT  FAILED_SUBSCRIPTION  CHECKOUT_ABANDONED
         │
         ▼
  Event Ingestion / Risk Detector
         ↓
  Context Builder
         ↓
  Diagnosis Agent (LLM or deterministic fallback)
         ↓
  Recovery Strategy Agent
         ↓
  Policy Engine ◄─── deterministic gate, zero LLM involvement
         ↓
  Action Executor (APPROVED actions only)
         ↓
  Payment Simulator / Communication Simulator
         ↓
  Recovery Verifier ◄─── authoritative — not LLM output
         ↓
  RECOVERED → STOP   |   REPLAN → Strategy   |   ESCALATE
         ↓
  Audit Ledger (append-only)
         ↓
  Dashboard (real numbers only — nothing hard-coded)
```

**Core guarantee:** The LLM reasons. It never executes financial actions, never authorizes itself, and never declares revenue recovered. Only the Policy Engine authorizes actions. Only the Recovery Verifier confirms recovery.

---

## Recovery scenarios

| Scenario | Failure types | Recovery approach |
|---|---|---|
| Failed Payment | INSUFFICIENT_FUNDS, BANK_DECLINE, EXPIRED_METHOD, GATEWAY_TEMPORARY, AUTH_FAILURE | Retry / update method / escalate |
| Failed Subscription | MANDATE_FAILURE, SUBSCRIPTION_GRACE, INSUFFICIENT_FUNDS | Retry sequencing within grace window |
| Checkout Abandonment | CHECKOUT_ABANDONED | Recovery message → simulate resume → verify payment |

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14, TypeScript, Tailwind CSS, Recharts, shadcn/ui |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Agent | LangGraph, LangChain, OpenAI (optional), MockProvider (deterministic fallback) |
| Database | PostgreSQL 16 |
| Cache / Jobs | Redis, Celery |
| Simulation | Faker, Pandas, NumPy, seeded RNG |
| Testing | Pytest, Playwright, Vitest |
| Quality | Ruff, MyPy, Bandit |
| CI/CD | GitHub Actions |
| Dev | Docker Compose |

---

## Prerequisites

- Docker Desktop
- Git
- Node.js 20+
- Python 3.12+

That's it. Everything else is managed by Docker Compose and `pip`/`npm`.

---

## Quick start

```bash
git clone <repo>
cd revenue-rescue-ai
cp .env.example .env

# Start all services (Postgres, Redis, backend, worker, frontend)
docker compose up --build

# In a separate terminal — run migrations and seed demo data
make migrate
make demo
```

Open **http://localhost:3000** — the dashboard loads with seeded demo cases.

---

## Running without Docker (local dev)

```bash
# Backend
cd revenue-rescue-ai
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r backend/requirements.txt

# Set env vars (copy .env.example → .env, edit DATABASE_URL)
uvicorn backend/app/main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

---

## Environment variables

See `.env.example` for all variables. Key ones:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `mock` | `mock` = deterministic fallback, `openai` = real LLM |
| `OPENAI_API_KEY` | *(empty)* | Only needed if `LLM_PROVIDER=openai` |
| `SIMULATION_MODE` | `true` | Always `true` — no real payments |
| `SIMULATION_SEED` | `42` | Reproducible datasets |
| `DATABASE_URL` | local Postgres | Connection string |

**The system runs fully without an OpenAI API key.** Set `LLM_PROVIDER=mock`.

---

## Running tests

```bash
# All tests (local, no Docker needed)
python -m pytest policies/tests/ simulator/tests/ agents/tests/ \
                 tests/redteam/ tests/integration/ \
                 backend/tests/unit/ backend/tests/integration/ \
                 -v --tb=short
# Expected: 130 passed

# Individual suites
python -m pytest policies/tests/ -v         # 31 tests — policy engine
python -m pytest simulator/tests/ -v        # 23 tests — simulator + baseline
python -m pytest agents/tests/ -v           # 20 tests — LangGraph pipeline
python -m pytest tests/redteam/ -v          # 25 tests — mandatory safety
python -m pytest tests/integration/ -v      # 8 tests  — e2e pipeline
```

---

## Seeded demo dataset

```bash
make demo
```

Creates 20 deterministic synthetic cases covering every scenario in the 5-minute demo:
- Successful retries (GATEWAY_TEMPORARY, INSUFFICIENT_FUNDS)
- Subscription mandate recovery
- Checkout abandonment recovery
- Policy denials (4th retry, opted-out, high-value escalation)
- Red-team cases (UNKNOWN failure, suspicious activity)

All clearly labeled `[SYNTHETIC]` in the audit trail.

---

## 5-minute demo flow

```
0:00–0:30  Batch overview — 3 scenario types, revenue at risk
0:30–1:00  Overview dashboard — KPIs from real simulation data
1:00–2:00  Live case (Failed Payment) → diagnose → policy approve → execute → RECOVERED
2:00–2:30  Live case (Checkout Abandonment) → recovery message → customer resumes → RECOVERED
2:30–3:15  Audit trail — full timeline, policy version on every decision
3:15–4:00  Safety demo: 4th retry → POLICY DENIED; opted-out → DENIED; checkout msg #3 → DENIED
4:00–5:00  Baseline vs AI batch results — both from real simulation data
```

---

## API documentation

FastAPI auto-generates Swagger UI at **http://localhost:8000/docs**.

Key endpoints:

```
POST /api/v1/events/payment-failed         Ingest a payment failure
POST /api/v1/events/checkout-abandoned     Ingest a checkout abandonment
GET  /api/v1/recovery-cases                List all recovery cases
GET  /api/v1/recovery-cases/{id}           Case detail
GET  /api/v1/recovery-cases/{id}/audit     Case audit trail
GET  /api/v1/metrics/overview              Dashboard KPIs
POST /api/v1/simulation/run                Start batch simulation
GET  /api/v1/simulation/{id}               Simulation status + results
GET  /api/v1/policies/active               Active merchant policy
```

---

## Project structure

```
revenue-rescue-ai/
├── backend/         FastAPI app, models, services, schemas
├── agents/          LangGraph state machine, nodes, prompts, tools
├── policies/        Policy engine (deterministic), schemas, tests
├── simulator/       Payment + communication simulator, generators
├── database/        Alembic migrations, demo seed
├── frontend/        Next.js dashboard
├── tests/           Integration, e2e, red-team (25 safety tests)
├── docs/            Architecture docs
├── docker-compose.yml
├── .env.example
├── Makefile
└── pyproject.toml
```

---

## Security model

- No real payment credentials, card numbers, or banking data — ever
- All customer data synthetic (Faker-generated)
- Policy Engine is deterministic, independently testable, zero LLM involvement
- LLM output validated against Pydantic schema — malformed output rejected
- All customer metadata treated as untrusted data (prompt injection defense)
- Idempotency keys on all write endpoints
- Append-only audit trail — no updates, no deletes
- RBAC: MERCHANT_ADMIN, OPERATOR, AUDITOR, SYSTEM roles
- Secrets via `.env` only — never committed, never logged

---

## Definition of done checklist

See `docs/checklist.md` for the full §23 verification checklist.

---

## License

Built for Razorpay Buildathon 2026. All payment data is synthetic.
