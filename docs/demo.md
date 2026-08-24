# 5-Minute Demo Guide

## Setup (before demo)

```bash
docker compose up --build
make migrate
make demo   # seeds 20 deterministic cases
```

Open http://localhost:3000

## Demo script

### 0:00–0:30 — The problem

- Show Overview page
- Point to "Revenue at Risk" — real number from seeded data
- "Three types of revenue leakage: failed payments, failed subscriptions, checkout abandonment"
- "All numbers you see are computed from real simulation runs — nothing is hard-coded"

### 0:30–1:00 — Batch overview

- Show the 3-scenario breakdown cards
- Show "Policy Violations: 0" — "Zero. By design. The policy engine blocks anything unauthorized."
- Show Recovery by Failure Reason chart

### 1:00–2:00 — Live case: Failed Payment recovered

Navigate to Recovery Cases → filter by RECOVERED + FAILED_PAYMENT
- Pick the "Retry #2 success" case (Case 1 from seed)
- Show: amount at risk → AI diagnosis → strategy → Policy: APPROVED → execution → RECOVERED
- Show audit timeline: CASE_CREATED → DIAGNOSIS_COMPLETED → POLICY_APPROVED → RETRY_EXECUTED → REVENUE_RECOVERED
- "₹X recovered. Verified by the simulator — not predicted by the AI."

### 2:00–2:30 — Live case: Checkout Abandonment recovered

Navigate to CHECKOUT_ABANDONMENT + RECOVERED
- Pick "Recovery message worked" case (Case 8 from seed)
- Show: checkout abandoned → recovery message → policy approved → customer resumed → payment success
- "Same pipeline. Same policy gate. Different scenario."

### 2:30–3:15 — Audit trail

- Navigate to Audit Trail
- Filter by REVENUE_RECOVERED — show only verified recoveries
- "Every event has a timestamp, actor, policy version. This is the audit trail judges can verify."
- Show POLICY_DENIED events — "Every blocked action is also recorded"

### 3:15–4:00 — Safety demo (the important part)

**4th retry blocked:**
- Navigate to Case 12 (4th retry DENIED)
- Show policy_decision: ESCALATE, reason: MAX_RETRIES_EXCEEDED
- "The LLM proposed a retry. The policy engine blocked it. The executor did not fire."

**Opted-out customer blocked:**
- Navigate to Case 13 (opted-out DENIED)  
- Show: customer opted out → DENIED → stopped
- "No override path. Hard constraint."

**Checkout message limit:**
- Navigate to Case 9 (checkout opted-out DENIED)
- "Same guarantee for checkout recovery messages."

### 4:00–5:00 — Batch comparison

- Navigate to Simulation page
- Show completed AI run and Baseline run
- Navigate to Analytics → Baseline vs AI chart
- "AI recovers more revenue. But more importantly — zero policy violations in both runs."
- "The improvement is real — computed from identical datasets with the same failure distribution."

## Key talking points

1. **Not a chatbot** — it executes recovery actions and verifies outcomes
2. **Policy is deterministic** — the LLM cannot override it under any framing
3. **Recovery is verified** — the number you see is confirmed by the simulator, not predicted
4. **Audit trail is complete** — every decision, every policy version, every blocked action
5. **Three scenarios** — failed payments, failed subscriptions, checkout abandonment — same architecture
