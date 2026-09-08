# Testing Guide

## Test suites

| Suite | Location | What it tests | Run without Docker? |
|---|---|---|---|
| Policy Engine | `policies/tests/` | All 31 authorization rules | ✅ Yes |
| Simulator | `simulator/tests/` | Payment outcomes, verifier, generators | ✅ Yes |
| Agent | `agents/tests/` | LangGraph pipeline, MockProvider, all scenarios | ✅ Yes |
| Red-Team | `tests/redteam/` | 25 mandatory safety tests | ✅ Yes |
| Integration | `tests/integration/` | End-to-end recovery pipeline | ✅ Yes |
| Backend Unit | `backend/tests/unit/` | Schema validation, scoring | ✅ Yes |
| Frontend Unit | `frontend/tests/` | Component rendering | ✅ Yes (npm) |
| E2E | `tests/e2e/` | Dashboard UI flows | ❌ Needs Docker |

## Running locally (no Docker)

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run everything except E2E
python -m pytest policies/tests/ simulator/tests/ agents/tests/ \
                 tests/redteam/ tests/integration/ backend/tests/unit/ \
                 -v --tb=short

# Frontend
cd frontend && npm install && npm run test -- --run
```

## Running in Docker

```bash
make test          # full backend suite
make test-redteam  # red-team only
make test-frontend # frontend unit tests
```

## Red-team tests (mandatory — all 25 must pass)

| # | Test | What it proves |
|---|---|---|
| rt01 | 4th retry blocked | LLM cannot bypass retry limit |
| rt02 | Opted-out → no communication | Hard opt-out constraint |
| rt03 | ₹100K → escalate | Auto-limit enforced |
| rt04 | Malicious metadata → no effect | Prompt injection defense |
| rt05 | LLM cannot modify policy | Policy immutability |
| rt06 | Duplicate event → idempotency | No double-processing |
| rt07 | Payment succeeded → STOP | Success state wins |
| rt08 | Already RECOVERED → no further actions | Recovery idempotency |
| rt09 | Invalid amount → safe stop | Input validation |
| rt10 | Policy engine down → fail closed | Fail-closed guarantee |
| rt11 | Malformed LLM JSON → fallback | Never execute unvalidated output |
| rt12 | No policy approval → action blocked | Executor gate |
| rt13 | Action replay → blocked | Action idempotency |
| rt14 | UNKNOWN failure → escalate | No fabricated diagnosis |
| rt15 | Communication limit → blocked | Message cap enforced |
| rt16 | Retry interval → blocked | Timing constraint |
| rt17 | Negative amount → rejected | Schema validation |
| rt18 | UNKNOWN → human review | Low-confidence escalation |
| rt19 | Audit write failure → raises | No silent data loss |
| rt20 | Suspicious activity → escalate | Automation safety halt |
| rt21 | Checkout opted-out → blocked | Checkout opt-out constraint |
| rt22 | Checkout message limit → blocked | Checkout message cap |
| rt23 | Checkout timeout not reached → blocked | Timing gate |
| rt24 | Checkout amount too low → blocked | Minimum amount gate |
| rt25 | Checkout completed → idempotency | Checkout recovery idempotency |

## E2E checks (from §23 spec)

**Check 1 — Happy path:**
```bash
python -m pytest tests/integration/test_e2e_recovery.py::test_e2e_gateway_failure_recovers -v
```

**Check 2 — Policy blocks unauthorized action:**
```bash
python -m pytest tests/integration/test_e2e_recovery.py::test_e2e_4th_retry_policy_denied -v
```

## Agent testing notes

All agent tests use `MockProvider` (no OpenAI API key needed).
The mock produces deterministic outputs keyed on `failure_reason`.
LLM mode tests require `LLM_PROVIDER=openai` and `OPENAI_API_KEY` set.
