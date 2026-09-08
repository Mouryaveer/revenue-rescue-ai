# Payment Simulator

## Overview

RevenueRescue AI uses a fully self-contained simulated payment ecosystem.
**No real gateways. No real credentials. No real card data. Ever.**

## Architecture

```
CustomerGenerator ──► SyntheticCustomer[]
PaymentEventGenerator ──► PaymentEvent[]  (FAILED_PAYMENT | FAILED_SUBSCRIPTION | CHECKOUT_ABANDONED)
          │
          ▼
PaymentSimulator.execute_retry()
    → SimulatedPaymentResult (SUCCESS | FAILED)
          │
          ▼
RecoveryVerifier.verify_payment_attempt()
    → VerificationResult (RECOVERED | FAILED | ALREADY_RECOVERED)
```

## Reproducibility

Every simulation uses a `seed: int` parameter.
Same seed + same config = identical results every run.

```python
sim = PaymentSimulator(seed=42)
result = sim.execute_retry(case_id="c1", ...)
# Same result every time with seed=42
```

Simulation metadata stored in `simulation_runs` table:
```json
{
  "simulation_id": "SIM-2026-001",
  "seed": 42,
  "policy_version": "1.0.0",
  "agent_version": "0.1.0",
  "dataset_version": "1.0.0"
}
```

## Failure probability tables

Retry success probabilities by failure reason and retry number:

| Failure reason | Retry 1 | Retry 2 | Retry 3 |
|---|---|---|---|
| INSUFFICIENT_FUNDS | 40% | 60% | 75% |
| GATEWAY_TEMPORARY | 70% | 90% | 95% |
| BANK_DECLINE | 25% | 45% | 55% |
| EXPIRED_METHOD | 0% | 0% | 0% |
| AUTH_FAILURE | 20% | 35% | 45% |
| MANDATE_FAILURE | 30% | 50% | 65% |
| SUBSCRIPTION_GRACE | 40% | 55% | 70% |
| UNKNOWN | 10% | 15% | 20% |

Customer segment modifiers: enterprise ×1.25, premium ×1.15, standard ×1.0, at_risk ×0.75.

## Checkout abandonment simulation

```
send_checkout_recovery()
    → customer resumes? (probability by segment)
        YES → payment_attempt → SUCCESS/FAILED
        NO  → no payment, case remains open
```

Resume probabilities: enterprise 65%, premium 50%, standard 35%, at_risk 20%.
Second message: 50% of base probability.

## Synthetic data guarantee

- `Customer.is_synthetic = True` always
- `Transaction.is_synthetic = True` always  
- `CheckoutSession.is_synthetic = True` always
- No real email addresses, phone numbers, card data, or banking credentials
- UI always shows `⚠ SYNTHETIC DATA` badge
- All seed data labeled `[SYNTHETIC]` in audit trail

## Baseline comparison

`BaselineSimulator` runs the same events with a fixed retry-once strategy:

```python
baseline = BaselineSimulator(seed=42)
results = baseline.run_batch(events)
metrics = BaselineSimulator.compute_metrics(results)
# {"mode": "BASELINE", "recovery_rate_pct": X, ...}
```

Same dataset → fair comparison with AI recovery.
