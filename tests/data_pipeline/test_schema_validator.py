"""
Unit tests for data schema validation.
"""

import pandas as pd

from pipeline.schema import DataValidator


def make_valid_row(**kwargs):
    row = {
        "schema_version": "payment-event.v1",
        "event_id": "EVT-001",
        "event_type": "FAILED_PAYMENT",
        "customer_id": "CUST-001",
        "amount_paise": 10000,
        "currency": "INR",
        "failure_reason": "GATEWAY_TEMPORARY",
        "occurred_at": "2026-03-01T10:00:00Z",
        "payment_method": "card",
        "device_type": "mobile",
        "country": "IN",
        "retry_count": 0,
        "recovered": False,
        "is_synthetic": True,
        "split": "train",
    }
    row.update(kwargs)
    return row


def test_validator_valid_dataset():
    df = pd.DataFrame([make_valid_row(event_id="EVT-1"), make_valid_row(event_id="EVT-2")])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is True
    assert report.total_rows == 2
    assert report.unique_events == 2
    assert len(report.errors) == 0


def test_validator_missing_column():
    df = pd.DataFrame([make_valid_row()])
    df = df.drop(columns=["customer_id"])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is False
    assert any("Missing required columns" in err for err in report.errors)


def test_validator_duplicate_event_id():
    df = pd.DataFrame([make_valid_row(event_id="EVT-1"), make_valid_row(event_id="EVT-1")])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is False
    assert any("Duplicate event_ids" in err for err in report.errors)


def test_validator_non_positive_amount():
    df = pd.DataFrame([make_valid_row(amount_paise=0)])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is False
    assert any("non-positive amount_paise" in err for err in report.errors)


def test_validator_invalid_event_type():
    df = pd.DataFrame([make_valid_row(event_type="INVALID_TYPE")])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is False
    assert any("Invalid event types" in err for err in report.errors)


def test_validator_unparseable_timestamp():
    df = pd.DataFrame([make_valid_row(occurred_at="not-a-timestamp")])
    report = DataValidator.validate_dataframe(df)
    assert report.is_valid is False
    assert any("unparseable timestamps" in err for err in report.errors)
