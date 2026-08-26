# Troubleshooting

## App won't start

**Symptom:** `docker compose up` fails  
**Check:**
```bash
docker compose logs postgres   # Is Postgres healthy?
docker compose logs backend    # Import errors? Missing env vars?
```
**Common causes:**
- `.env` not created from `.env.example`
- Postgres port 5432 already in use — change `ports` in docker-compose.yml
- Missing `OPENAI_API_KEY` — set `LLM_PROVIDER=mock` in `.env` to skip

---

## Migrations fail

**Symptom:** `alembic upgrade head` fails  
**Check:**
```bash
docker compose exec backend alembic current   # What version is DB at?
docker compose exec backend alembic history   # What migrations exist?
```
**Fix:** Make sure `DATABASE_URL` in `.env` points to the running Postgres container.

---

## Tests fail with `ModuleNotFoundError`

**Symptom:** `No module named 'asyncpg'` or similar  
**Cause:** Running tests locally without Docker, asyncpg not installed  
**Fix:**
```bash
pip install asyncpg     # or
pip install -r backend/requirements.txt
```
Most tests (policy engine, agent, simulator, red-team) run fine without asyncpg.
Only DB-dependent tests need it.

---

## LangChain Pydantic v1 warning

**Symptom:** `UserWarning: Core Pydantic V1 functionality isn't compatible with Python 3.14`  
**Cause:** LangChain internally uses Pydantic v1 compat layer, not compatible with Python 3.14+  
**Impact:** None — warning only, tests pass, agent runs correctly  
**Fix:** Pin Python to 3.12 in Docker (already done in `backend/Dockerfile`)

---

## Agent always uses fallback mode

**Symptom:** Mode indicator shows `FALLBACK MODE` even with API key set  
**Check:** Is `LLM_PROVIDER=openai` set in `.env`?  
**Check:** Is `OPENAI_API_KEY` set and valid?  
**Note:** Fallback mode is fully functional — the system works correctly without OpenAI. This is by design.

---

## Dashboard shows empty data

**Symptom:** All KPIs show 0  
**Fix:** Run `make demo` to seed the demo dataset  
**Check:** Is backend running? Check `http://localhost:8000/health`  
**Check:** Is `NEXT_PUBLIC_API_URL` pointing to the right backend?

---

## Policy violations > 0

**Symptom:** Dashboard shows policy_violations > 0  
**This should never happen** — it means an action executed without policy approval  
**Check:** Review audit trail for `UNAUTHORIZED_ACTION_ATTEMPT` events  
**Check:** Is the Policy Engine returning correct responses?

---

## Simulation hangs

**Symptom:** Simulation run stays at RUNNING indefinitely  
**Check:** Is the Celery worker running?
```bash
docker compose logs worker
```
**Fix:** The simulation service falls back to inline execution for small runs. For large runs, Redis + Celery worker must be running.

---

## `make` commands not found on Windows

**Cause:** GNU Make is not installed on Windows by default  
**Fix options:**
1. Install via `choco install make` (Chocolatey)
2. Install via `winget install GnuWin32.Make`
3. Run commands directly: `docker compose up --build` instead of `make up`
