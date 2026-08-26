"""
Recovery scoring service — deterministic heuristic, no ML.
Structured so a model could replace it later without changing the interface.

RecoveryScore = w_a*amount_score + w_h*history_score + w_f*failure_recoverability
                + w_rp*previous_retry_success + w_e*engagement - w_x*retry_penalty
Normalized to 0–100.
"""

from __future__ import annotations

FAILURE_RECOVERABILITY = {
    "INSUFFICIENT_FUNDS": 0.70,
    "EXPIRED_METHOD": 0.55,
    "GATEWAY_TEMPORARY": 0.85,
    "BANK_DECLINE": 0.50,
    "AUTH_FAILURE": 0.45,
    "MANDATE_FAILURE": 0.60,
    "SUBSCRIPTION_GRACE": 0.65,
    "CHECKOUT_ABANDONED": 0.50,
    "UNKNOWN": 0.15,
}

# Weights
W_AMOUNT = 0.20
W_HISTORY = 0.15
W_FAILURE = 0.35
W_RETRY = 0.15
W_ENGAGEMENT = 0.15
W_RETRY_PEN = 0.10


class RecoveryScoringService:
    def score(
        self,
        failure_reason: str,
        amount_paise: int,
        retry_count: int,
        success_rate: float = 0.85,
        engagement_score: float = 0.5,
    ) -> float:
        # Amount score: higher amounts get slightly higher priority (log scale, capped)
        import math

        amount_score = min(math.log10(max(amount_paise, 1)) / 7.0, 1.0)

        history_score = success_rate  # historical success rate 0–1
        failure_score = FAILURE_RECOVERABILITY.get(failure_reason, 0.20)
        retry_success = max(0.0, 1.0 - (retry_count * 0.25))  # decreases with retries
        retry_penalty = min(retry_count * 0.10, 0.40)

        raw = (
            W_AMOUNT * amount_score
            + W_HISTORY * history_score
            + W_FAILURE * failure_score
            + W_RETRY * retry_success
            + W_ENGAGEMENT * engagement_score
            - W_RETRY_PEN * retry_penalty
        )
        return round(max(0.0, min(raw * 100, 100.0)), 2)

    def economic_value(
        self,
        probability_of_recovery: float,
        amount_paise: int,
        intervention_cost_paise: int = 500,
    ) -> float:
        """
        EV(action) = P(recovery) * amount - intervention_cost
        Positive EV is necessary but NOT sufficient — policy always takes precedence.
        """
        return (probability_of_recovery * amount_paise) - intervention_cost_paise
