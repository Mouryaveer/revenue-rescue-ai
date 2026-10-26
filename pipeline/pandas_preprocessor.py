"""
Reproducible Pandas-based preprocessing pipeline for RevenueRescue AI.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pipeline.leakage_audit import LeakageAuditor
from pipeline.schema import DataValidator


class PandasPreprocessor:
    """Preprocesses raw synthetic payment events into leakage-free Parquet dataset."""

    TARGET = "recovered"
    CATEGORICAL_COLUMNS = [
        "event_type",
        "failure_reason",
        "payment_method",
        "device_type",
        "country",
    ]
    NUMERIC_COLUMNS = [
        "amount_paise",
        "retry_count",
        "event_hour_utc",
        "event_dayofweek_utc",
        "cust_prior_events",
        "cust_prior_amount_mean",
        "cust_prior_retry_total",
        "cust_prior_checkout_abandoned",
        "cust_prior_failed_payment",
        "cust_prior_failed_subscription",
        "cust_prior_same_failure_reason",
        "hours_since_prev_event",
    ]
    HISTORY_FEATURES = [
        "cust_prior_events",
        "cust_prior_amount_mean",
        "cust_prior_retry_total",
        "cust_prior_checkout_abandoned",
        "cust_prior_failed_payment",
        "cust_prior_failed_subscription",
        "cust_prior_same_failure_reason",
        "hours_since_prev_event",
    ]

    def __init__(self, data_dir: Path | None = None, output_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parent.parent
        self.data_dir = data_dir or (root / "data" / "training")
        self.output_dir = output_dir or (root / "data" / "preprocessed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def load_and_validate_raw_events(self, filename: str = "payment_events.csv") -> pd.DataFrame:
        csv_path = self.data_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Raw data file not found at {csv_path}")

        df = pd.read_csv(csv_path)
        report = DataValidator.validate_dataframe(df)
        if not report.is_valid:
            raise ValueError(f"Data validation failed on raw dataset: {report.errors}")

        return df

    def transform(
        self, df_raw: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
        events = df_raw.rename(columns={"split": "supplied_split"}).copy()
        events["occurred_at"] = pd.to_datetime(events["occurred_at"], utc=True)

        # 1. Event-time features
        events["event_hour_utc"] = events["occurred_at"].dt.hour.astype("int16")
        events["event_dayofweek_utc"] = events["occurred_at"].dt.dayofweek.astype("int16")

        # 2. Strict chronological sorting per customer
        events = events.sort_values(["customer_id", "occurred_at", "event_id"]).reset_index(
            drop=True
        )
        g = events.groupby("customer_id", sort=False)

        # 3. Point-in-time customer history features (strictly before current event)
        events["cust_prior_events"] = g.cumcount().astype("int16")
        prev_ts = g["occurred_at"].shift(1)
        events["hours_since_prev_event"] = (
            events["occurred_at"] - prev_ts
        ).dt.total_seconds() / 3600.0

        prior_amount_sum = g["amount_paise"].cumsum() - events["amount_paise"]
        events["cust_prior_amount_mean"] = prior_amount_sum / events["cust_prior_events"].replace(
            0, np.nan
        )
        events["cust_prior_retry_total"] = (
            g["retry_count"].cumsum() - events["retry_count"]
        ).astype("int16")

        # Event type specific history counts
        event_types = sorted(events["event_type"].unique())
        for et in event_types:
            flag = (events["event_type"] == et).astype("int16")
            col_name = f"cust_prior_{et.lower()}"
            events[col_name] = (flag.groupby(events["customer_id"]).cumsum() - flag).astype("int16")

        events["cust_prior_same_failure_reason"] = (
            events.groupby(["customer_id", "failure_reason"], sort=False).cumcount().astype("int16")
        )

        # Ensure required columns exist even if zero occurrences
        for req in [
            "cust_prior_checkout_abandoned",
            "cust_prior_failed_payment",
            "cust_prior_failed_subscription",
        ]:
            if req not in events.columns:
                events[req] = 0

        # Sanity check: first event of every customer has no history
        first = events["cust_prior_events"] == 0
        assert (
            events.loc[first, "hours_since_prev_event"].isna().all()
        ), "First customer event must have NaN hours_since_prev_event"
        assert (events.loc[first, "cust_prior_retry_total"] == 0).all()
        assert (
            events["hours_since_prev_event"].dropna() >= 0
        ).all(), "Found negative time deltas in customer history"

        # 4. Chronological splits (70% train, 15% validation, 15% test by timestamp quantile)
        t70, t85 = events["occurred_at"].quantile([0.70, 0.85])
        events["chrono_split"] = np.select(
            [events["occurred_at"] < t70, events["occurred_at"] < t85],
            ["train", "validation"],
            default="test",
        )

        # Audit leakage and split integrity
        all_features = self.CATEGORICAL_COLUMNS + self.NUMERIC_COLUMNS
        leakage_report = LeakageAuditor.audit_features_and_splits(
            df=events,
            feature_columns=all_features,
            timestamp_col="occurred_at",
            split_col="chrono_split",
            customer_id_col="customer_id",
        )
        if not leakage_report.is_leakage_free:
            raise ValueError(f"Leakage audit failed: {leakage_report.violations}")

        manifest = {
            "dataset_version": "synthetic-payment-events.v1",
            "all_data_synthetic": True,
            "rows": len(events),
            "feature_version": "rr-features.v2",
            "supplied_split_counts": {
                str(k): int(v) for k, v in events["supplied_split"].value_counts().items()
            },
            "chrono_split_counts": {
                str(k): int(v) for k, v in events["chrono_split"].value_counts().items()
            },
            "chrono_cutoffs_utc": {
                "validation_start": str(
                    events[events["chrono_split"] == "validation"]["occurred_at"].min()
                ),
                "test_start": str(events[events["chrono_split"] == "test"]["occurred_at"].min()),
            },
            "supplied_split_is_time_overlapping": True,
            "missing_value_policy": "NaN kept in hours_since_prev_event & cust_prior_amount_mean (handled natively by tree models)",
            "processing_engine": "pandas (vectorized, point-in-time safe)",
            "seed": 42,
        }

        feature_spec = {
            "feature_version": "rr-features.v2",
            "target": self.TARGET,
            "categorical": self.CATEGORICAL_COLUMNS,
            "numeric": self.NUMERIC_COLUMNS,
            "history_features": self.HISTORY_FEATURES,
            "excluded": {
                "recovered": "target",
                "event_id": "identifier",
                "customer_id": "identifier (grouping only)",
                "occurred_at": "raw timestamp",
                "supplied_split": "split metadata",
                "chrono_split": "split metadata",
                "schema_version": "constant metadata",
                "currency": "constant (INR)",
                "is_synthetic": "constant metadata",
            },
            "sequence_order": ["customer_id", "occurred_at", "event_id"],
            "split_columns": {
                "chrono_split": "primary (forward-in-time)",
                "supplied_split": "random (comparison only)",
            },
        }

        return events, manifest, feature_spec

    def run(self, input_file: str = "payment_events.csv") -> Path:
        raw_df = self.load_and_validate_raw_events(input_file)
        clean_events, manifest, feature_spec = self.transform(raw_df)

        out_parquet = self.output_dir / "events_clean.parquet"
        clean_events.to_parquet(out_parquet, index=False)

        manifest_path = self.output_dir / "preprocessing_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        spec_path = self.output_dir / "feature_spec.json"
        with open(spec_path, "w", encoding="utf-8") as f:
            json.dump(feature_spec, f, indent=2)

        return out_parquet


if __name__ == "__main__":
    preprocessor = PandasPreprocessor()
    path = preprocessor.run()
    print(f"Preprocessed parquet generated at {path}")
