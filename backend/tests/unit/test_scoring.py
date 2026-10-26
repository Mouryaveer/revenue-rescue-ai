"""
Unit tests for RecoveryScoringService.
"""

from app.services.scoring_service import RecoveryScoringService


def scorer():
    return RecoveryScoringService()


def test_score_returns_0_to_100():
    s = scorer()
    for reason in ["INSUFFICIENT_FUNDS", "GATEWAY_TEMPORARY", "EXPIRED_METHOD", "UNKNOWN"]:
        score = s.score(failure_reason=reason, amount_paise=299900, retry_count=0)
        assert 0 <= score <= 100, f"Score out of range for {reason}: {score}"


def test_gateway_temporary_scores_higher_than_unknown():
    s = scorer()
    gw = s.score("GATEWAY_TEMPORARY", 299900, 0)
    uk = s.score("UNKNOWN", 299900, 0)
    assert gw > uk


def test_retry_count_reduces_score():
    s = scorer()
    s0 = s.score("INSUFFICIENT_FUNDS", 299900, 0)
    s3 = s.score("INSUFFICIENT_FUNDS", 299900, 3)
    assert s0 > s3


def test_economic_value_positive_when_likely_recovery():
    s = scorer()
    ev = s.economic_value(probability_of_recovery=0.8, amount_paise=500000)
    assert ev > 0


def test_economic_value_negative_when_unlikely():
    s = scorer()
    ev = s.economic_value(probability_of_recovery=0.001, amount_paise=100)
    assert ev < 0
