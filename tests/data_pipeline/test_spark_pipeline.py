"""
Integration test for PySpark Big Data ETL pipeline.
"""

import csv
import os
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_HADOOP_DIR = _ROOT / "hadoop"
if (_HADOOP_DIR / "bin" / "winutils.exe").exists():
    os.environ["HADOOP_HOME"] = str(_HADOOP_DIR)
    _bin_str = str(_HADOOP_DIR / "bin")
    if _bin_str not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _bin_str + os.pathsep + os.environ.get("PATH", "")

from pipeline.spark_pipeline import (  # noqa: E402
    RAW_EVENT_SPARK_SCHEMA,
    SparkBigDataPipeline,
)


@pytest.fixture(scope="module")
def spark_pipeline(tmp_path_factory):
    fixture_dir = tmp_path_factory.mktemp("spark-pipeline-data")
    data_dir = fixture_dir / "training"
    data_dir.mkdir()
    events_path = data_dir / "payment_events.csv"
    columns = [field.name for field in RAW_EVENT_SPARK_SCHEMA.fields]
    event_types = ["CHECKOUT_ABANDONED", "FAILED_PAYMENT", "FAILED_SUBSCRIPTION"]
    failure_reasons = ["INSUFFICIENT_FUNDS", "NETWORK_ERROR", "CARD_DECLINED", "EXPIRED", "FRAUD"]
    with events_path.open("w", newline="", encoding="utf-8") as events_file:
        writer = csv.DictWriter(events_file, fieldnames=columns)
        writer.writeheader()
        for index in range(30):
            writer.writerow(
                {
                    "schema_version": "1",
                    "event_id": f"event-{index:03}",
                    "event_type": event_types[index % len(event_types)],
                    "customer_id": f"customer-{index % 6}",
                    "amount_paise": 10000 + index * 100,
                    "currency": "INR",
                    "failure_reason": failure_reasons[index % len(failure_reasons)],
                    "occurred_at": f"2025-01-{index // 24 + 1:02}T{index % 24:02}:00:00Z",
                    "payment_method": "card",
                    "device_type": "web",
                    "country": "IN",
                    "retry_count": index % 4,
                    "recovered": str(index % 2 == 0).lower(),
                    "is_synthetic": "false",
                    "split": "train",
                }
            )

    output_dir = fixture_dir / "output"
    pipeline = SparkBigDataPipeline(data_dir=data_dir, output_dir=output_dir)
    yield pipeline
    pipeline.spark.stop()


def test_spark_pipeline_schema_loading(spark_pipeline):
    df = spark_pipeline.load_raw_events()
    assert df.count() == 30
    assert "event_id" in df.columns
    assert "amount_paise" in df.columns
    assert "customer_id" in df.columns


def test_spark_pipeline_transformation_columns(spark_pipeline):
    df = spark_pipeline.load_raw_events()
    transformed_df, (t70, t85) = spark_pipeline.transform(df)
    cols = transformed_df.columns
    assert "cust_prior_events" in cols
    assert "hours_since_prev_event" in cols
    assert "cust_prior_retry_total" in cols
    assert "chrono_split" in cols
    assert t70 < t85


def test_spark_sql_analytics_queries(spark_pipeline):
    df = spark_pipeline.load_raw_events()
    transformed_df, _ = spark_pipeline.transform(df)
    analytics = spark_pipeline.run_spark_sql_analytics(transformed_df)
    assert len(analytics["by_event_type"]) == 3
    assert len(analytics["by_failure_reason"]) >= 5
    assert len(analytics["split_integrity"]) == 3
    assert "execution_plan_explain" in analytics
