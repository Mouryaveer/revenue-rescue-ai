"""Tests for threshold selection, bootstrap, calibration and report promotion."""

import json

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from evaluation.metrics import evaluate_binary
from evaluation.protocol import (
    Calibrator,
    bootstrap_ci,
    paired_bootstrap_difference,
    select_calibration,
    select_threshold,
    threshold_table,
)
from evaluation.report import (
    ReportPromotionError,
    environment_info,
    promote_to_latest,
    render_markdown,
    write_run,
)


@pytest.fixture
def data():
    rng = np.random.default_rng(7)
    n = 2000
    y = rng.binomial(1, 0.6, n)
    score = y * 0.8 + rng.normal(0, 1, n)
    p = 1 / (1 + np.exp(-score))
    return y, p


def test_threshold_table_rows_are_single_operating_points(data):
    y, p = data
    rows = threshold_table(y, p, [0.3, 0.5, 0.7])
    for r in rows:
        ref = evaluate_binary(y, p, threshold=r["threshold"])
        assert r["tp"] == ref["confusion_matrix"]["tp"]
        assert r["f1"] == pytest.approx(ref["metrics"]["f1"])
        assert r["mcc"] == pytest.approx(ref["metrics"]["mcc"])
    assert rows[0]["coverage"] >= rows[1]["coverage"] >= rows[2]["coverage"]


def test_select_threshold_methods(data):
    y, p = data
    rows = {r["threshold"]: r for r in threshold_table(y, p)}
    yj = select_threshold(y, p, "youden")
    assert rows[yj.threshold]["balanced_accuracy"] == max(
        r["balanced_accuracy"] for r in rows.values() if r["balanced_accuracy"] is not None
    )
    f1 = select_threshold(y, p, "max_f1")
    assert rows[f1.threshold]["f1"] == max(r["f1"] for r in rows.values() if r["f1"] is not None)
    assert select_threshold(y, p, "fixed", fixed=0.42).threshold == 0.42


def test_min_precision_feasible_and_infeasible(data):
    y, p = data
    hc = select_threshold(y, p, "min_precision", target_precision=0.8, min_coverage=0.05)
    r = evaluate_binary(y, p, threshold=hc.threshold)["metrics"]
    assert hc.feasible and r["precision"] >= 0.8 and r["coverage"] >= 0.05
    bad = select_threshold(y, p, "min_precision", target_precision=0.999, min_coverage=0.2)
    assert bad.feasible is False and "not reachable" in bad.note


def test_unknown_method():
    with pytest.raises(ValueError):
        select_threshold([0, 1], [0.2, 0.8], "magic")


def test_bootstrap_ci_reproducible_and_brackets_point(data):
    y, p = data
    a = bootstrap_ci(y, p, 0.5, n_boot=200, seed=1)
    b = bootstrap_ci(y, p, 0.5, n_boot=200, seed=1)
    assert a == b
    for m in ["roc_auc", "pr_auc", "precision", "recall", "f1", "brier"]:
        assert a[m]["status"] == "ok"
        assert a[m]["low"] <= a[m]["point"] <= a[m]["high"]
    assert a["roc_auc"]["point"] == pytest.approx(roc_auc_score(y, p))


def test_bootstrap_tiny_single_class_reports_insufficient():
    y = np.array([1, 1, 1, 0])
    p = np.array([0.9, 0.8, 0.7, 0.1])
    ci = bootstrap_ci(y, p, 0.5, n_boot=50, seed=0, min_valid=100)
    assert ci["roc_auc"]["low"] is None
    assert "insufficient" in ci["roc_auc"]["status"]
    assert ci["roc_auc"]["n_skipped"] > 0


def test_paired_difference_zero_for_identical(data):
    y, p = data
    d = paired_bootstrap_difference(y, p, p, n_boot=100)
    assert d["difference"] == 0 and d["low"] == 0 and d["high"] == 0


def test_calibration_selection_fixes_miscalibrated_scores(data):
    y, p = data
    squashed = 0.5 + 0.2 * (p - 0.5)  # under-confident, monotone
    sel = select_calibration(y, squashed)
    assert sel["method"] in {"sigmoid", "isotonic"}
    cal = sel["calibrator"].transform(squashed)
    assert evaluate_binary(y, cal)["metrics"]["log_loss"] < evaluate_binary(y, squashed)["metrics"]["log_loss"]
    assert len(sel["cross_fitted_validation_probs"]) == len(y)


def test_calibration_none_keeps_probabilities(data):
    y, p = data
    c = Calibrator("none").fit(p, y)
    assert np.array_equal(c.transform(p), p)


def _report(status="complete"):
    y = np.array([0, 1, 1, 0, 1])
    p = np.array([0.2, 0.7, 0.6, 0.4, 0.9])
    ev = evaluate_binary(y, p, threshold=0.5)
    return {
        "status": status,
        "run_id": "eval-test",
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "seed": 42,
        "dataset": {
            "path": "x.parquet", "sha256": "0" * 64, "rows": 5, "feature_version": "v",
            "synthetic": True, "split_column": "chrono_split", "split_rule": "rule",
            "splits": [{"split": "test", "rows": 5, "positives": 3, "prevalence": 0.6,
                        "start": "a", "end": "b"}],
        },
        "protocol": {"threshold_selection": "t", "calibration_selection": "c", "test_usage": "once"},
        "bootstrap": {"method": "m"},
        "models": {"M": {"validation": ev, "test": ev, "test_ci": {}}},
        "environment": environment_info(),
    }


def test_render_markdown_contains_all_metric_names():
    md = render_markdown(_report())
    for k in ["roc_auc", "log_loss", "mape_nonzero_pct", "cohen_kappa", "mcc", "specificity"]:
        assert k in md
    assert "| M | 0.50 |" in md  # threshold column filled


def test_promotion_refuses_incomplete_and_keeps_previous(tmp_path):
    good = _report()
    run = write_run(good, tmp_path)
    promote_to_latest(run, tmp_path, good)
    before = (tmp_path / "latest.json").read_text()
    bad = {**_report("failed"), "run_id": "eval-bad"}
    bad_run = write_run(bad, tmp_path)
    with pytest.raises(ReportPromotionError):
        promote_to_latest(bad_run, tmp_path, bad)
    assert (tmp_path / "latest.json").read_text() == before
    assert json.loads(before)["run_id"] == "eval-test"
    assert (tmp_path / "runs" / "eval-bad" / "report.json").exists()
