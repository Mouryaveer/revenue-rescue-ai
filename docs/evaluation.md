# Evaluation — Batch Experiment Methodology

## Primary metric

```
Recovery Rate = Verified Recovered Revenue / Total At-Risk Revenue × 100
```

**Not** predicted recovery. **Not** LLM-claimed recovery.
Only revenue confirmed by `RecoveryVerifier` reading authoritative simulator state.

## Experiment design

Every batch run records:
- `simulation_id` — unique run identifier
- `random_seed` — for exact reproducibility
- `policy_version` — which policy config was used
- `agent_version` — which agent build was used
- `dataset_version` — which dataset generator config was used

This makes every result independently reproducible and auditable.

## AI vs Baseline comparison

Both runs use **identical** datasets and failure distributions:

```
Same seed → same customers → same failure events → same simulator
    ↓                               ↓
AI Agent                     Baseline (retry-once)
    ↓                               ↓
Recovery Rate A%             Recovery Rate B%
    ↓
Improvement = A% - B%
```

Dashboard never fabricates improvement — it computes A% - B% from real run data.

## Metrics computed per run

| Metric | How computed |
|---|---|
| Revenue at risk | Sum of `amount_at_risk_paise` for all cases in run |
| Revenue recovered | Sum of `amount_recovered_paise` where `is_recovered=True` |
| Recovery rate | recovered / at_risk × 100 |
| Total cases | COUNT recovery_cases in run |
| Recovered cases | COUNT where `is_recovered=True` |
| Escalated cases | COUNT where `status=ESCALATED` |
| Policy violations | COUNT where policy DENIED but action executed (should always be 0) |
| Avg recovery time | AVG time from `CASE_CREATED` to `REVENUE_RECOVERED` audit events |

## Experiment reproducibility checklist

Before reporting results:
- [ ] `random_seed` recorded
- [ ] `policy_version` recorded  
- [ ] `agent_version` recorded
- [ ] Both AI and baseline runs use same seed
- [ ] Results read from DB — not from LLM output
- [ ] `policy_violations = 0` confirmed
- [ ] Dashboard shows `SYNTHETIC DATA` label

## Interpreting results

- Higher recovery rate = AI recovers more revenue per ₹ at risk
- Lower escalation rate = fewer cases requiring human intervention
- Zero policy violations = safety boundary held throughout the run
- Avg recovery time = operational efficiency metric

**Important:** Recovery rate varies by seed because it depends on simulated customer behavior. Run multiple seeds and report the mean for production evaluation.
