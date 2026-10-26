"""
Leakage audit and point-in-time temporal verification module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass
class LeakageAuditReport:
    """Findings from leakage and point-in-time checks."""

    is_leakage_free: bool
    train_val_temporal_overlap: bool
    val_test_temporal_overlap: bool
    train_end_time: str
    val_start_time: str
    val_end_time: str
    test_start_time: str
    target_in_features: list[str]
    negative_time_deltas: int
    customer_overlap_splits: dict[str, int]
    violations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_leakage_free": self.is_leakage_free,
            "train_val_temporal_overlap": self.train_val_temporal_overlap,
            "val_test_temporal_overlap": self.val_test_temporal_overlap,
            "train_end_time": self.train_end_time,
            "val_start_time": self.val_start_time,
            "val_end_time": self.val_end_time,
            "test_start_time": self.test_start_time,
            "target_in_features": self.target_in_features,
            "negative_time_deltas": self.negative_time_deltas,
            "customer_overlap_splits": self.customer_overlap_splits,
            "violations": self.violations,
        }


class LeakageAuditor:
    """Verifies that features are point-in-time safe and splits maintain chronological purity."""

    FORBIDDEN_FEATURE_NAMES: set[str] = {
        "recovered",
        "verification_outcome",
        "verified_amount",
        "actual_recovery",
        "future_event",
    }

    @classmethod
    def audit_features_and_splits(
        cls,
        df: pd.DataFrame,
        feature_columns: list[str],
        timestamp_col: str = "occurred_at",
        split_col: str = "chrono_split",
        customer_id_col: str = "customer_id",
    ) -> LeakageAuditReport:
        violations: list[str] = []

        # 1. Check for target or post-event leakage in candidate features
        target_in_features = [
            f for f in feature_columns if f.lower() in cls.FORBIDDEN_FEATURE_NAMES
        ]
        if target_in_features:
            violations.append(
                f"Forbidden target/post-outcome features present: {target_in_features}"
            )

        # Ensure timestamps are parsed
        df_ts = pd.to_datetime(df[timestamp_col], errors="coerce", utc=True)
        if df_ts.isna().any():
            violations.append(
                "Dataframe contains unparseable timestamps; cannot verify temporal ordering"
            )

        # 2. Check chronological split boundaries
        train_mask = df[split_col] == "train"
        val_mask = df[split_col] == "validation"
        test_mask = df[split_col] == "test"

        train_max = df_ts[train_mask].max() if train_mask.any() else None
        val_min = df_ts[val_mask].min() if val_mask.any() else None
        val_max = df_ts[val_mask].max() if val_mask.any() else None
        test_min = df_ts[test_mask].min() if test_mask.any() else None

        train_val_overlap = False
        if train_max is not None and val_min is not None:
            if train_max > val_min:
                train_val_overlap = True
                violations.append(
                    f"Train and Validation splits temporally overlap! (train max: {train_max}, val min: {val_min})"
                )

        val_test_overlap = False
        if val_max is not None and test_min is not None:
            if val_max > test_min:
                val_test_overlap = True
                violations.append(
                    f"Validation and Test splits temporally overlap! (val max: {val_max}, test min: {test_min})"
                )

        # 3. Check customer history sequencing (negative time deltas)
        negative_deltas = 0
        if "hours_since_prev_event" in df.columns:
            neg_mask = df["hours_since_prev_event"] < 0
            negative_deltas = int(neg_mask.sum())
            if negative_deltas > 0:
                violations.append(
                    f"Found {negative_deltas} events with negative hours_since_prev_event (future event leakage)"
                )

        # 4. Customer overlap between splits (for reporting)
        cust_train = set(df[train_mask][customer_id_col].unique()) if train_mask.any() else set()
        cust_val = set(df[val_mask][customer_id_col].unique()) if val_mask.any() else set()
        cust_test = set(df[test_mask][customer_id_col].unique()) if test_mask.any() else set()

        overlap_counts = {
            "train_val_customer_overlap": len(cust_train.intersection(cust_val)),
            "train_test_customer_overlap": len(cust_train.intersection(cust_test)),
            "val_test_customer_overlap": len(cust_val.intersection(cust_test)),
        }

        is_leakage_free = len(violations) == 0

        return LeakageAuditReport(
            is_leakage_free=is_leakage_free,
            train_val_temporal_overlap=train_val_overlap,
            val_test_temporal_overlap=val_test_overlap,
            train_end_time=str(train_max),
            val_start_time=str(val_min),
            val_end_time=str(val_max),
            test_start_time=str(test_min),
            target_in_features=target_in_features,
            negative_time_deltas=negative_deltas,
            customer_overlap_splits=overlap_counts,
            violations=violations,
        )
