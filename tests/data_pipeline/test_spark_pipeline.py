"""
Integration test for PySpark Big Data ETL pipeline.
"""

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

from pipeline.spark_pipeline import SparkBigDataPipeline  # noqa: E402


@pytest.fixture(scope="module")
def spark_pipeline(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("spark-pipeline-output")
    pipeline = SparkBigDataPipeline(output_dir=output_dir)
    yield pipeline
    pipeline.spark.stop()


def test_spark_pipeline_schema_loading(spark_pipeline):
    df = spark_pipeline.load_raw_events()
    assert df.count() == 100000
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
