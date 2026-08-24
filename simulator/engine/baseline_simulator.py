"""
Baseline simulator — fixed retry schedule, no AI diagnosis or strategy.
Runs against the same dataset as the AI agent for fair comparison.

Baseline strategy: retry every failed payment once after a fixed delay.
No context analysis, no customer history, no failure-reason diagnosis.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.engine.payment_simulator import PaymentSimulator, SimulatedOutcome
from simulator.engine.recovery_verifier import RecoveryVerifier, VerificationOutcome
from simulator.generators.payment_generator import PaymentEvent


@dataclass
class BaselineResult:
    event_id: str
    customer_id: str
    amount_paise: int
    failure_reason: str
    outcome: str          # RECOVERED | FAILED | SKIPPED
    amount_recovered: int
    retry_count: int


class BaselineSimulator:
    """
    Deterministic baseline: retry once, no intelligence.
    Used as the comparison baseline in batch experiments.
    Same dataset, same simulator, same failure distribution — only strategy differs.
    """

    def __init__(self, seed: int = 42) -> None:
        self._sim = PaymentSimulator(seed=seed)
        self._verifier = RecoveryVerifier()

    def run_batch(self, events: list[PaymentEvent]) -> list[BaselineResult]:
        results = []
        for event in events:
            result = self._process_event(event)
            results.append(result)
        return results

    def _process_event(self, event: PaymentEvent) -> BaselineResult:
        # Baseline: single retry attempt, no scheduling logic
        pay_result = self._sim.execute_retry(
            case_id=event.event_id,
            customer_id=event.customer_id,
            customer_segment=event.customer.segment,
            failure_reason=event.failure_reason,
            retry_number=1,
            amount_paise=event.amount_paise,
            currency=event.currency,
        )

        verification = self._verifier.verify_payment_attempt(
            case_id=event.event_id,
            payment_result=pay_result,
        )

        recovered = verification.outcome == VerificationOutcome.RECOVERED
        return BaselineResult(
            event_id=event.event_id,
            customer_id=event.customer_id,
            amount_paise=event.amount_paise,
            failure_reason=event.failure_reason,
            outcome="RECOVERED" if recovered else "FAILED",
            amount_recovered=verification.amount_recovered_paise,
            retry_count=1,
        )

    @staticmethod
    def compute_metrics(results: list[BaselineResult]) -> dict:
        total = len(results)
        recovered = [r for r in results if r.outcome == "RECOVERED"]
        total_at_risk = sum(r.amount_paise for r in results)
        total_recovered = sum(r.amount_recovered for r in recovered)

        return {
            "mode": "BASELINE",
            "total_events": total,
            "recovered_count": len(recovered),
            "failed_count": total - len(recovered),
            "total_at_risk_paise": total_at_risk,
            "total_recovered_paise": total_recovered,
            "recovery_rate_pct": round(
                (total_recovered / total_at_risk * 100) if total_at_risk > 0 else 0.0, 2
            ),
            "avg_retries": 1.0,  # baseline always does exactly 1 retry
            "escalations": 0,
            "policy_violations": 0,
            "note": "Fixed retry schedule — no diagnosis, no context",
        }
