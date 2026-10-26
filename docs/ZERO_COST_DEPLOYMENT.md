# Zero-Cost Cloud Deployment Guide

> **Budget: ₹0 / month** — All services use verified free tiers with documented quotas.

---

## Architecture Overview

```text
Frontend (Static Hosting)
    │
    ▼
FastAPI Backend (Render Free Tier)
    ├── LightGBM (CPU inference, in-process)
    ├── LangGraph Recovery Agent
    ├── Policy Engine (deterministic)
    └── Recovery Verifier
    │
    ├──► Supabase Free PostgreSQL (persistent storage)
    └──► Cloudflare Workers AI (DeepSeek-R1 reasoning)
```

---

## Service Quotas & Limitations

### Render Free Tier

| Resource | Limit |
| --- | --- |
| Plan | `free` |
| RAM | 512 MB |
| CPU | 0.1 shared |
| Hours | 750/month |
| Spin-down | After 15 min inactivity (~50s cold start) |
| Custom domains | Not available on free plan |

> [!WARNING]
> Render does not offer hard spending caps. Monitor usage to avoid surprise charges if you add paid features later.

### Supabase Free Tier

| Resource | Limit |
| --- | --- |
| Database storage | 500 MB |
| Bandwidth | 2 GB/month |
| Monthly active users | 50,000 |
| File storage | 500 MB |
| Inactivity pause | After 1 week (must log in to unpause) |

### Cloudflare Workers AI Free Tier

| Resource | Limit |
| --- | --- |
| Neurons/day | 10,000 |
| Supported model | `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` |
| Cost | Free within neuron budget |

> [!NOTE]
> The neuron budget is shared across all models used under the same account.

---

## Prerequisites

- GitHub account (for deployment from repo)
- Render account (free, no credit card required for free plan)
- Supabase account (free, no credit card required)
- Cloudflare account (free, for Workers AI)

---

## Step 1: Supabase Database Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database → Connection string → URI**
3. Replace `postgresql://` with `postgresql+asyncpg://` for SQLAlchemy async compatibility
4. Use the **Transaction pooler** connection (port 6543) for PgBouncer compatibility
5. The app's `database.py` already disables the prepared statement cache for PgBouncer

**Connection string format:**
```
postgresql+asyncpg://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

---

## Step 2: Cloudflare Workers AI Setup

1. Create a free account at [cloudflare.com](https://dash.cloudflare.com)
2. Navigate to **AI → Workers AI**
3. Get your **Account ID** from the dashboard URL or sidebar
4. Create an API token: **My Profile → API Tokens → Create Token → Workers AI (Read)**
5. Test with curl:

```bash
curl https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/@cf/deepseek-ai/deepseek-r1-distill-qwen-32b \
  -H 'Authorization: Bearer {API_TOKEN}' \
  -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

---

## Step 3: Render Deployment

### Option A: Blueprint (Recommended)

1. Fork or push the repo to GitHub
2. Go to Render Dashboard → **Blueprints → New Blueprint Group**
3. Connect your GitHub repo — Render will use the `render.yaml` in the repo root
4. Set the secret environment variables:
   - `DATABASE_URL` — from Supabase (Step 1)
   - `CLOUDFLARE_ACCOUNT_ID` — from Cloudflare (Step 2)
   - `CLOUDFLARE_API_TOKEN` — from Cloudflare (Step 2, mark as **Secret**)
   - `LLM_PROVIDER` — change from `deterministic` to `cloudflare` to enable AI reasoning

### Option B: Manual Setup

1. Create **New → Web Service** on Render
2. Connect your GitHub repo
3. Configure:
   - **Name:** `revenuerescue-backend`
   - **Runtime:** Python
   - **Build Command:** `pip install --no-cache-dir -r backend/requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. Set environment variables (see `render.yaml` for the full list)

### Environment Variables Reference

| Variable | Value | Notes |
| --- | --- | --- |
| `APP_ENV` | `production` | |
| `DEBUG` | `false` | |
| `PYTHONPATH` | `.:backend` | Required for imports |
| `PORT` | `8000` | |
| `PAYMENT_MODE` | `simulation` | **Safety: never change to `live`** |
| `ALLOW_REAL_PAYMENTS` | `false` | **Safety: never change to `true`** |
| `PAYMENT_PROVIDER` | `simulator` | |
| `LIGHTGBM_MODEL_PATH` | `models/artifacts/lightgbm_recovery_model.joblib` | |
| `LLM_PROVIDER` | `deterministic` or `cloudflare` | |
| `REASONING_MODEL` | `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` | |
| `LLM_TIMEOUT_SECONDS` | `30` | |
| `MAX_LLM_OUTPUT_TOKENS` | `512` | |
| `DATABASE_URL` | `postgresql+asyncpg://...` | From Supabase (Secret) |
| `CLOUDFLARE_ACCOUNT_ID` | Your account ID | From Cloudflare |
| `CLOUDFLARE_API_TOKEN` | Your API token | **Secret** |
| `APP_SECRET_KEY` | (auto-generate) | |
| `JWT_SECRET` | (auto-generate) | |
| `CORS_ORIGINS` | `["*"]` | |

---

## Step 4: LightGBM Model Artifact

The model artifact (`models/artifacts/lightgbm_recovery_model.joblib`) is excluded from git by `.gitignore`. For deployment, you have two options:

### Option A: Include in Build
Remove the `models/artifacts/` line from `.gitignore` and commit the artifact:
```bash
git add -f models/artifacts/lightgbm_recovery_model.joblib
git commit -m "Add trained LightGBM model artifact"
```

### Option B: Train During Build
Add training to the Render build command:
```
pip install --no-cache-dir -r backend/requirements.txt && python scripts/train_lightgbm.py
```

### Fallback
If the model artifact is unavailable, the app automatically falls back to deterministic heuristic scoring. All functionality continues to work.

---

## Step 5: Verify Deployment

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Basic liveness check |
| `GET /ready` | Readiness with ML, reasoning, DB status |
| `GET /api/v1/health` | Detailed component health |

---

## Local Development (No Cloud Required)

The entire system runs locally without any cloud services:

```bash
# Create venv
python -m venv .venv
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Linux/Mac

# Install dependencies
pip install -r backend/requirements.txt

# Train model (optional)
python scripts/train_lightgbm.py

# Run server
cd backend && uvicorn app.main:app --reload
```

Default configuration uses SQLite, deterministic LLM provider, and simulator payment provider.

---

## Safety Invariants

These invariants are enforced in **all** deployment configurations:

- `ALLOW_REAL_PAYMENTS=false` — real payment processing is disabled
- `PAYMENT_MODE=simulation` — synthetic payment simulation only
- `PAYMENT_PROVIDER=simulator` — no live payment gateway
- All LLM output is treated as untrusted and validated by Pydantic schemas
- Policy engine decisions are deterministic, not influenced by LLM output
- Recovery verification uses authoritative provider state, not LLM claims

---

## Cost Monitoring

| Service | Where to Check |
| --- | --- |
| Render | Dashboard → Usage |
| Supabase | Dashboard → Settings → Usage |
| Cloudflare | Dashboard → AI → Usage |

> [!CAUTION]
> None of these services offer hard spending caps on free tiers. Monitor usage to avoid surprise charges if you add paid features.

---

## Teardown

To completely remove the deployment and ensure zero future charges:

1. **Render:** Delete the web service
2. **Supabase:** Pause or delete the project
3. **Cloudflare:** Revoke the API token

---

## Disclaimer

> Free tier terms and quotas are subject to change by providers. This guide was verified as of October 2026. Always check the provider's current pricing page before deploying. The authors assume no responsibility for unexpected charges.
