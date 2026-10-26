# RevenueRescue AI

> **Find revenue that's slipping away — and win it back.**

RevenueRescue AI is a **bounded autonomous revenue recovery agent** that detects failed payments and abandoned checkouts, reasons about the failure, proposes recovery strategies, enforces deterministic merchant policies, executes only approved actions, and verifies recovered revenue from authoritative provider state.

**The core principle:**

> **The LLM reasons. The Policy Engine authorizes. The Recovery Verifier confirms.**

No LLM can authorize a financial action or declare revenue recovered.

---

## ✨ What It Does

RevenueRescue AI provides an end-to-end recovery pipeline for common revenue-loss scenarios:

* 🔎 Detects **failed payments**
* 🔁 Detects **failed subscriptions**
* 🛒 Detects **abandoned checkouts**
* 🧠 Diagnoses failures using an LLM or deterministic fallback
* 🎯 Proposes context-aware recovery strategies
* 🛡️ Enforces merchant-defined policies **deterministically**
* ⚡ Executes **only policy-approved actions**
* ✅ Verifies recovery using **authoritative provider state**
* 📊 Measures verified recovered revenue across simulation batches
* 🧾 Maintains a complete **append-only audit trail**
* 🚨 Escalates or replans when recovery fails

The system runs completely without an OpenAI API key using a deterministic mock provider.

> ⚠️ **Simulation only:** All simulations use synthetic data. No live payment credentials, real customer data, or real money are supported.

---

# 🏗️ Architecture

```text
                    Revenue Risk Events
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 FAILED_PAYMENT    FAILED_SUBSCRIPTION   CHECKOUT_ABANDONED
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                 Event Ingestion /
                  Risk Detection
                           │
                           ▼
                   Context Builder
                           │
                           ▼
                Diagnosis Agent
             ┌─────────────┴─────────────┐
             │                           │
        OpenAI LLM              Deterministic Fallback
             │                           │
             └─────────────┬─────────────┘
                           ▼
                Recovery Strategy Agent
                           │
                           ▼
                 ┌──────────────────┐
                 │   Policy Engine  │
                 │                  │
                 │  DETERMINISTIC   │
                 │   ZERO LLM AUTH  │
                 └────────┬─────────┘
                          │
                 APPROVED ACTIONS ONLY
                          │
                          ▼
                   Action Executor
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
      Payment Simulator      Communication Simulator
             │                         │
             └────────────┬────────────┘
                          ▼
                Recovery Verifier
                 AUTHORITATIVE STATE
                          │
             ┌────────────┼────────────┐
             ▼            ▼            ▼
         RECOVERED      REPLAN      ESCALATE
             │            │
             ▼            └──────► Strategy
            STOP
             │
             ▼
        Audit Ledger
        Append-only
             │
             ▼
          Dashboard
      Real simulation data
```

### Core safety guarantees

| Component                 | Responsibility               | Can authorize money movement? |
| ------------------------- | ---------------------------- | ----------------------------: |
| **LLM / Diagnosis Agent** | Reason about failure         |                             ❌ |
| **Strategy Agent**        | Recommend recovery action    |                             ❌ |
| **Policy Engine**         | Enforce merchant policy      |                             ✅ |
| **Action Executor**       | Execute approved action      |    Only after policy approval |
| **Recovery Verifier**     | Verify provider state        |                             ❌ |
| **Audit Ledger**          | Record every decision/action |                             ❌ |

**The LLM never executes financial actions, authorizes itself, or declares revenue recovered.**

---

# 💳 Test-Mode Payment Flow

The `/checkout?case_id=<recovery-case-id>` route provides an isolated test checkout flow using the configured payment provider.

The backend:

1. Loads the **exact persisted recovery case**
2. Creates the provider order for that case
3. Returns only the provider's **public key ID**
4. Stores the provider order ID
5. Receives checkout callback values
6. Performs server-side verification
7. Fetches the payment directly from the configured provider
8. Compares the authoritative payment against the recovery case
9. Counts revenue only when the provider reports a valid captured payment

### Revenue is counted only when all conditions match

```text
Provider payment = CAPTURED
        +
Order ID matches case
        +
Amount matches case
        +
Currency matches case
        ↓
     RECOVERED
```

The following **never count as recovered revenue**:

* Pending payments
* Failed payments
* Mismatched orders
* Mismatched amounts
* Mismatched currencies
* Duplicate callbacks
* Unsigned/invalid callbacks
* LLM-generated claims of success

---

# 🎯 Recovery Scenarios

| Scenario                 | Failure Types                                                                               | Recovery Approach                                    |
| ------------------------ | ------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| **Failed Payment**       | `INSUFFICIENT_FUNDS`, `BANK_DECLINE`, `EXPIRED_METHOD`, `GATEWAY_TEMPORARY`, `AUTH_FAILURE` | Retry, update payment method, or escalate            |
| **Failed Subscription**  | `MANDATE_FAILURE`, `SUBSCRIPTION_GRACE`, `INSUFFICIENT_FUNDS`                               | Retry sequencing within the grace window             |
| **Checkout Abandonment** | `CHECKOUT_ABANDONED`                                                                        | Recovery message → simulated resume → verify payment |

---

# 🧠 Agent Pipeline

RevenueRescue AI separates **reasoning** from **authorization**.

### 1. Event ingestion

A payment failure, subscription failure, or checkout abandonment enters the system.

### 2. Context building

Relevant case information is assembled into a structured context.

### 3. Diagnosis

The diagnosis agent determines the likely failure reason.

It can use:

* OpenAI
* A deterministic mock/fallback implementation

The LLM output is validated against a **Pydantic schema** before it enters the pipeline.

### 4. Recovery strategy

The strategy agent proposes a context-aware recovery action.

### 5. Policy enforcement

The deterministic Policy Engine evaluates the proposed action against merchant-defined rules.

**No LLM is involved in authorization.**

### 6. Action execution

Only actions explicitly approved by the Policy Engine can execute.

### 7. Recovery verification

The system checks authoritative provider/simulator state.

The LLM's opinion is irrelevant to whether revenue was recovered.

### 8. Replan / escalate / stop

```text
RECOVERED ─────────► STOP

NOT RECOVERED ─────► REPLAN
                         │
                         └──► Strategy Agent

UNSAFE / UNRESOLVED ──► ESCALATE
```

---

# 🛡️ Safety & Security Model

RevenueRescue AI is designed around **bounded autonomy**.

### Deterministic authorization

The Policy Engine is:

* Deterministic
* Independently testable
* Versioned
* Free of LLM decision-making
* The only component allowed to authorize recovery actions

### LLM isolation

LLM output:

* Is schema-validated
* Cannot directly execute actions
* Cannot bypass policy
* Cannot authorize itself
* Cannot mark revenue as recovered
* Is treated as untrusted reasoning output

### Prompt-injection defense

Customer metadata is treated as **untrusted input**.

Customer-controlled content cannot directly modify system policy or grant action permissions.

### Idempotency

All write endpoints use idempotency keys to prevent duplicate processing.

### Append-only auditing

Audit records are append-only:

* No updates
* No deletes
* Policy version recorded
* Decision recorded
* Action recorded
* Verification recorded

### RBAC

Supported roles:

```text
MERCHANT_ADMIN
OPERATOR
AUDITOR
SYSTEM
```

### Secrets

Secrets are provided through environment variables and are:

* Never committed
* Never logged
* Never exposed to the frontend

### Synthetic data only

No real:

* Payment credentials
* Card numbers
* Banking data
* Customer records

are required or supported.

---

# 🧪 Simulation Environment

RevenueRescue AI includes a deterministic simulation environment for evaluating recovery strategies.

Simulation uses:

* Faker
* Pandas
* NumPy
* Seeded random number generation

Configure reproducibility with:

```env
SIMULATION_MODE=true
SIMULATION_SEED=42
```

Every simulated customer and payment is synthetic.

---

# 📊 Seeded Demo Dataset

Run:

```bash
make demo
```

The demo creates **20 deterministic synthetic recovery cases** covering the major paths:

* Successful retries

  * `GATEWAY_TEMPORARY`
  * `INSUFFICIENT_FUNDS`
* Subscription mandate recovery
* Checkout abandonment recovery
* Policy denials

  * 4th retry
  * Customer opted out
  * High-value escalation
* Red-team cases

  * Unknown failure
  * Suspicious activity

All synthetic activity is clearly labeled:

```text
[SYNTHETIC]
```

in the audit trail.

---


---

# 🧰 Tech Stack

| Layer            | Technology                                               |
| ---------------- | -------------------------------------------------------- |
| **Frontend**     | Vite, React, TypeScript                                  |
| **Backend**      | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| **Agents**       | LangGraph, LangChain, OpenAI (optional)                  |
| **Fallback**     | Deterministic MockProvider                               |
| **Database**     | PostgreSQL 16                                            |
| **Cache / Jobs** | Redis, Celery                                            |
| **Simulation**   | Faker, Pandas, NumPy, seeded RNG                         |
| **Testing**      | Pytest, Playwright, Vitest                               |
| **Quality**      | Ruff, MyPy, Bandit                                       |
| **CI/CD**        | GitHub Actions                                           |
| **Development**  | Docker Compose                                           |

---

# 🚀 Quick Start

## Prerequisites

Install:

* [Docker Desktop](https://www.docker.com/products/docker-desktop/)
* Git
* Node.js 20+
* Python 3.12+

Everything else is managed by Docker Compose and pip/npm.

## 1. Clone the repository

```bash
git clone <repo-url>
cd revenue-rescue-ai
```

## 2. Configure environment variables

```bash
cp .env.example .env
```

The default configuration runs without an OpenAI API key.

## 3. Start the stack

```bash
docker compose up --build
```

This starts:

* PostgreSQL
* Redis
* Backend
* Celery worker
* Frontend

## 4. Run migrations

In a separate terminal:

```bash
make migrate
```

## 5. Seed demo data

```bash
make demo
```

## 6. Open the dashboard

```text
http://localhost:3000
```

The dashboard should load with the seeded synthetic recovery cases.

---

# 💻 Local Development Without Docker

### Backend

```bash
cd revenue-rescue-ai

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r backend/requirements.txt
```

Train or verify LightGBM recovery model (optional — deterministic fallback is active if omitted):

```bash
python scripts/train_lightgbm.py
```

Configure:

```bash
cp .env.example .env
```

Start the API:

```bash
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

---

# ⚙️ Configuration

See `.env.example` for the complete configuration.

Important variables:

| Variable                          | Default        | Description                                                        |
| --------------------------------- | -------------- | ------------------------------------------------------------------ |
| `LLM_PROVIDER`                    | `deterministic`| `deterministic` (default, ₹0), `cloudflare` (Workers AI DeepSeek-R1), `openai` |
| `REASONING_MODEL`                 | `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` | Serverless model for Cloudflare Workers AI |
| `CLOUDFLARE_ACCOUNT_ID`           | Empty          | Cloudflare dashboard Account ID (for Workers AI)                   |
| `CLOUDFLARE_API_TOKEN`            | Empty          | Cloudflare API token with Workers AI Read permissions              |
| `OPENAI_API_KEY`                  | Empty          | Required only when `LLM_PROVIDER=openai`                           |
| `LIGHTGBM_MODEL_PATH`             | `models/artifacts/lightgbm_recovery_model.joblib` | Path to trained LightGBM model bundle |
| `PAYMENT_MODE`                    | `simulation`   | Financial safety: `simulation`, `test`, `live` (strictly locked)  |
| `ALLOW_REAL_PAYMENTS`             | `false`        | Non-negotiable safety invariant for ₹0 budget                     |
| `PAYMENT_PROVIDER`                | `simulator`    | Configured payment provider (`simulator`)                          |
| `SIMULATION_MODE`                 | `true`         | Enables isolated synthetic simulations                             |
| `SIMULATION_SEED`                 | `42`           | Seed for reproducible datasets                                     |
| `DATABASE_URL`                    | Local Postgres | PostgreSQL or SQLite connection string                             |

### Free-Tier Serverless Reasoning (Cloudflare Workers AI)

Run DeepSeek-R1-Distill-Qwen reasoning at ₹0 cost with 10,000 free neurons/day:

```env
LLM_PROVIDER=cloudflare
REASONING_MODEL=@cf/deepseek-ai/deepseek-r1-distill-qwen-32b
CLOUDFLARE_ACCOUNT_ID=your_account_id
CLOUDFLARE_API_TOKEN=your_api_token
```

### Run without any Cloud Credentials (Default)

The default configuration requires **no external API keys or paid accounts**:

```env
LLM_PROVIDER=deterministic
```

---

# 🚀 Cloud Deployment & ML Training Guides

- 📖 **Zero-Cost Cloud Deployment Guide**: [docs/ZERO_COST_DEPLOYMENT.md](docs/ZERO_COST_DEPLOYMENT.md) — Render Free + Supabase Free + Cloudflare Workers AI setup.
- 🤖 **LightGBM Model Training Guide**: [docs/MODEL_TRAINING.md](docs/MODEL_TRAINING.md) — Feature engineering, leakage prevention, calibration, and artifact management.

---

# 🧪 Testing

Run the complete test suite:

```bash
python -m pytest \
  policies/tests/ \
  simulator/tests/ \
  agents/tests/ \
  tests/redteam/ \
  tests/integration/ \
  backend/tests/unit/ \
  backend/tests/integration/ \
  -v --tb=short
```

Expected:

```text
130 passed
```

### Individual suites

```bash
# Policy Engine
python -m pytest policies/tests/ -v

# Simulator
python -m pytest simulator/tests/ -v

# Agent pipeline
python -m pytest agents/tests/ -v

# Red-team / safety
python -m pytest tests/redteam/ -v

# End-to-end integration
python -m pytest tests/integration/ -v
```

### Test coverage by suite

| Suite         | Tests | Purpose                         |
| ------------- | ----: | ------------------------------- |
| Policy Engine |    31 | Deterministic authorization     |
| Simulator     |    23 | Payment and recovery simulation |
| Agents        |    20 | LangGraph recovery pipeline     |
| Red Team      |    25 | Mandatory safety scenarios      |
| Integration   |     8 | End-to-end behavior             |

---

# 🔌 API

FastAPI automatically generates interactive API documentation.

**Swagger UI:**

```text
http://localhost:8000/docs
```

### Key endpoints

| Method | Endpoint                            | Purpose                       |
| ------ | ----------------------------------- | ----------------------------- |
| `POST` | `/api/v1/events/payment-failed`     | Ingest payment failure        |
| `POST` | `/api/v1/events/checkout-abandoned` | Ingest checkout abandonment   |
| `GET`  | `/api/v1/recovery-cases`            | List recovery cases           |
| `GET`  | `/api/v1/recovery-cases/{id}`       | Get case details              |
| `GET`  | `/api/v1/recovery-cases/{id}/audit` | Get case audit trail          |
| `GET`  | `/api/v1/metrics/overview`          | Dashboard KPIs                |
| `POST` | `/api/v1/simulation/run`            | Start batch simulation        |
| `GET`  | `/api/v1/simulation/{id}`           | Get simulation status/results |
| `GET`  | `/api/v1/policies/active`           | Get active merchant policy    |

---

# 📁 Project Structure

```text
revenue-rescue-ai/
├── backend/         FastAPI app, models, services, schemas
├── agents/          LangGraph state machine, nodes, prompts, tools
├── policies/        Policy engine (deterministic), schemas, tests
├── simulator/       Payment + communication simulator, generators
├── database/        Alembic migrations, demo seed
├── frontend/        React + Vite dashboard (pnpm)
├── tests/           Integration, e2e, red-team (25 safety tests)
├── docs/            Architecture docs
├── docker-compose.yml
├── .env.example
├── Makefile
└── pyproject.toml
```

---

# 🔐 Security Principles

RevenueRescue AI follows a **defense-in-depth** model:

```text
Untrusted Input
      │
      ▼
Structured Validation
      │
      ▼
LLM Reasoning
      │
      ▼
Schema Validation
      │
      ▼
Deterministic Policy Engine
      │
      ▼
Approved Action
      │
      ▼
Authoritative Verification
      │
      ▼
Append-only Audit
```

The system deliberately prevents a language model from becoming an autonomous financial authority.

### Non-negotiable boundaries

```text
LLM
 └── Can reason
 └── Cannot authorize

Policy Engine
 └── Can authorize
 └── Cannot be replaced by LLM output

Action Executor
 └── Can execute
 └── Only approved actions

Recovery Verifier
 └── Can confirm provider state
 └── Never trusts LLM claims
```

---

# 📋 Definition of Done

The complete verification checklist is available in:

```text
docs/checklist.md
```

It covers:

* Architecture
* Policy enforcement
* Recovery execution
* Provider verification
* Idempotency
* Auditability
* Prompt-injection resistance
* Red-team scenarios
* Simulation integrity
* Test coverage

---

# 🗺️ Recovery Decision Model

A simplified recovery decision looks like:

```text
                Failure Detected
                       │
                       ▼
                 Diagnose
                       │
                       ▼
              Propose Recovery
                       │
                       ▼
               Policy Check
                 /          \
             DENY            APPROVE
              │                 │
              ▼                 ▼
          Audit + Stop      Execute
                                │
                                ▼
                           Verify State
                           /     |      \
                          /      |       \
                    Recovered  Failed   Unsafe
                       │         │         │
                       ▼         ▼         ▼
                      STOP     REPLAN   ESCALATE
```

---

# 📈 What Makes RevenueRescue AI Different?

### Traditional automation

```text
IF payment_failed
THEN retry_payment
```

### Unbounded AI agent

```text
LLM decides what happened
        ↓
LLM decides what to do
        ↓
LLM executes action
        ↓
LLM says "recovered"
```

### RevenueRescue AI

```text
Detect
  ↓
Reason
  ↓
Propose
  ↓
Deterministic Policy Gate
  ↓
Execute Approved Action
  ↓
Verify Authoritative State
  ↓
Record Everything
```

This separation makes the system **auditable, testable, bounded, and reproducible**.

---

# ⚠️ Simulation & Payment Safety Notice

RevenueRescue AI is a simulation and engineering project.

**It does not support real-money transactions.**

All payment and customer data used by the project is synthetic or test-mode data.

Never commit:

```text
.env
API keys
payment secrets
webhook secrets
real customer data
real card information
```

---

# 📄 License

See the repository license file for licensing information.

---

## ⭐ Project Status

RevenueRescue AI is designed as a production-style demonstration of **bounded autonomous agents for revenue recovery**, with deterministic authorization and authoritative verification at the financial boundary.

If you find the project useful, consider giving it a ⭐ on GitHub.
