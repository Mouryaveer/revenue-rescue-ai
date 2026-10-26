"""
Schema definitions and validation utilities for RevenueRescue AI datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

VALID_EVENT_TYPES: set[str] = {
    "FAILED_PAYMENT",
    "FAILED_SUBSCRIPTION",
    "CHECKOUT_ABANDONMENT",
    "CHECKOUT_ABANDONED",
}

VALID_FAILURE_REASONS: set[str] = {
    "INSUFFICIENT_FUNDS",
    "BANK_DECLINE",
    "AUTH_FAILURE",
    "GATEWAY_TEMPORARY",
    "EXPIRED_METHOD",
    "MANDATE_FAILURE",
    "SUBSCRIPTION_GRACE",
    "CHECKOUT_ABANDONED",
    "UNKNOWN",
}

VALID_SPLITS: set[str] = {"train", "validation", "test"}

REQUIRED_RAW_COLUMNS: list[str] = [
    "schema_version",
    "event_id",
    "event_type",
    "customer_id",
    "amount_paise",
    "currency",
    "failure_reason",
    "occurred_at",
    "payment_method",
    "device_type",
    "country",
    "retry_count",
    "recovered",
    "is_synthetic",
    "split",
]


@dataclass
class ValidationReport:
    """Detailed summary of data quality validation results."""

    is_valid: bool
    total_rows: int
    unique_events: int
    unique_customers: int
    missing_counts: dict[str, int]
    invalid_event_types: list[str]
    invalid_failure_reasons: list[str]
    invalid_amounts: int
    unparseable_timestamps: int
    split_distribution: dict[str, int]
    target_distribution: dict[str, int]
    errors: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "total_rows": self.total_rows,
            "unique_events": self.unique_events,
            "unique_customers": self.unique_customers,
            "missing_counts": self.missing_counts,
            "invalid_event_types": self.invalid_event_types,
            "invalid_failure_reasons": self.invalid_failure_reasons,
            "invalid_amounts": self.invalid_amounts,
            "unparseable_timestamps": self.unparseable_timestamps,
            "split_distribution": self.split_distribution,
            "target_distribution": self.target_distribution,
            "errors": self.errors,
        }


class EventSchema:
    """Specification of expected columns and types."""

    REQUIRED_COLUMNS = REQUIRED_RAW_COLUMNS
    EVENT_TYPES = VALID_EVENT_TYPES
    FAILURE_REASONS = VALID_FAILURE_REASONS
    SPLITS = VALID_SPLITS


class DataValidator:
    """Validates raw event data integrity, schema consistency, and domain invariants."""

    @staticmethod
    def validate_dataframe(df: pd.DataFrame) -> ValidationReport:
        errors: list[str] = []

        # 1. Required columns check
        missing_cols = [c for c in REQUIRED_RAW_COLUMNS if c not in df.columns]
        if missing_cols:
            errors.append(f"Missing required columns: {missing_cols}")
            return ValidationReport(
                is_valid=False,
                total_rows=len(df),
                unique_events=0,
                unique_customers=0,
                missing_counts={},
                invalid_event_types=[],
                invalid_failure_reasons=[],
                invalid_amounts=0,
                unparseable_timestamps=0,
                split_distribution={},
                target_distribution={},
                errors=errors,
            )

        total_rows = len(df)
        unique_events = int(df["event_id"].nunique())
        unique_customers = int(df["customer_id"].nunique())

        if unique_events != total_rows:
            errors.append(f"Duplicate event_ids detected: {total_rows - unique_events} duplicates")

        # 2. Missing values per column
        missing_counts = {str(col): int(df[col].isna().sum()) for col in df.columns}
        for col, cnt in missing_counts.items():
            if cnt > 0 and col in REQUIRED_RAW_COLUMNS:
                errors.append(f"Column '{col}' has {cnt} missing values")

        # 3. Categorical validation
        raw_event_types = set(df["event_type"].dropna().unique())
        invalid_event_types = sorted(raw_event_types - VALID_EVENT_TYPES)
        if invalid_event_types:
            errors.append(f"Invalid event types found: {invalid_event_types}")

        raw_reasons = set(df["failure_reason"].dropna().unique())
        invalid_reasons = sorted(raw_reasons - VALID_FAILURE_REASONS)
        if invalid_reasons:
            errors.append(f"Invalid failure reasons found: {invalid_reasons}")

        # 4. Numeric invariants
        invalid_amounts = int((df["amount_paise"] <= 0).sum())
        if invalid_amounts > 0:
            errors.append(f"Found {invalid_amounts} rows with non-positive amount_paise")

        # 5. Timestamp parsing
        parsed_ts = pd.to_datetime(df["occurred_at"], errors="coerce", utc=True)
        unparseable_timestamps = int(parsed_ts.isna().sum())
        if unparseable_timestamps > 0:
            errors.append(f"Found {unparseable_timestamps} unparseable timestamps in occurred_at")

        # 6. Split distribution
        split_distribution = {
            str(k): int(v) for k, v in df["split"].value_counts(dropna=False).items()
        }

        # 7. Target distribution
        target_distribution = {
            str(k): int(v) for k, v in df["recovered"].value_counts(dropna=False).items()
        }

        is_valid = len(errors) == 0

        return ValidationReport(
            is_valid=is_valid,
            total_rows=total_rows,
            unique_events=unique_events,
            unique_customers=unique_customers,
            missing_counts=missing_counts,
            invalid_event_types=invalid_event_types,
            invalid_failure_reasons=invalid_reasons,
            invalid_amounts=invalid_amounts,
            unparseable_timestamps=unparseable_timestamps,
            split_distribution=split_distribution,
            target_distribution=target_distribution,
            errors=errors,
        )
