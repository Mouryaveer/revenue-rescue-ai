"""
Spark ↔ Pandas parity for the preprocessing pipeline.

Uses a deterministic synthetic fixture with timestamp ties (globally and within one customer),
customers with several events, and a non-UTC-looking hour range, so that time-zone, ordering and
split-boundary bugs show up as feature mismatches.
"""

from __future__ import annotations

import csv
import random
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pyspark")

from pipeline.pandas_preprocessor import PandasPreprocessor  # noqa: E402
from pipeline.spark_pipeline import (  # noqa: E402
    FEATURE_COLUMNS,
    RAW_EVENT_SPARK_SCHEMA,
    SparkBigDataPipeline,
    SparkValidationError,
)
from pipeline.splits import chrono_cutoffs  # noqa: E402

EVENT_TYPES = ["CHECKOUT_ABANDONED", "FAILED_PAYMENT", "FAILED_SUBSCRIPTION"]
REASONS = ["INSUFFICIENT_FUNDS", "BANK_DECLINE", "GATEWAY_TEMPORARY", "EXPIRED_METHOD", "UNKNOWN"]
FLOAT_TOL = 1e-9


def _rows(n: int = 400, seed: int = 3) -> list[dict]:
    rnd = random.Random(seed)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for i in range(n):
        # minute resolution over ~10 days with many collisions
        ts = start + timedelta(minutes=rnd.randrange(0, 60 * 24 * 10, 7))
        et = rnd.choice(EVENT_TYPES)
        rows.append(
            {
                "schema_version": "payment-event.v1",
                "event_id": f"EVT-{rnd.randrange(10**9):09d}-{i:04d}",
                "event_type": et,
                "customer_id": f"CUST-{rnd.randrange(60):03d}",
                "amount_paise": rnd.randrange(10_000, 500_000),
                "currency": "INR",
                "failure_reason": "CHECKOUT_ABANDONED" if et == "CHECKOUT_ABANDONED" else rnd.choice(REASONS),
                "occurred_at": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "payment_method": rnd.choice(["card", "upi", "wallet"]),
                "device_type": rnd.choice(["web", "ios", "android"]),
                "country": rnd.choice(["IN", "US"]),
                "retry_count": rnd.randrange(4),
                "recovered": rnd.random() < 0.6,
                "is_synthetic": True,
                "split": rnd.choice(["train", "validation", "test"]),
            }
        )
    # force an exact same-customer, same-timestamp tie
    rows[1]["customer_id"], rows[1]["occurred_at"] = rows[0]["customer_id"], rows[0]["occurred_at"]
    return rows


def _write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[fld.name for fld in RAW_EVENT_SPARK_SCHEMA.fields])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "recovered": str(r["recovered"]), "is_synthetic": str(r["is_synthetic"])})


@pytest.fixture(scope="module")
def outputs(tmp_path_factory):
    base = tmp_path_factory.mktemp("parity")
    data_dir = base / "training"
    data_dir.mkdir()
    _write(data_dir / "payment_events.csv", _rows())

    pdf, _, _ = PandasPreprocessor(data_dir=data_dir, output_dir=base / "pd").transform(
        pd.read_csv(data_dir / "payment_events.csv")
    )
    with SparkBigDataPipeline(data_dir=data_dir, output_dir=base / "spark", shuffle_partitions=2) as sp:
        raw = sp.load_raw_events()
        sdf, cutoffs = sp.transform(raw)
        spark_pd = sdf.toPandas()
        analytics = sp.run_spark_sql_analytics(sdf, write_report=False)
        path = sp.write_partitioned_parquet(sdf)
        pruning = sp.inspect_pruning(path)
        validation = sp.validate(raw)
        yield {
            "pandas": pdf, "spark": spark_pd, "cutoffs": cutoffs, "analytics": analytics,
            "pruning": pruning, "validation": validation, "pipeline": sp, "data_dir": data_dir,
        }


def _joined(outputs):
    p = outputs["pandas"].set_index("event_id").sort_index()
    s = outputs["spark"].set_index("event_id").sort_index()
    return p, s


def test_row_count_and_ids_match(outputs):
    p, s = _joined(outputs)
    assert len(p) == len(s) == 400
    assert p.index.equals(s.index)


def test_validation_passes_on_clean_fixture(outputs):
    assert outputs["validation"]["is_valid"], outputs["validation"]["errors"]


@pytest.mark.parametrize("col", FEATURE_COLUMNS)
def test_feature_parity(outputs, col):
    p, s = _joined(outputs)
    a, b = p[col], s[col]
    if col in {"event_type", "failure_reason", "payment_method", "device_type", "country"}:
        assert (a.astype(str) == b.astype(str)).all()
        return
    a, b = a.astype(float).to_numpy(), b.astype(float).to_numpy()
    assert np.array_equal(np.isnan(a), np.isnan(b)), f"{col}: missing-value pattern differs"
    m = ~np.isnan(a)
    np.testing.assert_allclose(a[m], b[m], rtol=0, atol=FLOAT_TOL, err_msg=col)


def test_hour_is_utc(outputs):
    p, s = _joined(outputs)
    expected = pd.to_datetime(p["occurred_at"], utc=True).dt.hour
    assert (s["event_hour_utc"].astype(int) == expected).all()


def test_split_parity_and_cutoffs(outputs):
    p, s = _joined(outputs)
    assert (p["chrono_split"] == s["chrono_split"]).all()
    t70, t85 = chrono_cutoffs(p["occurred_at"])
    assert outputs["cutoffs"] == (int(t70.timestamp()), int(t85.timestamp()))


def test_equal_timestamps_share_split(outputs):
    p, _ = _joined(outputs)
    assert (p.groupby("occurred_at")["chrono_split"].nunique() == 1).all()


def test_same_customer_tie_broken_by_event_id(outputs):
    p, _ = _joined(outputs)
    tie = p.reset_index().groupby(["customer_id", "occurred_at"]).filter(lambda d: len(d) > 1)
    assert not tie.empty
    for _, d in tie.groupby(["customer_id", "occurred_at"]):
        d = d.sort_values("event_id")
        assert d["cust_prior_events"].is_monotonic_increasing
        assert (d["cust_prior_events"].diff().dropna() == 1).all()
        assert (d["hours_since_prev_event"].iloc[1:] == 0).all()


def test_aggregation_parity(outputs):
    p = outputs["pandas"]
    exp = p.groupby("event_type").agg(
        total_events=("event_id", "size"),
        recovered_events=("recovered", "sum"),
        recovery_rate=("recovered", "mean"),
        total_at_risk_paise=("amount_paise", "sum"),
    )
    got = pd.DataFrame(outputs["analytics"]["by_event_type"]).set_index("event_type").sort_index()
    for col in exp.columns:
        np.testing.assert_allclose(
            got.loc[exp.index, col].astype(float), exp[col].astype(float), atol=1e-9, err_msg=col
        )
    split_rows = {r["chrono_split"]: r["row_count"] for r in outputs["analytics"]["split_integrity"]}
    assert split_rows == p["chrono_split"].value_counts().to_dict()


def test_partition_and_column_pruning_visible_in_plan(outputs):
    pr = outputs["pruning"]
    assert pr["partition_pruning_in_plan"], pr["file_scan_line"]
    assert pr["column_pruning_in_plan"], pr["read_schema"]


def test_validate_reports_bad_rows(outputs, tmp_path):
    rows = _rows(20)
    rows[0]["failure_reason"] = "NOT_A_REASON"
    rows[1]["amount_paise"] = 0
    rows[2]["event_id"] = rows[3]["event_id"]
    d = tmp_path / "bad"
    d.mkdir()
    _write(d / "payment_events.csv", rows)
    sp = outputs["pipeline"]
    old = sp.data_dir
    sp.data_dir = d
    try:
        rep = sp.validate(sp.load_raw_events())
        assert not rep["is_valid"]
        text = " ".join(rep["errors"])
        assert "NOT_A_REASON" in text and "duplicate" in text and "non positive" in text
        with pytest.raises(SparkValidationError):
            sp.run_pipeline()
    finally:
        sp.data_dir = old


def test_missing_input_file_raises(outputs, tmp_path):
    sp = outputs["pipeline"]
    old = sp.data_dir
    sp.data_dir = tmp_path
    try:
        with pytest.raises(FileNotFoundError):
            sp.load_raw_events()
    finally:
        sp.data_dir = old
