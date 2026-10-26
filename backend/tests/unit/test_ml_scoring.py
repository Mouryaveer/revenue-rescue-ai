"""
Unit tests for LightGBM MLScoringService.

Verifies:
- Model artifact loading and version checks.
- Output probability bounds [0.0, 1.0].
- Expected economic value unit consistency (paise / INR) and explicit cost assumptions.
- Graceful deterministic fallback when model artifact is missing or corrupted.
- Input validation: feature schema order, categorical imputation, numeric range limits.
- Clear separation between ML recovery probability and rule-based retry timing recommendations.
"""

import math

from app.services.ml_scoring_service import FEATURE_COLUMNS, MLScoringService
from app.services.scoring_service import RecoveryScoringService


def test_ml_scoring_service_loads_artifact():
    scorer = MLScoringService()
    # If the artifact was generated, it should be trained and have version rr-lightgbm.v1
    assert scorer.model_version in ("rr-lightgbm.v1", "not_trained_fallback")
    if scorer.is_trained:
        assert scorer._model is not None
        assert scorer._preprocessor is not None


def test_ml_scoring_predict_probability_bounds():
    scorer = MLScoringService()
    features = {
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "payment_method": "card",
        "device_type": "web",
        "country": "IN",
        "amount_paise": 499900,
        "retry_count": 0,
        "event_hour_utc": 14,
        "event_dayofweek_utc": 2,
        "event_month_utc": 5,
    }
    prob = scorer.predict_probability(features)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0


def test_ml_scoring_missing_artifact_fallback():
    # Pass non-existent path
    scorer = MLScoringService(model_path="non_existent_model_dir/fake_model.joblib")
    assert scorer.is_trained is False
    assert scorer.model_version in ("not_trained_fallback", "none")

    features = {
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "GATEWAY_TEMPORARY",
        "amount_paise": 199900,
        "retry_count": 0,
    }
    prob = scorer.predict_probability(features)
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0
    # Should equal fallback heuristic score / 100.0
    expected_heuristic = RecoveryScoringService().score("GATEWAY_TEMPORARY", 199900, 0) / 100.0
    assert math.isclose(prob, round(expected_heuristic, 4), abs_tol=0.01)


def test_expected_value_unit_consistency():
    scorer = MLScoringService()
    amount_paise = 100000  # ₹1,000.00
    prob = 0.70
    cost_paise = 500  # ₹5.00

    # EV = (0.70 * 100,000) - 500 = 70,000 - 500 = 69,500 paise (₹695.00)
    ev_paise = scorer.calculate_expected_value(
        prob, amount_paise, intervention_cost_paise=cost_paise
    )
    assert ev_paise == 69500.0

    # Negative EV test: very low prob on small amount
    low_prob = 0.02
    small_amount = 10000  # ₹100.00
    # EV = (0.02 * 10,000) - 500 = 200 - 500 = -300 paise
    ev_negative = scorer.calculate_expected_value(
        low_prob, small_amount, intervention_cost_paise=cost_paise
    )
    assert ev_negative == -300.0


def test_feature_preparation_sanitizes_malformed_inputs():
    scorer = MLScoringService()
    malformed = {
        "event_type": None,
        "failure_reason": "UNKNOWN_REASON_CODE",
        "payment_method": 12345,
        "amount_paise": -5000,  # negative amount should clamp to 0
        "retry_count": "invalid_int",  # invalid should clamp to 0
        "event_hour_utc": 99,  # should wrap or clamp modulo 24
    }
    df = scorer._prepare_feature_row(malformed)
    assert list(df.columns) == FEATURE_COLUMNS
    assert df["amount_paise"].iloc[0] == 0
    assert df["retry_count"].iloc[0] == 0
    assert 0 <= df["event_hour_utc"].iloc[0] < 24


def test_rule_based_retry_delay_is_deterministic_and_labelled():
    delays = [
        MLScoringService.get_rule_based_retry_delay_hours("GATEWAY_TEMPORARY", 0),
        MLScoringService.get_rule_based_retry_delay_hours("INSUFFICIENT_FUNDS", 0),
        MLScoringService.get_rule_based_retry_delay_hours("INSUFFICIENT_FUNDS", 1),
        MLScoringService.get_rule_based_retry_delay_hours("BANK_DECLINE", 0),
        MLScoringService.get_rule_based_retry_delay_hours("EXPIRED_METHOD", 0),
    ]
    assert delays == [2, 24, 48, 48, 0]


def test_quantitative_evidence_packet():
    scorer = MLScoringService()
    features = {
        "event_type": "FAILED_PAYMENT",
        "failure_reason": "INSUFFICIENT_FUNDS",
        "amount_paise": 299900,
        "retry_count": 0,
    }
    evidence = scorer.get_quantitative_evidence(features)
    assert "recovery_probability" in evidence
    assert "recovery_score" in evidence
    assert "expected_value_paise" in evidence
    assert "expected_value_inr" in evidence
    assert "rule_based_retry_delay_hours" in evidence
    assert "cost_assumption_basis" in evidence
    assert "scoring_mode" in evidence
    assert 0.0 <= evidence["recovery_probability"] <= 1.0
