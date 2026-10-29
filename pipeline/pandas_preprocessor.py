"""
Reproducible Pandas preprocessing for RevenueRescue AI (the reference implementation).

The preprocessing notebook and the Spark pipeline must produce the same features as this module;
``tests/data_pipeline/test_spark_pandas_parity.py`` checks Spark against it.

Feature definitions (``rr-features.v2``)
----------------------------------------
Events are ordered per customer by ``(occurred_at, event_id)``. For an event ``e`` of customer
``c`` the *prior* events are the events of ``c`` that come strictly before ``e`` in this order.

* ``event_hour_utc``, ``event_dayofweek_utc`` (Monday = 0) — from ``occurred_at`` in UTC.
* ``cust_prior_events`` — number of prior events.
* ``hours_since_prev_event`` — hours since the immediately prior event; NaN if none.
* ``cust_prior_amount_mean`` — mean ``amount_paise`` of prior events; NaN if none.
* ``cust_prior_retry_total`` — sum of ``retry_count`` of prior events.
* ``cust_prior_{checkout_abandoned,failed_payment,failed_subscription}`` — prior events by type.
* ``cust_prior_same_failure_reason`` — prior events with the same ``failure_reason``.

No feature reads ``recovered``, and no feature reads a later event.
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
from pipeline.splits import (
    SEQUENCE_ORDER,
    SPLIT_RULE_TEXT,
    SPLIT_RULE_VERSION,
    assign_chrono_split,
    chrono_cutoffs,
)

FEATURE_VERSION = "rr-features.v2"
DATASET_VERSION = "synthetic-payment-events.v1"
HISTORY_EVENT_TYPES = ["CHECKOUT_ABANDONED", "FAILED_PAYMENT", "FAILED_SUBSCRIPTION"]


class PandasPreprocessor:
    """Preprocesses raw synthetic payment events into a leakage-free Parquet dataset."""

    TARGET = "recovered"
    CATEGORICAL_COLUMNS = [
        "event_type",
        "failure_reason",
        "payment_method",
        "device_type",
        "country",
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
    NUMERIC_COLUMNS = [
        "amount_paise",
        "retry_count",
        "event_hour_utc",
        "event_dayofweek_utc",
        *HISTORY_FEATURES,
    ]
    EXCLUDED = {
        "recovered": "target",
        "event_id": "identifier (tie-breaker for ordering)",
        "customer_id": "identifier (grouping only)",
        "occurred_at": "raw timestamp (ordering only)",
        "supplied_split": "split metadata (random split from the generator)",
        "chrono_split": "split metadata (canonical)",
        "schema_version": "constant metadata",
        "currency": "constant (INR)",
        "is_synthetic": "constant metadata",
    }

    def __init__(self, data_dir: Path | None = None, output_dir: Path | None = None) -> None:
        root = Path(__file__).resolve().parent.parent
        self.data_dir = data_dir or (root / "data" / "training")
        self.output_dir = output_dir or (root / "data" / "preprocessed")

    @staticmethod
    def sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def load_and_validate_raw_events(self, filename: str = "payment_events.csv") -> pd.DataFrame:
        csv_path = self.data_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Raw data file not found at {csv_path}")
        df = pd.read_csv(csv_path, low_memory=False)
        report = DataValidator.validate_dataframe(df)
        if not report.is_valid:
            raise ValueError(f"Data validation failed on raw dataset: {report.errors}")
        return df

    # ------------------------------------------------------------------ steps
    @classmethod
    def clean(cls, df_raw: pd.DataFrame) -> pd.DataFrame:
        """Strip strings, cast the target to int8, parse timestamps to UTC, add calendar features."""
        events = df_raw.rename(columns={"split": "supplied_split"}).copy()
        for col in events.select_dtypes(include=["object", "string"]).columns:
            if col != "occurred_at":
                events[col] = events[col].astype("string").str.strip().astype(object)
        target = events[cls.TARGET]
        if target.dtype == object:
            target = target.astype(str).str.strip().str.lower().map({"true": 1, "false": 0, "1": 1, "0": 0})
        events[cls.TARGET] = target.astype("int8")
        events["occurred_at"] = pd.to_datetime(events["occurred_at"], utc=True, errors="raise")
        events["event_hour_utc"] = events["occurred_at"].dt.hour.astype("int16")
        events["event_dayofweek_utc"] = events["occurred_at"].dt.dayofweek.astype("int16")
        return events

    @staticmethod
    def add_history_features(events: pd.DataFrame) -> pd.DataFrame:
        """Point-in-time customer history (strictly prior events only)."""
        events = events.sort_values(SEQUENCE_ORDER, kind="mergesort").reset_index(drop=True)
        g = events.groupby("customer_id", sort=False)

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
        for et in HISTORY_EVENT_TYPES:
            flag = (events["event_type"] == et).astype("int16")
            events[f"cust_prior_{et.lower()}"] = (
                flag.groupby(events["customer_id"]).cumsum() - flag
            ).astype("int16")
        events["cust_prior_same_failure_reason"] = (
            events.groupby(["customer_id", "failure_reason"], sort=False).cumcount().astype("int16")
        )

        first = events["cust_prior_events"] == 0
        if not events.loc[first, "hours_since_prev_event"].isna().all():
            raise AssertionError("first customer event must have NaN hours_since_prev_event")
        if not (events.loc[first, "cust_prior_retry_total"] == 0).all():
            raise AssertionError("first customer event must have zero prior retries")
        if (events["hours_since_prev_event"].dropna() < 0).any():
            raise AssertionError("negative time delta in customer history")
        return events

    @staticmethod
    def add_chrono_split(events: pd.DataFrame) -> tuple[pd.DataFrame, tuple]:
        cutoffs = chrono_cutoffs(events["occurred_at"])
        events = events.copy()
        events["chrono_split"] = assign_chrono_split(events["occurred_at"], cutoffs)
        return events, cutoffs

    # --------------------------------------------------------------- pipeline
    def transform(
        self, df_raw: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[str, Any], dict[str, Any]]:
        events = self.clean(df_raw)
        events = self.add_history_features(events)
        events, (t70, t85) = self.add_chrono_split(events)

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

        supplied_overlap = None
        if "supplied_split" in events and events["supplied_split"].notna().all():
            rng = events.groupby("supplied_split")["occurred_at"].agg(["min", "max"])
            if {"train", "test"} <= set(rng.index):
                supplied_overlap = bool(rng.loc["test", "min"] < rng.loc["train", "max"])

        manifest = {
            "dataset_version": DATASET_VERSION,
            "all_data_synthetic": bool(events.get("is_synthetic", pd.Series([True])).all()),
            "rows": len(events),
            "feature_version": FEATURE_VERSION,
            "split_rule_version": SPLIT_RULE_VERSION,
            "split_rule": SPLIT_RULE_TEXT,
            "sequence_order": SEQUENCE_ORDER,
            "tie_breaking": "events with equal occurred_at are ordered by event_id",
            "supplied_split_counts": {
                str(k): int(v) for k, v in events["supplied_split"].value_counts().items()
            },
            "chrono_split_counts": {
                str(k): int(v) for k, v in events["chrono_split"].value_counts().items()
            },
            "chrono_cutoffs_utc": {"validation_start": str(t70), "test_start": str(t85)},
            "supplied_split_is_time_overlapping": supplied_overlap,
            "leakage_audit": leakage_report.to_dict(),
            "missing_value_policy": "NaN kept in hours_since_prev_event and cust_prior_amount_mean "
            "for first events (no history); LightGBM handles NaN natively",
            "processing_engine": "pandas (local, single node)",
        }
        feature_spec = self.feature_spec()
        return events, manifest, feature_spec

    @classmethod
    def feature_spec(cls) -> dict[str, Any]:
        return {
            "feature_version": FEATURE_VERSION,
            "target": cls.TARGET,
            "categorical": cls.CATEGORICAL_COLUMNS,
            "numeric": cls.NUMERIC_COLUMNS,
            "history_features": cls.HISTORY_FEATURES,
            "excluded": cls.EXCLUDED,
            "sequence_order": SEQUENCE_ORDER,
            "split_rule_version": SPLIT_RULE_VERSION,
            "split_columns": {
                "chrono_split": "canonical (forward-in-time)",
                "supplied_split": "random, comparison only",
            },
        }

    def write_outputs(
        self,
        events: pd.DataFrame,
        manifest: dict[str, Any],
        feature_spec: dict[str, Any],
        source_csv: Path | None = None,
    ) -> Path:
        """Write Parquet (snappy), feature spec, manifest and checksums."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        out_parquet = self.output_dir / "events_clean.parquet"
        events.to_parquet(out_parquet, index=False, compression="snappy")
        if source_csv is not None and source_csv.exists():
            manifest = {
                **manifest,
                "source_file": source_csv.name,
                "source_sha256": self.sha256_file(source_csv),
            }
        manifest = {**manifest, "events_clean_sha256": self.sha256_file(out_parquet)}
        (self.output_dir / "feature_spec.json").write_text(
            json.dumps(feature_spec, indent=2), encoding="utf-8"
        )
        (self.output_dir / "preprocessing_manifest.json").write_text(
            json.dumps(manifest, indent=2, default=str), encoding="utf-8"
        )
        rows = [
            {"file": p.name, "bytes": p.stat().st_size, "sha256": self.sha256_file(p)}
            for p in sorted(self.output_dir.iterdir())
            if p.is_file() and p.name != "output_checksums.csv"
        ]
        pd.DataFrame(rows).to_csv(self.output_dir / "output_checksums.csv", index=False)
        return out_parquet

    def run(self, input_file: str = "payment_events.csv") -> Path:
        raw_df = self.load_and_validate_raw_events(input_file)
        clean_events, manifest, feature_spec = self.transform(raw_df)
        return self.write_outputs(clean_events, manifest, feature_spec, self.data_dir / input_file)


if __name__ == "__main__":
    path = PandasPreprocessor().run()
    print(f"Preprocessed parquet generated at {path}")
