# Definition of Done — §23 Verification Checklist

Run through this before declaring the project complete.

## Core functionality

- [ ] Payment simulator works (run: `pytest simulator/tests/ -v`)
- [ ] Database migrations apply cleanly (`make migrate`)
- [ ] Failed payment event creates a recovery case (`POST /events/payment-failed`)
- [ ] Agent diagnoses the failure (check `diagnosis` field in case detail)
- [ ] Agent proposes a recovery strategy (check `strategy` field)
- [ ] Policy engine validates the strategy (check `policy_result`)
- [ ] Unauthorized actions are blocked — proven by red-team test rt01
- [ ] Authorized actions execute through tools (GATEWAY_TEMPORARY test recovers)
- [ ] Payment simulator returns realistic results (deterministic per seed)
- [ ] Recovery verifier confirms success from authoritative state (not LLM output)
- [ ] Successful recovery stops the agent — no further actions (rt08)
- [ ] Failed recovery can re-plan within policy (replan_count < max_replans)
- [ ] Escalation works end-to-end (high-value test rt03)
- [ ] Audit trail records every important event (check `/api/v1/audit`)
- [ ] Revenue recovered computed from verified transactions only

## Batch simulation

- [ ] Batch simulation works (`POST /simulation/run`)
- [ ] Baseline comparison works (run AI + baseline, compare via `/metrics/baseline-comparison`)
- [ ] Dashboard uses only real backend data (no hard-coded values anywhere)

## Safety / red-team

- [ ] All 25 red-team tests pass (`pytest tests/redteam/ -v`)
- [ ] E2E tests pass (`pytest tests/integration/ -v`)

## Deployment / config

- [ ] No secrets hard-coded — `.env.example` present, `.env` in `.gitignore`
- [ ] README is accurate and app actually runs from it
- [ ] Seeded demo dataset works deterministically (`make demo`)
- [ ] App runs locally via `docker compose up`
- [ ] No fabricated / fake metrics anywhere in the UI

## Two mandatory E2E checks (run explicitly)

**Check 1 — Happy path:**
```
synthetic failed payment
  → risk detection
  → context building
  → diagnosis (fallback mode)
  → strategy
  → policy validation: APPROVED
  → tool execution
  → payment simulation
  → verification: RECOVERED
  → state: RECOVERED + STOPPED
  → audit trail: CASE_CREATED → ... → REVENUE_RECOVERED
  → dashboard metric updates
```

**Check 2 — Policy blocks unauthorized action:**
```
AI proposes 4th retry (retry_count=3)
  → policy engine: ESCALATE (MAX_RETRIES_EXCEEDED)
  → executor: does NOT execute
  → audit trail: POLICY_ESCALATE recorded
```
