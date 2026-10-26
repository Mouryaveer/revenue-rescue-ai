"""
Unit tests for leakage auditor and temporal purity verification.
"""

import pandas as pd

from pipeline.leakage_audit import LeakageAuditor


def test_leakage_audit_clean_data():
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C1", "C2"],
            "occurred_at": [
                "2026-01-01T00:00:00Z",
                "2026-02-01T00:00:00Z",
                "2026-03-01T00:00:00Z",
            ],
            "chrono_split": ["train", "validation", "test"],
            "hours_since_prev_event": [float("nan"), 744.0, float("nan")],
            "feature_a": [1, 2, 3],
        }
    )
    report = LeakageAuditor.audit_features_and_splits(
        df=df,
        feature_columns=["feature_a"],
        timestamp_col="occurred_at",
        split_col="chrono_split",
        customer_id_col="customer_id",
    )
    assert report.is_leakage_free is True
    assert len(report.violations) == 0


def test_leakage_audit_target_in_features():
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C2"],
            "occurred_at": ["2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z"],
            "chrono_split": ["train", "test"],
            "recovered": [True, False],
        }
    )
    report = LeakageAuditor.audit_features_and_splits(
        df=df,
        feature_columns=["recovered"],
        timestamp_col="occurred_at",
        split_col="chrono_split",
    )
    assert report.is_leakage_free is False
    assert any("Forbidden target" in v for v in report.violations)


def test_leakage_audit_temporal_split_overlap():
    # Train occurs after validation start
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C2"],
            "occurred_at": ["2026-05-01T00:00:00Z", "2026-03-01T00:00:00Z"],
            "chrono_split": ["train", "validation"],
        }
    )
    report = LeakageAuditor.audit_features_and_splits(
        df=df,
        feature_columns=[],
        timestamp_col="occurred_at",
        split_col="chrono_split",
    )
    assert report.is_leakage_free is False
    assert report.train_val_temporal_overlap is True


def test_leakage_audit_negative_time_delta():
    df = pd.DataFrame(
        {
            "customer_id": ["C1", "C1"],
            "occurred_at": ["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"],
            "chrono_split": ["train", "train"],
            "hours_since_prev_event": [float("nan"), -5.0],
        }
    )
    report = LeakageAuditor.audit_features_and_splits(
        df=df,
        feature_columns=[],
        timestamp_col="occurred_at",
        split_col="chrono_split",
    )
    assert report.is_leakage_free is False
    assert report.negative_time_deltas == 1
